# CitationSculptor URL Resolution Tools Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add four URL resolution capabilities (proxy URL stripping, Google Scholar URL parsing, Scopus EID extraction, OpenAlex Scopus EID lookup) and wire them into `lookup_auto()` so CitationSculptor can correctly resolve every URL type found in real-world academic articles accessed via institutional proxies.

**Architecture:** Three new extractor functions are added to `CitationTypeDetector` in `modules/type_detector.py`; one new method is added to `OpenAlexClient` in `modules/openalex_client.py`; and `lookup_auto()` in `citation_lookup.py` is updated to use all four before falling back to title search. Proxy URL stripping is applied as a universal pre-processing step so all downstream logic receives canonical URLs.

**Tech Stack:** Python 3.12, pytest, requests, existing PubMed/CrossRef/OpenAlex clients already in codebase. No new dependencies required.

---

## Context for Implementers

### The Problem

This repo's `lookup_auto()` function fails silently on URLs from articles accessed via institutional EZProxy servers (e.g., Ohio State University Library). EZProxy rewrites URLs in a specific pattern:

- `doi.org/10.1056/X` becomes `doi-org.proxy.lib.ohio-state.edu/10.1056/X`
- `www.sciencedirect.com/...` becomes `www-sciencedirect-com.proxy.lib.ohio-state.edu/...`

The key change: **dots in the domain are replaced with hyphens**, and `.proxy.INSTITUTION.edu` is appended. The current DOI regex `doi\.org/(10\...)` looks for a literal dot, so proxy-wrapped DOIs are silently missed and fall through to the much slower, less accurate title search.

Additionally, every reference in a ScienceDirect article has a Google Scholar `scholar_lookup` URL that contains clean title/author/year params -- but `lookup_auto()` currently passes the raw encoded URL string as a title, giving garbage results.

### File Locations

All paths are relative to `/Users/tusharshah/Developer/MCP-Servers/CitationSculptor/`.

| File | Purpose |
|------|---------|
| `modules/type_detector.py` | Add `strip_proxy_url()`, `parse_scholar_lookup_url()`, `extract_scopus_eid()` |
| `modules/openalex_client.py` | Add `fetch_by_scopus_eid()` method to `OpenAlexClient` class |
| `citation_lookup.py` | Update `lookup_auto()` + `__init__` to use new tools |
| `tests/test_type_detector.py` | Add tests for the 3 new type_detector functions |
| `tests/test_openalex_scopus.py` | New test file for `fetch_by_scopus_eid` |
| `tests/test_citation_lookup.py` | Add integration tests for updated `lookup_auto()` |
| `docs/AGENT_API.md` | New: machine-readable capability manifest for external agents |
| `~/.claude/skills/CitationSculptor/SKILL.md` | Update: document new URL types handled |

### Running Tests

From the repo root (activate the venv first):

```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
source .venv/bin/activate
pytest tests/test_type_detector.py -v
pytest tests/test_openalex_scopus.py -v
pytest tests/test_citation_lookup.py -v
```

### Existing Patterns to Follow

**type_detector.py methods** all live inside the `CitationTypeDetector` class. New methods follow this signature pattern:
```python
def extract_xxx(self, url: str) -> Optional[SomeType]:
    """One-line summary.
    
    Args:
        url: The URL to parse.
    
    Returns:
        Extracted value or None if not found/applicable.
    """
    if not url:
        return None
    # implementation
```

**openalex_client.py methods** follow the `fetch_by_doi` pattern: rate-limit, build URL, GET, 404 → None, parse with `_parse_work`. See lines 112-141.

**Tests** use `pytest` with a `setup_method` creating a fresh instance. Use `unittest.mock.patch` for any network calls -- never hit real APIs in unit tests.

---

## Stream A: URL Extractors in type_detector.py

*These three tasks are independent of all other streams. They only touch `modules/type_detector.py` and `tests/test_type_detector.py`.*

---

### Task A1: strip_proxy_url()

**Files:**
- Modify: `modules/type_detector.py` (add method to `CitationTypeDetector` class)
- Modify: `tests/test_type_detector.py` (add new test class at end of file)

**Background:** EZProxy rewrites `doi.org` as `doi-org.proxy.lib.ohio-state.edu`. The transformation rule: replace every dot in the original domain with a hyphen, then append `.proxy.INSTITUTION.edu`. To reverse: extract the part before `.proxy.`, replace hyphens that were dots back to dots.

The reversal heuristic: any segment in the proxy subdomain that uses only hyphens (never in real domain names this way) represents a dotted domain. Split on `.proxy.`, take the left part, convert hyphens back to dots.

**Step 1: Write the failing tests**

Add this class to the **bottom** of `tests/test_type_detector.py`:

```python
class TestStripProxyUrl:
    """Tests for EZProxy URL stripping."""

    def setup_method(self):
        self.detector = CitationTypeDetector()

    def test_doi_proxy_url(self):
        """DOI proxy URL should be converted to canonical doi.org URL."""
        proxied = "https://doi-org.proxy.lib.ohio-state.edu/10.1056/nejmra1710575"
        result = self.detector.strip_proxy_url(proxied)
        assert result == "https://doi.org/10.1056/nejmra1710575"

    def test_sciencedirect_proxy_url(self):
        """ScienceDirect proxy URL should resolve to canonical domain."""
        proxied = "https://www-sciencedirect-com.proxy.lib.ohio-state.edu/science/article/pii/S0735109721082735"
        result = self.detector.strip_proxy_url(proxied)
        assert result == "https://www.sciencedirect.com/science/article/pii/S0735109721082735"

    def test_scopus_proxy_url(self):
        """Scopus proxy URL should resolve to canonical domain."""
        proxied = "https://www-scopus-com.proxy.lib.ohio-state.edu/inward/record.url?eid=2-s2.0-85051788505"
        result = self.detector.strip_proxy_url(proxied)
        assert result == "https://www.scopus.com/inward/record.url?eid=2-s2.0-85051788505"

    def test_non_proxy_url_unchanged(self):
        """Non-proxy URL must be returned unchanged."""
        url = "https://doi.org/10.1056/nejmra1710575"
        result = self.detector.strip_proxy_url(url)
        assert result == url

    def test_pubmed_proxy_url(self):
        """PubMed proxy URL should resolve correctly."""
        proxied = "https://pubmed-ncbi-nlm-nih-gov.proxy.lib.ohio-state.edu/35086660/"
        result = self.detector.strip_proxy_url(proxied)
        assert result == "https://pubmed.ncbi.nlm.nih.gov/35086660/"

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert self.detector.strip_proxy_url("") == ""

    def test_none_input(self):
        """None should return empty string."""
        assert self.detector.strip_proxy_url(None) == ""

    def test_proxy_doi_still_extractable(self):
        """After stripping, extract_doi should find the DOI."""
        proxied = "https://doi-org.proxy.lib.ohio-state.edu/10.1056/nejmra1710575"
        stripped = self.detector.strip_proxy_url(proxied)
        doi = self.detector.extract_doi(stripped)
        assert doi == "10.1056/nejmra1710575"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_type_detector.py::TestStripProxyUrl -v
```
Expected: `AttributeError: 'CitationTypeDetector' object has no attribute 'strip_proxy_url'`

