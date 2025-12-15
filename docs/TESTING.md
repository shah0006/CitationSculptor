# Testing Guide

## Running Unit Tests

```bash
cd "/Users/tusharshah/Main Obsidian (Sync)/20 - Projects/Inactive Projects/Software Projects/CitationSculptor"
source venv/bin/activate

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_pubmed_client.py -v

# Run with coverage
python -m pytest tests/ --cov=modules --cov-report=html
```

## Test Files

| File | Coverage |
|------|----------|
| `test_pubmed_client.py` | API client, caching, rate limiting, CrossRef, scraping |
| `test_vancouver_formatter.py` | All citation formats, helper methods |
| `test_reference_parser.py` | V1-V8 formats, multi-section parsing |
| `test_type_detector.py` | Citation type detection |
| `test_inline_replacer.py` | Reference replacement |

**Total: 166 tests**

## Regression Testing

### Test Samples
Located in `test_samples/` folder:

| File | Format | Status |
|------|--------|--------|
| `Right Ventricular Dilation...md` | V2 Extended + Multi-Section | ✅ PASS |
| `Gene Therapy Approaches...md` | V3 Footnotes (DOI links) | ✅ PASS |
| `Arrhythmogenic Cardiomyopathies - Genetics.md` | V3 Footnotes (body after refs) | ✅ PASS |
| `Future Healthcare Delivery Models...md` | V6 Grouped Footnotes | ✅ PASS |

### Smoke Tests

```bash
# Dry-run test files
python citation_sculptor.py "test_samples/Right Ventricular Dilation...md" --multi-section --dry-run
python citation_sculptor.py "test_samples/Gene Therapy Approaches...md" --multi-section --dry-run
python citation_sculptor.py "test_samples/Arrhythmogenic Cardiomyopathies - Genetics.md" --multi-section --dry-run
```

## Known Test Issues

- `pelican_bay...md` is processed output, not original input (need original)

