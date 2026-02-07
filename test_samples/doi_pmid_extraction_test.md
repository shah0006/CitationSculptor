# Test Document for DOI/PMID Extraction Enhancement

This document tests the new DOI/PMID extraction feature that should eliminate most manual review requirements.

## Test Cases

### Case 1: PMID in text (no URL)
Some text about cardiovascular disease [1].

### Case 2: DOI in text (no URL)
Another study on heart failure [2].

### Case 3: Both DOI and PMID in text
A comprehensive review of the topic [3].

### Case 4: PMID with URL (should use text-based PMID)
More research findings [4].

### Case 5: Title-only (fallback to title search)
Traditional reference without identifiers [5].

## References

1. Li Y, Ilyas I, et al. Standardized cardiovascular magnetic resonance imaging in clinical trials. Circulation. 2018. PMID: 29712712
2. Shah T, et al. Effects of aspirin on cardiovascular events. Lancet. 2018. DOI: 10.1016/S0140-6736(18)31133-4
3. Packer M, et al. Cardiovascular and renal outcomes with empagliflozin. NEJM. 2020. PMID: 32865377 DOI: 10.1056/NEJMoa2022190
4. Antithrombotic Trialists Collaboration. Collaborative meta-analysis. BMJ. 2002. PMID: 11786451 URL: https://example.com/wrong-url
5. Smith J, et al. Traditional citation format without any identifiers. Journal of Medicine. 2021;45(3):123-145.