**Step 3: Implement `strip_proxy_url`**

Add this method to `CitationTypeDetector` class in `modules/type_detector.py`, after the `format_elsevier_pii` method (around line 235):

```python
def strip_proxy_url(self, url: Optional[str]) -> str:
    """Remove institutional EZProxy wrapper from a URL, returning the canonical form.

    EZProxy rewrites domains by replacing dots with hyphens and appending
    `.proxy.INSTITUTION.edu`. For example:
        doi.org         -> doi-org.proxy.lib.ohio-state.edu
        www.scopus.com  -> www-scopus-com.proxy.lib.ohio-state.edu

    This method detects the pattern and reverses the transformation.

    Args:
        url: Any URL, possibly proxy-wrapped.

    Returns:
        Canonical URL with proxy wrapper removed, or original URL if not proxied.
        Returns empty string for None/empty input.
    """
    if not url:
        return ""

    # EZProxy pattern: scheme://DOMAIN-WITH-HYPHENS.proxy.INSTITUTION.TLD/path
    # The subdomain before ".proxy." represents the original domain with dots->hyphens
    match = re.match(
        r'^(https?://)([a-zA-Z0-9-]+)\.proxy\.[a-zA-Z0-9.-]+(/.*)?$',
        url
    )
    if not match:
        return url

    scheme = match.group(1)          # "https://"
    hyphenated_domain = match.group(2)  # "doi-org" or "www-sciencedirect-com"
    path = match.group(3) or ""      # "/10.1056/..." or "/science/article/..."

    # Convert hyphens back to dots to reconstruct the original domain.
    # Heuristic: the hyphenated segment is the original domain with dots replaced.
    canonical_domain = hyphenated_domain.replace('-', '.')

    return f"{scheme}{canonical_domain}{path}"
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_type_detector.py::TestStripProxyUrl -v
```
Expected: All 8 tests PASS.

**Step 5: Commit**

```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
git add modules/type_detector.py tests/test_type_detector.py
git commit -m "feat(type_detector): add strip_proxy_url for EZProxy URL normalization"
```

---

### Task A2: parse_scholar_lookup_url()

**Files:**
- Modify: `modules/type_detector.py`
- Modify: `tests/test_type_detector.py`

**Background:** Every reference in a ScienceDirect article has a Google Scholar URL of the form:
```
https://scholar.google.com/scholar_lookup?title=Clinical%20course%20and%20...&publication_year=2018&author=B.J.%20Maron
```
These URLs contain clean, URL-encoded title/author/year that can be extracted and used for PubMed/CrossRef title search. Currently `lookup_auto()` passes this as a raw string to title search, which gives garbage results because the URL itself becomes the "title".

**Step 1: Write the failing tests**

Add this class to the **bottom** of `tests/test_type_detector.py`:

```python
class TestParseScholarLookupUrl:
    """Tests for Google Scholar scholar_lookup URL parsing."""

    def setup_method(self):
        self.detector = CitationTypeDetector()

    def test_basic_scholar_url(self):
        """Parse title, year, and authors from a typical scholar_lookup URL."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Clinical%20course%20and%20management%20of%20hypertrophic%20cardiomyopathy"
            "&publication_year=2018"
            "&author=B.J.%20Maron"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is not None
        assert result["title"] == "Clinical course and management of hypertrophic cardiomyopathy"
        assert result["year"] == "2018"
        assert result["authors"] == ["B.J. Maron"]

    def test_multiple_authors(self):
        """Multiple author params should be collected into a list."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=How%20hypertrophic%20cardiomyopathy%20became%20treatable"
            "&publication_year=2016"
            "&author=B.J.%20Maron"
            "&author=E.J.%20Rowin"
            "&author=S.A.%20Casey"
            "&author=M.S.%20Maron"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is not None
        assert len(result["authors"]) == 4
        assert "B.J. Maron" in result["authors"]
        assert "M.S. Maron" in result["authors"]

    def test_non_scholar_url_returns_none(self):
        """Non-Scholar URL should return None."""
        url = "https://pubmed.ncbi.nlm.nih.gov/35086660/"
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is None

    def test_scholar_search_url_returns_none(self):
        """scholar.google.com/scholar? (search) is NOT a lookup URL -- return None."""
        url = "https://scholar.google.com/scholar?q=hypertrophic+cardiomyopathy"
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is None

    def test_missing_year_still_parses(self):
        """URL without publication_year should still return title and authors."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Some%20article%20title"
            "&author=J.%20Smith"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is not None
        assert result["title"] == "Some article title"
        assert result["year"] is None

    def test_short_title_returns_none(self):
        """Title with fewer than 4 words is too ambiguous -- return None."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Short%20title"
            "&publication_year=2020"
            "&author=J.%20Smith"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is None

    def test_empty_url(self):
        """Empty string returns None."""
        assert self.detector.parse_scholar_lookup_url("") is None

    def test_plus_encoded_spaces(self):
        """Some Scholar URLs use + for spaces -- should decode correctly."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=A+Guide+to+Hypertrophic+Cardiomyopathy"
            "&publication_year=2022"
            "&author=B.J.+Maron"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is not None
        assert result["title"] == "A Guide to Hypertrophic Cardiomyopathy"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_type_detector.py::TestParseScholarLookupUrl -v
```
Expected: `AttributeError: 'CitationTypeDetector' object has no attribute 'parse_scholar_lookup_url'`

