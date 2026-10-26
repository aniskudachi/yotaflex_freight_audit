# YotaFlex Freight Invoice Validation & Audit Platform

A production-grade, reproducible synthetic-data platform and rule-based audit engine for validating commercial freight invoices against contracted carrier tariffs, shipment physical characteristics, auxiliary accessorials, certified scale measurements, and delivery records.

---

## 🌟 Key Features

- **Deterministic High-Performance Generator (`src/generate_data.py`)**:
  - Generates 11 core entities, an audit event history, and an isolated evaluation ground truth table.
  - Scale parameterization: `--scale starter` (quick local development) and `--scale full` (100 carriers, 20,000 shipments, 15,000 freight invoices) generated in **under 4 seconds** using $O(1)$ indexed tariff lookups.
  - 100% bitwise identical reproducibility with fixed seed (`20261022`).
- **Rule-Based 3-Way Matching Engine (`src/audit_invoices.py`)**:
  - Validates dimensional weight formula: $\text{round}((L \times W \times H) / 5000, 2)$ vs certified scale weight.
  - Chargeable weight tier validation, base freight rate matching, contracted fuel surcharge (12%), and accessorial pre-authorization checks.
  - Detects duplicate billing, expired tariffs, and unapproved accessorials.
  - Reconciles carrier credit notes against approved dispute limits (detects excessive credit memos).
- **Out-of-Band Ground Truth Evaluation**:
  - Evaluation ground truth (`ground_truth.csv` / `ground_truth.json`) is strictly isolated and never consumed by the audit engine.
  - Achieves **100% Precision, 100% Recall, and 100% Detection Rate** across all 7 negative anomaly categories.
- **Relational Persistence & Export**:
  - SQLite database (`outputs/freight_audit.db`) with primary keys, foreign keys, and query indices.
  - Standalone SQL seed script (`outputs/freight_audit_seed.sql`) compatible with PostgreSQL, SQLite, and MySQL.
- **Automated Data Quality Suite (`src/validate_data.py`)**:
  - Enforces 40 validation checks across PK uniqueness, FK referential integrity, allowed enums, date ordering, arithmetic reconciliation, and SHA-256 table digests.
- **Interactive Glassmorphic Web Dashboard (`src/app.py`)**:
  - Modern web UI at `http://127.0.0.1:8080` with dark mode, executive KPI cards, filter toolbar, 360-degree trace drawer, role switcher (Logistics Analyst, Operations Manager, Planner, Carrier Operator), dispute workflow, and confusion matrix visualizer.
  - Built with pure Python standard library and vanilla CSS/JS (zero npm packages or external runtime dependencies).

---

## 🏗️ Relational Data Model (11 Core Entities)

| # | Entity | Primary Key | Key Relationships / Constraints | Description |
|---|---|---|---|---|
| 1 | **Carrier** | `carrier_id` (`CAR-000001`) | Unique SCAC code, payment terms, lifecycle status | Contracted motor carriers / logistics providers. |
| 2 | **Lane** | `lane_id` (`LANE-0001`) | Origin hub $\ne$ Destination hub, distance km | Commercial transportation corridors. |
| 3 | **RateCard** | `rate_id` (`RATE-CAR-...`) | FK: Carrier, Lane; service tier, base rate, fuel % | Contracted freight tariffs by weight tier. |
| 4 | **Shipment** | `shipment_id` (`SHP-2026-000001`) | FK: Carrier, Lane, RateCard; actual/dim weights | Physical cargo booking, dimensions, and POD. |
| 5 | **ShipmentLeg** | `leg_id` (`LEG-2026-000001-01`) | FK: Shipment; sequence number, transit dates | Transit segment and hub routing records. |
| 6 | **WeightMeasurement** | `measurement_id` (`WM-2026-000001`) | FK: Shipment; scale ID, calibration flag | Origin terminal certified scale weigh-ins. |
| 7 | **Accessorial** | `accessorial_id` (`ACC-2026-000001`) | FK: Shipment; code, amount, eligibility, approval | Pre-approved auxiliary services (`LIFTGATE`, `DETENTION`). |
| 8 | **FreightInvoice** | `invoice_id` (`FINV-2026-000001`) | FK: Carrier, RateCard, Shipment | Carrier billing document for settlement. |
| 9 | **InvoiceLine** | `line_id` (`FLINE-...-01`) | FK: FreightInvoice; line type, amount | Itemized base freight, fuel, and accessorial lines. |
| 10 | **AuditException** | `exception_id` (`FEX-2026-000001`) | FK: FreightInvoice, Carrier; severity, variance | Logged 3-way match audit discrepancies. |
| 11 | **CreditNote** | `credit_note_id` (`CN-2026-000001`) | FK: AuditException, FreightInvoice, Carrier | Carrier credit memos reconciling dispute amounts. |
| 12 | **AuditEventHistory** | `event_id` (`EVT-2026-000001`) | FK: Entity ID; state transition, actor, notes | Immutable chronological audit trail. |
| 13 | **GroundTruth** | `case_id` (`GT-000001`) | Evaluation-only; anomaly type, expected decision | Out-of-band evaluation benchmark (never leaked). |

