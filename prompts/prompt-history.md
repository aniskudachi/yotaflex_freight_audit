# Prompt History & Developmental Evolution

This file preserves the prompt log and developmental progression of the Freight Invoice Validation & Audit project.

---

## Initial Brief
Validate freight invoices against contracted rates, shipment characteristics, accessorials, and delivery records. Build an end-to-end working solution with master data, dependent events, 3-way matching business logic, immutable event history, separate ground truth, SQLite persistence, and measurable evaluation outputs.

---

## Candidate Review Log

### Phase 1: Architectural Assessment & Master Schema
- **Prompt:** Review existing repository structure, identify gaps against requirements (11 core entities, granular data dictionary, duplicate billing, dimensional weight divisor, expired rate cards, excess credit notes).
- **Accepted Changes:** Added comprehensive data dictionary in `docs/data_dictionary.md` specifying types, nullability, enums, units, uniqueness, and validation rules for all 11 entities.
- **Validation:** Inspected file and verified schema coverage against project specifications.

### Phase 2: High-Performance Generator & Edge Case Injection
- **Prompt:** Upgrade `src/generate_data.py` to support O(1) indexed rate card lookups, generate all 11 core tables + audit event history + ground truth, create explicit expired rate cards in `rate_card.csv`, and inject all 7 required negative scenarios (`UNKNOWN_SHIPMENT`, `EXPIRED_RATE_CARD`, `WEIGHT_TIER_MISMATCH`, `DUPLICATE_SURCHARGE`, `INVALID_ACCESSORIAL`, `DUPLICATE_INVOICE`, `EXCESS_CREDIT`).
- **Validation:** Benchmarked `--scale starter` (0.4s) and `--scale full` (3.9s for 100 carriers, 20,000 shipments, 15,000 invoices). Verified bitwise identical SHA-256 digests across dual runs with seed `20261022`.

### Phase 3: Rule-Based Audit Engine & Ground Truth Isolation
- **Prompt:** Enhance `src/audit_invoices.py` to perform rigorous 3-way matching, dimensional weight calculation verification, weight tier verification, duplicate detection, unapproved accessorial flagging, credit note auditing, and compute precision/recall/confusion matrix against ground truth without data leakage.
- **Validation:** Executed audit engine, verifying 100% precision, 100% recall, 0 false positives, and 100% detection rate across all 7 anomaly taxonomies.

### Phase 4: Validation Suite, SQLite, and SQL Export
- **Prompt:** Upgrade `src/validate_data.py` to test all 40 integrity rules (PK uniqueness, FK referential integrity, enums, date ordering, arithmetic reconciliation). Upgrade `src/load_sqlite.py` and build `src/export_sql.py`.
- **Validation:** Ran validator (40/40 checks passed), loaded 16 tables into SQLite database, and verified standalone SQL seed script.

### Phase 5: Interactive Web Dashboard & Test Automation
- **Prompt:** Build modern glassmorphic web dashboard with dark mode, interactive 360-degree trace drawer, role switcher, dispute actions, confusion matrix viewer, and standard library test suite in `tests/test_audit.py`.
- **Validation:** Ran `python -m unittest discover tests` passing all 7 tests. Tested HTTP server endpoints returning 200 OK.