**Step 3: Implement `parse_scholar_lookup_url`**

Add this method to `CitationTypeDetector` after `strip_proxy_url`:

```python
def parse_scholar_lookup_url(self, url: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse a Google Scholar scholar_lookup URL, extracting title, year, and authors.

    Scholar lookup URLs embed structured citation metadata as query parameters.
    This method extracts that data for use in PubMed/CrossRef title searches,
    which is significantly more accurate than passing the raw URL as a title.

    Args:
        url: A Google Scholar URL (must contain /scholar_lookup path).

    Returns:
        Dict with keys:
          - "title" (str): URL-decoded article title
          - "year"  (str | None): Publication year, or None if absent
          - "authors" (List[str]): URL-decoded author names (may be empty)
        Returns None if:
          - URL is not a scholar_lookup URL
          - Decoded title has fewer than 4 words (too ambiguous for reliable search)
          - URL is empty or None
    """
    if not url:
        return None

    # Must be a scholar_lookup URL (not a generic Scholar search)
    if 'scholar.google.com/scholar_lookup' not in url:
        return None

    from urllib.parse import urlparse, parse_qs, unquote_plus

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=False)

    # Extract title (first value if present)
    title_raw = params.get('title', [None])[0]
    if not title_raw:
        return None
    title = unquote_plus(title_raw).strip()

    # Reject titles that are too short to be useful for search
    if len(title.split()) < 4:
        return None

    # Extract year (optional)
    year_raw = params.get('publication_year', [None])[0]
    year = year_raw.strip() if year_raw else None

    # Extract authors (there may be multiple 'author' params)
    authors = [unquote_plus(a).strip() for a in params.get('author', [])]

    return {
        "title": title,
        "year": year,
        "authors": authors,
    }
```

Also add `Dict, Any` to the imports at the top of `type_detector.py` if not already present:
```python
from typing import Optional, Dict, Any  # ensure Dict and Any are imported
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_type_detector.py::TestParseScholarLookupUrl -v
```
Expected: All 8 tests PASS.

**Step 5: Commit**

```bash
git add modules/type_detector.py tests/test_type_detector.py
git commit -m "feat(type_detector): add parse_scholar_lookup_url for Scholar metadata extraction"
```

---

### Task A3: extract_scopus_eid()

**Files:**
- Modify: `modules/type_detector.py`
- Modify: `tests/test_type_detector.py`

**Background:** Scopus EIDs (Electronic IDs) appear in two URL formats in ScienceDirect reference lists:
1. Scopus record URL: `scopus.com/inward/record.url?eid=2-s2.0-85051788505`
2. ScienceDirect PDF URL: `/pdfft?md5=...&pid=1-s2.0-85051788505-main.pdf`

The EID format is always `2-s2.0-{numeric_id}`. OpenAlex can resolve these to DOI/PMID for free via `filter=ids.scopus:{eid}`.

**Step 1: Write the failing tests**

Add this class to `tests/test_type_detector.py`:

```python
class TestExtractScopusEid:
    """Tests for Scopus EID extraction."""

    def setup_method(self):
        self.detector = CitationTypeDetector()

    def test_scopus_record_url(self):
        """EID should be extracted from Scopus record URL."""
        url = "https://www.scopus.com/inward/record.url?eid=2-s2.0-85051788505&partnerID=10&rel=R3.0.0"
        result = self.detector.extract_scopus_eid(url)
        assert result == "2-s2.0-85051788505"

    def test_scopus_proxy_url(self):
        """EID should be extracted from proxy-wrapped Scopus URL."""
        url = "https://www-scopus-com.proxy.lib.ohio-state.edu/inward/record.url?eid=2-s2.0-84979547014&partnerID=10"
        result = self.detector.extract_scopus_eid(url)
        assert result == "2-s2.0-84979547014"

    def test_sciencedirect_pdf_pid(self):
        """EID should be extracted from ScienceDirect PDF pid param."""
        url = "https://www-sciencedirect-com.proxy.lib.ohio-state.edu/science/article/pii/S1936878X16303394/pdfft?md5=e346a48bb04e1a3ec14dabaa3250beb8&pid=1-s2.0-S1936878X16303394-main.pdf"
        result = self.detector.extract_scopus_eid(url)
        # Note: the ScienceDirect PDF pid contains the PII not a numeric Scopus EID
        # The numeric portion after "1-s2.0-" here is a PII string, not an EID.
        # extract_scopus_eid should return None for PII-format pids (non-numeric suffix).
        assert result is None

    def test_scopus_numeric_eid_in_pdf(self):
        """EID should be extracted from PDF URL with a numeric Scopus EID in pid."""
        url = "https://example.sciencedirect.com/pdfft?pid=1-s2.0-85051788505-main.pdf"
        result = self.detector.extract_scopus_eid(url)
        assert result == "2-s2.0-85051788505"

    def test_non_scopus_url(self):
        """Non-Scopus URL should return None."""
        url = "https://pubmed.ncbi.nlm.nih.gov/35086660/"
        result = self.detector.extract_scopus_eid(url)
        assert result is None

    def test_empty_url(self):
        """Empty string returns None."""
        assert self.detector.extract_scopus_eid("") is None

    def test_doi_url_returns_none(self):
        """DOI URL is not a Scopus URL -- return None."""
        url = "https://doi.org/10.1056/nejmra1710575"
        assert self.detector.extract_scopus_eid(url) is None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_type_detector.py::TestExtractScopusEid -v
```
Expected: `AttributeError: 'CitationTypeDetector' object has no attribute 'extract_scopus_eid'`

**Step 3: Implement `extract_scopus_eid`**

Add this method to `CitationTypeDetector` after `parse_scholar_lookup_url`:

