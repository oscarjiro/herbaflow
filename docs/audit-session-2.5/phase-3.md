# Phase 3: Frontend Bugs

## T3.1 — Disease Display Name Formatting
**Root cause**: `formatDiseaseName` only preserved already-uppercase words. DB stores some
disease names in lowercase (e.g. `copd`, `masld`). Added known-acronym lookup to uppercase
recognized medical acronyms before title-casing.
**ETL note**: Root fix is to canonicalize disease names in the ETL pipeline. Deferred.