---

## 🚀 Quick Start CLI Workflow

Ensure you have **Python 3.10+** installed. No third-party dependencies are required.

```bash
# 1. Generate Starter Synthetic Dataset (10 carriers, 200 shipments, 150 invoices)
python src/generate_data.py --scale starter --out data

# 2. Run the Rule-Based Audit Engine
python src/audit_invoices.py --data data --out outputs

# 3. Load Relational SQLite Database
python src/load_sqlite.py --data data --db outputs/freight_audit.db --outputs outputs

# 4. Export Standalone SQL Seed Script
python src/export_sql.py --data data --out outputs/freight_audit_seed.sql

# 5. Run the 40-Rule Data Quality & Integrity Suite
python src/validate_data.py --data data --out outputs/validation_summary.json

# 6. Launch the Interactive Web Dashboard Server
python src/app.py --port 8080
```
Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)** in your browser to explore the interactive workbench!

---

## 📈 Generating Full Baseline Volume

To generate the requested full enterprise volume (100 carriers, 20,000 shipments, 15,000 freight invoices, 48,000 rate cards, 32,000+ line items):

```bash
python src/generate_data.py --scale full --out data_full
python src/audit_invoices.py --data data_full --out outputs_full
python src/validate_data.py --data data_full --out outputs_full/validation_summary.json
```
Generation of the full 20,000 shipment dataset completes in **~3.9 seconds**!

---

## 🌐 Public Cloud Deployment Guide

To share your Freight Invoice Audit Dashboard with recruiters or stakeholders 24/7 without keeping your computer running, deploy it to a free public hosting platform.

### Option 1: Render (Recommended — 100% Free Tier & Auto-Deploy)

Render natively supports Python web applications and continuously deploys changes whenever you push to your GitHub repository.

1. **Push your code to GitHub**:
   Ensure all changes and deployment files (`render.yaml`, `Procfile`, `Dockerfile`) are committed and pushed:
   ```bash
   git add .
   git commit -m "feat: add production cloud deployment configuration"
   git push origin main
   ```