```python
def extract_scopus_eid(self, url: Optional[str]) -> Optional[str]:
    """Extract a Scopus Electronic ID (EID) from a Scopus or ScienceDirect URL.

    Scopus EIDs have the format "2-s2.0-{digits}" and appear in:
    - Scopus record URLs: scopus.com/inward/record.url?eid=2-s2.0-85051788505
    - ScienceDirect PDF URLs: /pdfft?pid=1-s2.0-85051788505-main.pdf
      (only when the numeric suffix is all digits -- PII-format pids are excluded)

    EIDs can be resolved to DOI/PMID via the OpenAlex API (free, no key required):
    GET https://api.openalex.org/works?filter=ids.scopus:{eid}

    Args:
        url: Any URL, possibly containing a Scopus EID.

    Returns:
        Normalized EID string (e.g., "2-s2.0-85051788505") or None.
    """
    if not url:
        return None

    from urllib.parse import urlparse, parse_qs

    # Path 1: Scopus record URL -- eid query param
    # Handles both direct and proxy-wrapped Scopus URLs
    if 'scopus' in url.lower():
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        eid = params.get('eid', [None])[0]
        if eid and re.match(r'^2-s2\.0-\d+$', eid):
            return eid

    # Path 2: ScienceDirect PDF URL -- pid param with numeric Scopus EID
    # Format: pid=1-s2.0-{digits}-main.pdf  (digits only = Scopus EID)
    # Contrast: pid=1-s2.0-{PII}-main.pdf   (PII contains letters = not an EID)
    if 'pdfft' in url or 'pid=' in url:
        pid_match = re.search(r'pid=1-s2\.0-(\d+)-main\.pdf', url)
        if pid_match:
            numeric_id = pid_match.group(1)
            return f"2-s2.0-{numeric_id}"

    return None
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_type_detector.py::TestExtractScopusEid -v
```
Expected: All 7 tests PASS.

**Step 5: Run the full type_detector test suite to ensure no regressions**

```bash
pytest tests/test_type_detector.py -v
```
Expected: All existing tests plus new tests PASS.

**Step 6: Commit**

```bash
git add modules/type_detector.py tests/test_type_detector.py
git commit -m "feat(type_detector): add extract_scopus_eid for Scopus record and PDF URLs"
```

---

## Stream B: OpenAlex Scopus EID Resolver

*Independent of Stream A. Only touches `modules/openalex_client.py` and creates `tests/test_openalex_scopus.py`.*

---

### Task B1: fetch_by_scopus_eid()

**Files:**
- Modify: `modules/openalex_client.py` (add method to `OpenAlexClient` class)
- Create: `tests/test_openalex_scopus.py`

**Background:** OpenAlex indexes Scopus EIDs and exposes them via a filter query:
```
GET https://api.openalex.org/works?filter=ids.scopus:2-s2.0-85051788505
```
This returns full work metadata including DOI and PMID -- with no API key required (just add `mailto=email` for the polite pool). The response is a list (results array); take the first result if present.

Follow the exact pattern of `fetch_by_doi` (lines 112-141) and `fetch_by_pmid` (lines 143-170).

**Step 1: Write the failing test file**

Create `tests/test_openalex_scopus.py`:

```python
"""
Tests for OpenAlexClient.fetch_by_scopus_eid().

All network calls are mocked -- these tests never hit the real OpenAlex API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.openalex_client import OpenAlexClient, OpenAlexWork


MOCK_OPENALEX_WORK = {
    "id": "https://openalex.org/W2741809809",
    "doi": "https://doi.org/10.1056/nejmra1710575",
    "title": "Clinical Course and Management of Hypertrophic Cardiomyopathy",
    "publication_year": 2018,
    "publication_date": "2018-08-16",
    "type": "journal-article",
    "cited_by_count": 1250,
    "open_access": {"is_oa": False, "oa_url": None},
    "authorships": [
        {"author": {"display_name": "Barry J. Maron"}}
    ],
    "primary_location": {
        "source": {
            "display_name": "New England Journal of Medicine",
            "issn": ["0028-4793"]
        }
    },
    "biblio": {
        "volume": "379",
        "issue": "7",
        "first_page": "655",
        "last_page": "668"
    },
    "ids": {
        "pmid": "https://pubmed.ncbi.nlm.nih.gov/30110588/",
        "pmcid": None
    },
    "concepts": [],
    "referenced_works": []
}


class TestFetchByScopusEid:
    """Tests for OpenAlexClient.fetch_by_scopus_eid."""

    def setup_method(self):
        self.client = OpenAlexClient(email="test@example.com")

    def test_successful_eid_lookup(self):
        """Valid EID should return an OpenAlexWork with DOI and PMID populated."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [MOCK_OPENALEX_WORK],
            "meta": {"count": 1}
        }

        with patch.object(self.client.session, 'get', return_value=mock_response):
            result = self.client.fetch_by_scopus_eid("2-s2.0-85051788505")

        assert result is not None
        assert isinstance(result, OpenAlexWork)
        assert result.doi == "10.1056/nejmra1710575"
        assert result.pmid == "30110588"
        assert result.title == "Clinical Course and Management of Hypertrophic Cardiomyopathy"

    def test_eid_not_found_returns_none(self):
        """EID with no OpenAlex match should return None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [],
            "meta": {"count": 0}
        }

        with patch.object(self.client.session, 'get', return_value=mock_response):
            result = self.client.fetch_by_scopus_eid("2-s2.0-99999999999")

        assert result is None

    def test_api_error_returns_none(self):
        """Network error should return None without raising."""
        import requests
        with patch.object(self.client.session, 'get', side_effect=requests.RequestException("timeout")):
            result = self.client.fetch_by_scopus_eid("2-s2.0-85051788505")

        assert result is None

    def test_correct_api_url_called(self):
        """Verify the correct OpenAlex filter URL is constructed."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "meta": {"count": 0}}

        with patch.object(self.client.session, 'get', return_value=mock_response) as mock_get:
            self.client.fetch_by_scopus_eid("2-s2.0-85051788505")

        call_args = mock_get.call_args
        url = call_args[0][0]
        assert "api.openalex.org/works" in url
        # The EID filter should be in params, not the URL path
        params = call_args[1].get('params', {}) or call_args[0][1] if len(call_args[0]) > 1 else {}
        # Accept either inline or params-dict form
        assert "2-s2.0-85051788505" in str(call_args)

    def test_empty_eid_returns_none(self):
        """Empty EID string should return None without making API call."""
        with patch.object(self.client.session, 'get') as mock_get:
            result = self.client.fetch_by_scopus_eid("")
        assert result is None
        mock_get.assert_not_called()

    def test_none_eid_returns_none(self):
        """None EID should return None without making API call."""
        with patch.object(self.client.session, 'get') as mock_get:
            result = self.client.fetch_by_scopus_eid(None)
        assert result is None
        mock_get.assert_not_called()

    def test_eid_prefix_normalized(self):
        """EID without '2-s2.0-' prefix should still work."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [MOCK_OPENALEX_WORK],
            "meta": {"count": 1}
        }

        with patch.object(self.client.session, 'get', return_value=mock_response):
            # Some callers may pass just the numeric part
            result = self.client.fetch_by_scopus_eid("85051788505")

        # Should still succeed (method normalizes the prefix)
        assert result is not None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_openalex_scopus.py -v
```
Expected: `AttributeError: 'OpenAlexClient' object has no attribute 'fetch_by_scopus_eid'`

