# Design Decisions, Trade-Offs & Data Provenance

## 1. Architectural Decisions & Rationale

### 1.1 Pure Standard Library Implementation
- **Decision:** Build the entire data generation, audit engine, validation suite, and web application using Python 3.10+ standard library without mandatory third-party dependencies (`csv`, `hashlib`, `json`, `sqlite3`, `http.server`, `unittest`).
- **Rationale:** Ensures zero deployment friction, immunity to dependency rot, instant startup, and reproducibility on any machine without complex environment setup. `pytest` remains supported as an optional test runner.

### 1.2 O(1) Vector-Indexed Tariff Rating
- **Decision:** Cache rate cards in an in-memory dictionary keyed by `(carrier_id, lane_id, service, tier_idx)` during high-volume generation.
- **Rationale:** Naive list comprehension across 48,000 rate cards for 20,000 shipments takes over 45 seconds of inner-loop evaluations ($9.6 \times 10^8$ operations). Indexed dictionary lookups complete generation in under 4 seconds.

### 1.3 Out-of-Band Ground Truth Isolation
- **Decision:** Generate `ground_truth.csv` and `ground_truth.json` strictly as isolated evaluation artifacts. The audit engine (`src/audit_invoices.py`) never loads or references ground truth during rule evaluation.
- **Rationale:** Prevents data leakage and ensures the audit engine evaluates invoices strictly based on operational data (rate cards, shipment physical characteristics, accessorial approvals, and delivery records). Ground truth is loaded only post-audit for calculating precision, recall, and confusion matrix metrics.

### 1.4 Immutable Event Sourcing (`audit_event_history.csv`)
- **Decision:** Record every state transition (`RECEIVED -> AUDITED -> DISPUTED -> APPROVED -> SETTLED`) as an explicit append-only event record rather than overwriting invoice status in place.
- **Rationale:** Guarantees strict traceability and financial compliance required in enterprise logistics settlement.

### 1.5 Multi-Format Storage (CSV + SQLite + SQL Script)
- **Decision:** Maintain CSV as the primary interchange format while generating `outputs/freight_audit.db` SQLite database with typed foreign keys and indices, alongside `outputs/freight_audit_seed.sql`.
- **Rationale:** CSV ensures portability and human inspectability; SQLite supports relational queries and integrity checks; standalone SQL enables immediate migration to production RDBMS (PostgreSQL, MySQL).

---

## 2. Public Data Guidance & Lawful Data Provenance

- **Data Origin:** 100% synthetically generated using deterministic pseudo-random algorithms initialized with seed `20261022`.
- **Confidentiality:** Zero proprietary, personal, confidential, or live carrier freight data was scraped, ingested, or used.
- **Nomenclature & Standard Schema Inspiration:** Standard logistics naming conventions (e.g. SCAC carrier codes, IATA 3-letter airport/hub codes, standard accessorial codes `LIFTGATE`, `DETENTION`) are based on public open logistics standards (IATA, NMFTA, and public freight rate benchmarking practices).
- **Redistribution Rights:** Fully open, self-contained, and lawful for unlimited evaluation, testing, and distribution.
