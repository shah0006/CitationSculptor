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