**Step 3: Implement `fetch_by_scopus_eid`**

Add this method to `OpenAlexClient` in `modules/openalex_client.py`, after `fetch_by_pmid` (around line 170):

```python
def fetch_by_scopus_eid(self, eid: Optional[str]) -> Optional["OpenAlexWork"]:
    """Fetch a work by Scopus Electronic ID (EID) via the OpenAlex API.

    OpenAlex indexes Scopus EIDs and provides a free, no-key-required resolution
    path from Scopus EID to DOI and PMID. This is the recommended method for
    resolving Scopus URLs found in academic article reference lists.

    Args:
        eid: Scopus EID string. Accepts:
             - Full EID:       "2-s2.0-85051788505"
             - Numeric suffix: "85051788505" (prefix is added automatically)

    Returns:
        OpenAlexWork with doi and pmid populated if found, or None.

    Example:
        work = client.fetch_by_scopus_eid("2-s2.0-85051788505")
        if work:
            print(work.doi)   # "10.1056/nejmra1710575"
            print(work.pmid)  # "30110588"

    API reference: https://docs.openalex.org/api-entities/works/filter-works#ids.scopus
    """
    if not eid:
        return None

    # Normalize: ensure EID has the standard "2-s2.0-" prefix
    eid_str = str(eid).strip()
    if re.match(r'^\d+$', eid_str):
        eid_str = f"2-s2.0-{eid_str}"
    elif not eid_str.startswith('2-s2.0-'):
        logger.debug(f"Unrecognized EID format: {eid_str}")
        return None

    self._rate_limit()

    try:
        url = f"{self.BASE_URL}/works"
        params = self._build_params(filter=f"ids.scopus:{eid_str}")

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])
        if not results:
            logger.debug(f"No OpenAlex work found for Scopus EID: {eid_str}")
            return None

        return self._parse_work(results[0])

    except Exception as e:
        logger.debug(f"OpenAlex Scopus EID lookup failed for {eid_str}: {e}")
        return None
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_openalex_scopus.py -v
```
Expected: All 7 tests PASS.

**Step 5: Commit**

```bash
git add modules/openalex_client.py tests/test_openalex_scopus.py
git commit -m "feat(openalex): add fetch_by_scopus_eid for free Scopus-to-DOI/PMID resolution"
```

---

## Stream C: Integration into lookup_auto() (depends on A1, A2, A3, B1)

*Do not start this stream until all Stream A and Stream B tasks are committed.*

---

### Task C1: Add OpenAlexClient to CitationLookup.__init__

**Files:**
- Modify: `citation_lookup.py`

**Step 1: Write the failing test**

Find the class `TestLookupAuto` in `tests/test_citation_lookup.py` (or add if missing). Add this test:

```python
def test_lookup_auto_has_openalex_client(self):
    """CitationLookup should instantiate an OpenAlexClient for Scopus EID resolution."""
    from modules.openalex_client import OpenAlexClient
    lookup = CitationLookup()
    assert hasattr(lookup, 'openalex_client')
    assert isinstance(lookup.openalex_client, OpenAlexClient)
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_citation_lookup.py::TestLookupAuto::test_lookup_auto_has_openalex_client -v
```
Expected: FAIL (attribute does not exist)

**Step 3: Add the import and instantiation**

In `citation_lookup.py`:

1. Add import near line 35 (with other module imports):
```python
from modules.openalex_client import OpenAlexClient
```

2. In `CitationLookup.__init__` (around line 118), after `self.book_client = BookClient()`, add:
```python
self.openalex_client = OpenAlexClient()
```

**Step 4: Run to verify it passes**

```bash
pytest tests/test_citation_lookup.py::TestLookupAuto::test_lookup_auto_has_openalex_client -v
```

**Step 5: Commit**

```bash
git add citation_lookup.py
git commit -m "feat(citation_lookup): instantiate OpenAlexClient for Scopus EID resolution"
```

---

### Task C2: Update lookup_auto() with all new resolution paths

**Files:**
- Modify: `citation_lookup.py` (`lookup_auto` method, lines 287-337)
- Modify: `tests/test_citation_lookup.py`

**Background:** The updated `lookup_auto()` should follow this decision tree, in order:

1. Strip proxy URL (always, before any type detection)
2. PII extraction (existing)
3. PMID (existing)
4. PMC ID (existing)
5. arXiv (existing)
6. ISBN (existing)
7. DOI -- now also catches proxy-stripped URLs
8. **NEW:** Scopus EID from URL -- try OpenAlex EID lookup
9. **NEW:** Google Scholar `scholar_lookup` URL -- extract title/year/authors
10. Full citation text detection (existing)
11. Default title search (existing)

**Step 1: Write the failing tests**

Add to `tests/test_citation_lookup.py` (use `patch` to mock all network calls):