2. **Sign up on Render**:
   - Go to [render.com](https://render.com) and log in with your GitHub account.
3. **Deploy with 1-Click Blueprint or New Web Service**:
   - **Method A (Blueprint)**: In the Render Dashboard, click **New +** > **Blueprint**, select your repository (`aniskudachi/yotaflex_freight_audit`), and Render will automatically read [`render.yaml`](file:///c:/Users/anisk/OneDrive/Desktop/yotaflex_freight_audit/render.yaml) and configure everything.
   - **Method B (Manual Web Service)**:
     - Click **New +** > **Web Service**.
     - Connect `https://github.com/aniskudachi/yotaflex_freight_audit`.
     - **Runtime**: `Python 3`
     - **Build Command**: `python -m pip install -r requirements.txt && python src/load_sqlite.py`
     - **Start Command**: `python src/app.py --host 0.0.0.0 --port $PORT`
     - **Instance Type**: `Free`
     - Click **Create Web Service**.
4. **Access the Public Dashboard**:
   Once the build completes (usually ~1–2 minutes), Render gives you an active public URL:
   `https://yotaflex-freight-audit.onrender.com`

---

### Option 2: Railway

1. Go to [railway.com](https://railway.com) and log in with GitHub.
2. Click **New Project** > **Deploy from GitHub repo** > select `yotaflex_freight_audit`.
3. Railway automatically detects [`Procfile`](file:///c:/Users/anisk/OneDrive/Desktop/yotaflex_freight_audit/Procfile) and [`Dockerfile`](file:///c:/Users/anisk/OneDrive/Desktop/yotaflex_freight_audit/Dockerfile).
4. Go to **Settings** > **Generate Domain** to get your public `https://*.up.railway.app` URL.

---

### Option 3: Docker Container

Build and run anywhere (Fly.io, AWS App Runner, Google Cloud Run, Azure Container Apps, or locally):

```bash
# Build production container
docker build -t yotaflex-freight-audit .

# Run container on port 8080
docker run -d -p 8080:8080 -e PORT=8080 --name freight-audit yotaflex-freight-audit
```

---

## 🧪 Running the Automated Test Suite

The test suite is compatible with both Python's built-in `unittest` runner and `pytest`:

```bash
# Run with Python built-in unittest (zero external dependencies required)
python -m unittest discover -s tests -p "test_*.py" -v

# Or run with pytest (if installed)
python -m pytest tests/ -v
```

### Test Suite Coverage (12 Automated Tests):
1. `test_starter_generation_and_audit`: Verifies end-to-end pipeline execution and output artifact generation.
2. `test_reproducibility_same_seed`: Confirms identical SHA-256 digests across dual generation runs.
3. `test_validation_integrity_rules`: Asserts all 40 data quality and referential integrity checks pass.
4. `test_ground_truth_isolation_and_recall`: Validates 100% anomaly detection recall and 100% precision with 0 false alarms.
5. `test_dimensional_weight_formula`: Asserts $\text{dim\_weight} = (L \times W \times H)/5000$ and $\text{chargeable} = \max(\text{actual}, \text{dim})$.
6. `test_credit_note_excess_dispute`: Verifies excess credit detection against approved dispute limits.
7. `test_sqlite_queryability`: Confirms relational joins across invoices, shipments, and rate cards.
8. `test_health_endpoints`: Validates `/health` and `/healthz` cloud orchestrator probes.
9. `test_static_assets_serving`: Verifies HTML, CSS, and JS static asset delivery.
10. `test_api_summary`: Validates executive metrics calculation and ground truth isolation scoring.
11. `test_api_invoices`: Tests multi-criteria filtering and pagination.
12. `test_api_carriers`: Verifies carrier master record retrieval.

---

## 🔁 Reproducibility Verification (Same-Seed SHA-256 Check)

To verify deterministic bitwise reproducibility, generate two runs using seed `20261022` and compare checksums:

```bash
python src/generate_data.py --scale starter --seed 20261022 --out test_seed_a
python src/generate_data.py --scale starter --seed 20261022 --out test_seed_b

python -c "
import json
from pathlib import Path
a = json.loads(Path('test_seed_a/source_manifest.json').read_text())['sha256']
b = json.loads(Path('test_seed_b/source_manifest.json').read_text())['sha256']
mismatches = [k for k in a if a[k] != b.get(k)]
print('Identical tables count:', len([k for k in a if a[k] == b.get(k)]))
print('Mismatches:', mismatches)
assert len(mismatches) == 0, 'Seed reproducibility failed!'
print('VERIFIED: 100% bitwise identical reproducibility!')
"
```

---

## ⚖️ Decision Policy & Negative Scenarios

| Decision | Criteria | Action & Accounting Treatment |
|---|---|---|
| **`PASS`** | Billed amount equals calculated contracted amount (within $\$0.01$ tolerance); rate active; approved accessorials match. | Auto-approved for batch accounts payable disbursement. |
| **`REVIEW`** | Chargeable weight tier misapplied, minor calculation variance, or price discrepancy. | Routed to Logistics Analyst for root cause analysis and formal dispute. |
| **`REJECT`** | Unknown shipment, duplicate invoice, expired rate card, duplicate fuel surcharge, unapproved accessorial, or excess credit note. | Invoice suspended; payment blocked; carrier dispute notice dispatched. |

### Labelled Anomaly Injections & Detection:
- **`UNKNOWN_SHIPMENT`**: Invoice references non-existent shipment (`REJECT`).
- **`EXPIRED_RATE_CARD`**: Invoice references expired tariff card (`REJECT`).
- **`WEIGHT_TIER_MISMATCH`**: Invoiced base rate charged at higher tier than chargeable weight warrants (`REVIEW`).
- **`DUPLICATE_SURCHARGE`**: Duplicate fuel surcharge lines billed on same invoice (`REJECT`).
- **`INVALID_ACCESSORIAL`**: Unapproved or ineligible accessorial line billed (`REJECT`).
- **`DUPLICATE_INVOICE`**: Same shipment billed across multiple invoices (`REJECT`).
- **`EXCESS_CREDIT`**: Carrier credit note issued for amount exceeding approved dispute amount (`REJECT`).

---

## 🔒 Public Data Guidance & Lawful Data Provenance

1. **Synthetic Generation:** All records, carrier names, addresses, and transaction IDs are synthetically generated using deterministic algorithms. No live, personal, or confidential shipper/carrier data was accessed or scraped.
2. **Open Industry Standards:** Tariffs, accessorial codes (`LIFTGATE`, `DETENTION`, `HAZMAT`), dimensional weight divisor ($5000\text{ cm}^3/\text{kg}$), and SCAC naming conventions are patterned after publicly documented freight industry standards.
3. **Lawful Provenance:** The dataset is fully self-contained and permitted for unrestricted redistribution, testing, benchmarking, and demonstration.
