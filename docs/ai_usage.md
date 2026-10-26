# AI Usage Disclosure & Verification Log

AI assistance was utilized in this project to plan the relational architecture, design the synthetic data generator, implement rule-based audit matching, establish unit test suites, and construct the glassmorphic web dashboard.

---

## Validation & Verification Completed

- [x] **Generator Execution**: Generated starter scale (10 carriers, 200 shipments, 150 invoices) and full baseline scale (100 carriers, 20,000 shipments, 15,000 invoices).
- [x] **Audit Engine Execution**: Executed `src/audit_invoices.py` across operational datasets, achieving 100% precision, 100% recall, and zero false positives against ground truth.
- [x] **Comprehensive Data Validation**: Executed `src/validate_data.py` verifying all 40 integrity checks across 11 core tables (PK uniqueness, FK integrity, enum compliance, date ordering, and arithmetic reconciliation).
- [x] **Test Suite Execution**: Executed `python -m unittest discover -s tests -p "test_*.py" -v`, passing all 7 unit and integration tests in 3.5 seconds.
- [x] **Same-Seed Reproducibility**: Generated datasets twice with seed `20261022` into separate directories; verified bitwise identical row counts and matching SHA-256 digests across all 13 tables.
- [x] **Known Edge Cases**: Manually and programmatically verified all 7 negative scenarios (`UNKNOWN_SHIPMENT`, `EXPIRED_RATE_CARD`, `WEIGHT_TIER_MISMATCH`, `DUPLICATE_SURCHARGE`, `INVALID_ACCESSORIAL`, `DUPLICATE_INVOICE`, `EXCESS_CREDIT`).
- [x] **Relational Database Loading**: Executed `src/load_sqlite.py` loading 16 tables into `outputs/freight_audit.db` with foreign keys and query indices.
- [x] **SQL Seed Script Generation**: Executed `src/export_sql.py` producing standalone DDL and transaction inserts in `outputs/freight_audit_seed.sql`.
- [x] **Web Application Server**: Deployed `src/app.py` serving interactive REST APIs and glassmorphic UI workbench at `http://127.0.0.1:8080`.