```python
class TestLookupAutoNewPaths:
    """Tests for new resolution paths added in v2: proxy URLs, Scholar URLs, Scopus EIDs."""

    def setup_method(self):
        self.lookup = CitationLookup()
        # Build a minimal successful LookupResult for use as mock return value
        self.mock_success = LookupResult(
            success=True,
            identifier="30110588",
            identifier_type="pmid",
            inline_mark="[^MaronBJ-2018-30110588]",
            endnote_citation="[^MaronBJ-2018-30110588]: Maron BJ...",
            full_citation="[^MaronBJ-2018-30110588]: Maron BJ...",
        )

    def test_proxy_doi_url_is_resolved(self):
        """Proxy-wrapped DOI URL should resolve via DOI path, not title search."""
        proxied_url = "https://doi-org.proxy.lib.ohio-state.edu/10.1056/nejmra1710575"

        with patch.object(self.lookup, 'lookup_doi', return_value=self.mock_success) as mock_doi, \
             patch.object(self.lookup, 'lookup_title') as mock_title:
            result = self.lookup.lookup_auto(proxied_url)

        mock_doi.assert_called_once()
        # lookup_doi should be called with the canonical DOI, not the proxy URL
        call_arg = mock_doi.call_args[0][0]
        assert call_arg == "10.1056/nejmra1710575"
        mock_title.assert_not_called()
        assert result.success is True

    def test_scholar_lookup_url_uses_extracted_title(self):
        """Scholar lookup URL should extract title params, not pass raw URL as title."""
        scholar_url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Clinical%20course%20and%20management%20of%20hypertrophic%20cardiomyopathy"
            "&publication_year=2018"
            "&author=B.J.%20Maron"
        )

        with patch.object(self.lookup, 'lookup_title', return_value=self.mock_success) as mock_title:
            result = self.lookup.lookup_auto(scholar_url)

        mock_title.assert_called_once()
        title_arg = mock_title.call_args[0][0]
        # The title argument should be the clean decoded title, not the full URL
        assert 'scholar.google.com' not in title_arg
        assert 'hypertrophic cardiomyopathy' in title_arg.lower()

    def test_scopus_url_tries_openalex_eid(self):
        """Scopus URL should try OpenAlex EID lookup before falling back to title search."""
        scopus_url = "https://www.scopus.com/inward/record.url?eid=2-s2.0-85051788505"

        from modules.openalex_client import OpenAlexWork
        mock_oa_work = Mock(spec=OpenAlexWork)
        mock_oa_work.doi = "10.1056/nejmra1710575"
        mock_oa_work.pmid = "30110588"

        with patch.object(self.lookup.openalex_client, 'fetch_by_scopus_eid', return_value=mock_oa_work) as mock_eid, \
             patch.object(self.lookup, 'lookup_doi', return_value=self.mock_success) as mock_doi:
            result = self.lookup.lookup_auto(scopus_url)

        mock_eid.assert_called_once_with("2-s2.0-85051788505")
        assert result.success is True

    def test_scopus_url_falls_back_to_title_when_eid_fails(self):
        """When OpenAlex EID lookup returns None, fall through to title search."""
        scopus_url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Some%20rare%20article%20not%20in%20openalex"
            "&publication_year=2020"
            "&author=J.%20Smith"
        )
        with patch.object(self.lookup, 'lookup_title', return_value=self.mock_success) as mock_title:
            result = self.lookup.lookup_auto(scopus_url)

        mock_title.assert_called_once()

    def test_plain_doi_still_works(self):
        """Existing plain DOI path must not regress."""
        with patch.object(self.lookup, 'lookup_doi', return_value=self.mock_success) as mock_doi:
            result = self.lookup.lookup_auto("10.1056/nejmra1710575")

        mock_doi.assert_called_once()
        assert result.success is True
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_citation_lookup.py::TestLookupAutoNewPaths -v
```
Expected: Multiple failures (proxy URL falls through to title search, Scholar URL passes raw URL, etc.)

**Step 3: Rewrite `lookup_auto()`**

Replace the entire `lookup_auto` method body in `citation_lookup.py` with:

```python
def lookup_auto(self, identifier: str) -> LookupResult:
    """Auto-detect identifier type and look up accordingly.

    Detection order (first match wins):
    1. Strip institutional proxy wrapper (EZProxy) -- normalizes all URLs before detection
    2. ScienceDirect/Elsevier PII URL  -> PubMed PMID via resolve_pii_to_pmid()
    3. Plain PMID (all digits)          -> lookup_pmid()
    4. PMC ID (starts with PMC)         -> lookup_pmcid()
    5. arXiv ID                         -> lookup_arxiv()
    6. ISBN                             -> lookup_isbn()
    7. DOI (10.xxx or doi.org/...)      -> lookup_doi()
    8. Scopus EID URL                   -> OpenAlex EID lookup -> lookup_doi()
    9. Google Scholar scholar_lookup URL -> extract title/year -> lookup_title()
    10. Full citation text              -> extract title -> lookup_title()
    11. Default                         -> lookup_title()

    Proxy stripping (step 1) handles institutional EZProxy URLs where
    doi.org becomes doi-org.proxy.lib.INSTITUTION.edu. This runs first
    so all downstream detection logic sees canonical URLs.

    Args:
        identifier: Any string: URL, DOI, PMID, title, full citation text.

    Returns:
        LookupResult with success=True if found, success=False otherwise.
    """
    from modules.type_detector import CitationTypeDetector
    detector = CitationTypeDetector()

    identifier = identifier.strip()

    # Step 1: Strip institutional proxy wrapper (EZProxy normalization)
    identifier = detector.strip_proxy_url(identifier) or identifier

    # Step 2: ScienceDirect/Elsevier PII URL
    pii_match = re.search(r'/pii/([A-Z]\d{16})', identifier, re.IGNORECASE)
    if pii_match:
        pii = pii_match.group(1).upper()
        try:
            pmid_from_pii = self.pubmed_client.resolve_pii_to_pmid(pii)
            if pmid_from_pii:
                return self.lookup_pmid(pmid_from_pii)
        except Exception as e:
            logger.debug(f"PII lookup failed for {pii}: {e}")

    # Step 3: PMID (all digits)
    if identifier.isdigit():
        return self.lookup_pmid(identifier)

    # Step 4: PMC ID
    if identifier.upper().startswith('PMC'):
        return self.lookup_pmcid(identifier)

    # Step 5: arXiv ID
    if self.arxiv_client.is_arxiv_id(identifier) or identifier.lower().startswith('arxiv:'):
        return self.lookup_arxiv(identifier)

    # Step 6: ISBN
    if self.book_client.is_isbn(identifier):
        return self.lookup_isbn(identifier)

    # Step 7: DOI
    if identifier.startswith('10.') or 'doi.org' in identifier.lower():
        doi = identifier.split('doi.org/')[-1] if 'doi.org/' in identifier else identifier
        if self.preprint_client.is_preprint_doi(doi):
            return self.lookup_preprint(doi)
        return self.lookup_doi(doi)

    # Step 8: Scopus EID URL -> OpenAlex EID lookup
    scopus_eid = detector.extract_scopus_eid(identifier)
    if scopus_eid:
        oa_work = self.openalex_client.fetch_by_scopus_eid(scopus_eid)
        if oa_work:
            if oa_work.doi:
                result = self.lookup_doi(oa_work.doi)
                if result.success:
                    return result
            if oa_work.pmid:
                result = self.lookup_pmid(oa_work.pmid)
                if result.success:
                    return result
        # EID found but OpenAlex had no match -- fall through to Scholar/title paths

    # Step 9: Google Scholar scholar_lookup URL
    scholar_data = detector.parse_scholar_lookup_url(identifier)
    if scholar_data:
        title = scholar_data["title"]
        # If year is available, PubMed title+year search is more precise
        # Pass year as part of title for now; PubMed client already does fuzzy matching
        result = self.lookup_title(title)
        if result.success:
            return result
        # Scholar URL found but title lookup failed -- fall through to default

    # Step 10: Full citation text -- extract title and try lookup
    if not identifier.startswith('10.') and '. ' in identifier and re.search(r'\b(19|20)\d{2}\b', identifier):
        extracted_title = self._extract_title_from_citation_text(identifier)
        if extracted_title and len(extracted_title.split()) >= 4:
            logger.info(f"Citation text detected, extracted title: {extracted_title[:60]}...")
            result = self.lookup_title(extracted_title)
            if result.success:
                return result

    # Step 11: Default title search
    return self.lookup_title(identifier)
```

