# Open Source Compliance Report

Audit date: 2026-04-15 (UTC)  
Repository: `frenzymath/Aria-autoformalizer`

## Scope

- Repository structure and legal files
- Direct third-party dependencies inferred from source imports
- Potential disclosure of internal endpoints or credentials
- Distribution hygiene items relevant to open-source release

## Findings (ordered by severity)

### Critical

No unresolved critical findings.

1. Missing top-level open-source license
   - Status: fixed.
   - Changes: added top-level `LICENSE` as `Apache-2.0`.

### High

No unresolved high findings.

1. Internal infrastructure endpoints were committed in tracked config/code
   - Status: fixed.
   - Changes:
     - Replaced endpoint values in `Aria-autoformalizer/configs/config.yaml` and `Aria-autoformalizer/configs/leansearch.yaml` with localhost placeholders.
     - Replaced hardcoded verifier URL in `Aria-autoformalizer/src/tools.py` with config/env resolution (`ARIA_VERIFY_URL` > config > localhost fallback).

2. Compiled artifacts were tracked in git (`.pyc`)
   - Status: fixed.
   - Changes:
     - Removed 23 tracked `.pyc` files from git index.
     - Existing `.gitignore` patterns (`*.pyc`, `__pycache__/`) remain in place.

### Medium

1. No dependency manifest was present in either Python subproject
   - Status: fixed in this audit.
   - Changes:
     - Added `Aria-autoformalizer/requirements.txt`
     - Added `AriaScorer/requirements.txt`
   - Remaining action: pin/review production versions before release.

2. Third-party attribution inventory was missing
   - Status: fixed in this audit.
   - Changes:
     - Added `THIRD_PARTY_NOTICES.md`
   - Remaining action: include full license texts as required by chosen distribution channel.

### Low

1. Unused imports added compliance surface area
   - Status: fixed in this audit.
   - Changes:
     - Removed unused `Levenshtein` and `xlsxwriter` imports from `Aria-autoformalizer/src/tools.py`
     - Removed unused `requests` import from `Aria-autoformalizer/src/LeanSearch/client.py`

## Recommended release gate (must pass)

1. Verify and freeze dependency versions for release.
2. Confirm third-party notices and required license text distribution.
3. Verify provenance and required attribution for `Aria-autoformalizer/src/PocketFlow.py`.