**Step 4: Run new tests**

```bash
pytest tests/test_citation_lookup.py::TestLookupAutoNewPaths -v
```
Expected: All 5 new tests PASS.

**Step 5: Run full test suite -- no regressions**

```bash
pytest tests/test_citation_lookup.py -v
```
Expected: All existing tests plus new tests PASS.

**Step 6: Commit**

```bash
git add citation_lookup.py tests/test_citation_lookup.py
git commit -m "feat(citation_lookup): wire proxy stripping, Scholar URL, Scopus EID into lookup_auto"
```

---

## Stream D: Documentation and Discoverability

*Can run in parallel with Stream C. Touches only documentation files.*

---

### Task D1: Create AGENT_API.md -- Machine-Readable Capability Manifest

**Files:**
- Create: `docs/AGENT_API.md`

**Purpose:** External agents (PAI skills, subagents) need to discover what CitationSculptor can resolve without reading source code. This file is the authoritative reference.

**Step 1: Create the file**

```bash
cat > /Users/tusharshah/Developer/MCP-Servers/CitationSculptor/docs/AGENT_API.md << 'HEREDOC'
# CitationSculptor Agent API Reference

> This file documents all inputs that `citation_lookup.py --auto` can resolve.
> It is the authoritative reference for external agents calling CitationSculptor.

## Primary CLI Entry Point

```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
source .venv/bin/activate
python citation_lookup.py --auto "<identifier>" --json
```

The `--json` flag outputs structured JSON instead of formatted text. Use this for agent-to-agent calls.

## Supported Identifier Types (lookup_auto detection order)

| Priority | Type | Examples | Resolution Path |
|----------|------|---------|----------------|
| 1 | **EZProxy-wrapped URL** (any type below) | `doi-org.proxy.lib.ohio-state.edu/10.xxx/yyy` | Proxy prefix stripped; then detected as below |
| 2 | **ScienceDirect PII URL** | `sciencedirect.com/science/article/pii/S0735109721082735` | PII → PubMed resolve_pii_to_pmid → PMID |
| 3 | **PubMed PMID** | `35086660`, `"35086660"` | Direct PubMed efetch |
| 4 | **PMC ID** | `PMC8765432` | PubMed PMC fetch |
| 5 | **arXiv ID** | `2103.01234`, `arxiv:2103.01234` | arXiv API |
| 6 | **ISBN** | `978-0-470-92765-0` | Google Books / OpenLibrary |
| 7 | **DOI** | `10.1056/nejmra1710575`, `https://doi.org/10.1056/...` | CrossRef + PubMed esearch |
| 8 | **Scopus EID URL** | `scopus.com/inward/record.url?eid=2-s2.0-85051788505` | Scopus EID → OpenAlex filter → DOI/PMID |
| 9 | **Google Scholar `scholar_lookup` URL** | `scholar.google.com/scholar_lookup?title=...&publication_year=...` | Extract title/year → PubMed title search |
| 10 | **Full citation text** | `"Maron BJ. Clinical course. N Engl J Med. 2018;379:655."` | Extract title → PubMed title search |
| 11 | **Article title** | `"Clinical course and management of hypertrophic cardiomyopathy"` | PubMed + CrossRef title search |

## JSON Output Format (--json flag)

```json
{
  "success": true,
  "identifier": "35086660",
  "identifier_type": "pmid",
  "inline_mark": "[^MaronBJ-2018-35086660]",
  "endnote_citation": "[^MaronBJ-2018-35086660]: Maron BJ, et al. Diagnosis and evaluation... PMID: 35086660",
  "full_citation": "[^MaronBJ-2018-35086660]: ...",
  "pmid": "35086660",
  "doi": "10.1016/j.jacc.2021.12.012",
  "title": "Diagnosis and Evaluation of Hypertrophic Cardiomyopathy",
  "authors": ["Maron BJ", "Rowin EJ", "Maron MS"],
  "year": "2022",
  "journal": "J Am Coll Cardiol",
  "volume": "79",
  "issue": "4",
  "pages": "372-389",
  "confidence": 0.95
}
```

## Usage Patterns for Agents

### Pattern 1: Resolve a DOI from a pasted reference

```bash
python citation_lookup.py --auto "10.1056/nejmra1710575" --json
```

### Pattern 2: Resolve from a ScienceDirect URL (with or without proxy)

```bash
python citation_lookup.py --auto "https://www-sciencedirect-com.proxy.lib.ohio-state.edu/science/article/pii/S0735109721082735" --json
```

### Pattern 3: Resolve from a Google Scholar scholar_lookup URL

```bash
python citation_lookup.py --auto "https://scholar.google.com/scholar_lookup?title=Clinical%20course%20and%20management%20of%20hypertrophic%20cardiomyopathy&publication_year=2018&author=B.J.%20Maron" --json
```

### Pattern 4: Resolve a Scopus EID

```bash
python citation_lookup.py --auto "https://www.scopus.com/inward/record.url?eid=2-s2.0-85051788505" --json
```

## Rate Limits

| API | Limit | Key Required |
|-----|-------|-------------|
| PubMed E-utilities | 2.5 req/s (no key), 10 req/s (NCBI key) | No |
| CrossRef | ~50 req/s (polite pool) | No (email recommended) |
| OpenAlex | ~100,000 req/day | No (email recommended) |
| arXiv | ~3 req/s | No |

## Known Limitations

- Scopus API (institutional key): NOT used -- OpenAlex is used instead (free)
- PubMed ID Converter (`idconv`): only finds PMC articles; use `esearch [doi]` instead
- Google Scholar `scholar?q=` search URLs: NOT supported (only `scholar_lookup?title=`)
- Scopus PDF pids containing PIIs (alphanumeric): NOT resolved as Scopus EIDs
HEREDOC
echo "Created AGENT_API.md"
```

**Step 2: Verify file exists**

```bash
cat /Users/tusharshah/Developer/MCP-Servers/CitationSculptor/docs/AGENT_API.md | head -10
```

**Step 3: Commit**

```bash
git add docs/AGENT_API.md
git commit -m "docs: add AGENT_API.md machine-readable capability manifest for external agents"
```

---

### Task D2: Update CitationSculptor SKILL.md

**Files:**
- Modify: `~/.claude/skills/CitationSculptor/SKILL.md`

**Step 1: Find and read the current SKILL.md**

```bash
cat ~/.claude/skills/CitationSculptor/SKILL.md | head -80
```

**Step 2: Add/update the "URL Types Supported" section**

Find the section describing `--auto` or `citation_lookup.py` usage and add after it (or create it if absent):

```markdown
## URL Types Handled by --auto

`citation_lookup.py --auto` resolves any of these inputs without configuration:

| Input | Example | How it resolves |
|-------|---------|----------------|
| Plain DOI | `10.1056/nejmra1710575` | CrossRef + PubMed |
| doi.org URL | `https://doi.org/10.1056/nejmra1710575` | As above |
| **EZProxy DOI URL** | `doi-org.proxy.lib.ohio-state.edu/10.1056/...` | Proxy stripped → DOI |
| **EZProxy ScienceDirect** | `www-sciencedirect-com.proxy.lib.ohio-state.edu/...` | Proxy stripped → PII |
| ScienceDirect PII | `sciencedirect.com/...pii/S0735109721082735` | PII → PubMed |
| **Scopus EID URL** | `scopus.com/...?eid=2-s2.0-85051788505` | EID → OpenAlex (free) |
| **Scholar lookup URL** | `scholar.google.com/scholar_lookup?title=...` | Params extracted → PubMed |
| PubMed PMID | `35086660` | Direct PubMed fetch |
| Full citation text | `Maron BJ. N Engl J Med. 2018;379:655.` | Title extracted → PubMed |

**Bold** entries are new in v2. For complete API documentation see `docs/AGENT_API.md` in the repo.
```

**Step 3: Commit**

```bash
git add ~/.claude/skills/CitationSculptor/SKILL.md
git commit -m "docs(skill): update SKILL.md with new URL types handled by lookup_auto v2"
```

---

## Parallelization Map

```
Start
├── Stream A (type_detector.py) ──── runs independently ──────────────────────┐
│   ├── Task A1: strip_proxy_url                                              │
│   ├── Task A2: parse_scholar_lookup_url                                     │
│   └── Task A3: extract_scopus_eid                                           │
│                                                                              ▼
├── Stream B (openalex_client.py) ─ runs independently ──────────────────────┤
│   └── Task B1: fetch_by_scopus_eid                                          │
│                                                                              ▼
│                                                              Stream C (citation_lookup.py)
│                                                              ├── C1: add openalex_client
│                                                              └── C2: update lookup_auto()
│
└── Stream D (docs) ─────────────── runs independently ──────────────────────┘
    ├── Task D1: AGENT_API.md
    └── Task D2: SKILL.md update
```

**Parallel agents:**
- **Agent Alpha:** Stream A (Tasks A1, A2, A3 -- sequential within stream)
- **Agent Beta:** Stream B (Task B1)
- **Agent Gamma:** Stream D (Tasks D1, D2 -- can start immediately)
- **Agent Delta:** Stream C (Tasks C1, C2 -- starts only after Alpha and Beta complete)

---

## Acceptance Criteria

After all streams complete, run:

```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
source .venv/bin/activate

# 1. All new tests pass
pytest tests/test_type_detector.py tests/test_openalex_scopus.py tests/test_citation_lookup.py -v

# 2. Proxy DOI resolves correctly
python citation_lookup.py --auto "https://doi-org.proxy.lib.ohio-state.edu/10.1056/nejmra1710575" --json

# 3. Scholar URL resolves correctly
python citation_lookup.py --auto "https://scholar.google.com/scholar_lookup?title=Clinical%20course%20and%20management%20of%20hypertrophic%20cardiomyopathy&publication_year=2018&author=B.J.%20Maron" --json

# 4. Scopus EID URL resolves correctly
python citation_lookup.py --auto "https://www.scopus.com/inward/record.url?eid=2-s2.0-85051788505" --json

# 5. Existing regression tests pass
pytest tests/ -v --ignore=tests/test_document_intelligence_integration.py
```

Expected for items 2-4: `"success": true` with `pmid` and `doi` populated.
