#!/usr/bin/env python3
"""Comprehensive dataset integrity, foreign-key, enum, date ordering, and reconciliation validator.

Enforces Step 8 criteria:
- Primary-key uniqueness across all 11 core tables
- Foreign-key referential integrity across all relationships
- Allowed enum validation
- Date ordering validation (ship <= deliver <= invoice, effective_from <= effective_to)
- Arithmetic reconciliation (sum of lines == billed_total, chargeable == max(actual, dim))
- Duplicate detection
- SHA-256 table checksums
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

def read(p):
    if not Path(p).exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def validate_all(data_dir, out_file):
    d = Path(data_dir)
    checks = []
    counts = {}

    # 1. Read Tables
    tables = {p.name: read(p) for p in sorted(d.glob("*.csv"))}
    for name, rows in tables.items():
        counts[name] = len(rows)

    # Helper to add check result
    def record_check(category, check_name, passed, details=None):
        checks.append({
            "category": category,
            "check": check_name,
            "passed": bool(passed),
            "details": details or ""
        })

    # 2. Primary Key Uniqueness
    pk_map = {
        "carrier.csv": "carrier_id",
        "lane.csv": "lane_id",
        "rate_card.csv": "rate_id",
        "shipment.csv": "shipment_id",
        "shipment_leg.csv": "leg_id",
        "weight_measurement.csv": "measurement_id",
        "accessorial.csv": "accessorial_id",
        "freight_invoice.csv": "invoice_id",
        "invoice_line.csv": "line_id",
        "audit_exception.csv": "exception_id",
        "credit_note.csv": "credit_note_id",
        "audit_event_history.csv": "event_id",
        "ground_truth.csv": "case_id"
    }

    for tname, pk in pk_map.items():
        rows = tables.get(tname, [])
        if rows:
            vals = [r[pk] for r in rows if pk in r]
            is_unique = len(vals) == len(set(vals))
            record_check(
                "PRIMARY_KEY_UNIQUENESS",
                f"{tname}: unique PK '{pk}'",
                is_unique,
                f"Total {len(vals)} rows, {len(set(vals))} unique IDs."
            )

    # 3. Foreign Key Integrity
    carriers = {r["carrier_id"] for r in tables.get("carrier.csv", [])}
    lanes = {r["lane_id"] for r in tables.get("lane.csv", [])}
    rates = {r["rate_id"] for r in tables.get("rate_card.csv", [])}
    shipments = {r["shipment_id"]: r for r in tables.get("shipment.csv", [])}
    invoices = {r["invoice_id"]: r for r in tables.get("freight_invoice.csv", [])}
    exceptions = {r["exception_id"] for r in tables.get("audit_exception.csv", [])}
    gt_unknown_shipments = {
        r["invoice_id"] for r in tables.get("ground_truth.csv", [])
        if r.get("issue_type") == "UNKNOWN_SHIPMENT"
    }

    # RateCard -> Carrier, Lane
    rc_carrier_fk = all(r["carrier_id"] in carriers for r in tables.get("rate_card.csv", []))
    rc_lane_fk = all(r["lane_id"] in lanes for r in tables.get("rate_card.csv", []))
    record_check("FOREIGN_KEY_INTEGRITY", "rate_card -> carrier.carrier_id", rc_carrier_fk)
    record_check("FOREIGN_KEY_INTEGRITY", "rate_card -> lane.lane_id", rc_lane_fk)

    # Shipment -> Carrier, Lane, RateCard
    shp_fk = all(
        r["carrier_id"] in carriers and r["lane_id"] in lanes and r["rate_id"] in rates
        for r in tables.get("shipment.csv", [])
    )
    record_check("FOREIGN_KEY_INTEGRITY", "shipment -> carrier, lane, rate_card", shp_fk)

    # ShipmentLeg -> Shipment
    leg_fk = all(r["shipment_id"] in shipments for r in tables.get("shipment_leg.csv", []))
    record_check("FOREIGN_KEY_INTEGRITY", "shipment_leg -> shipment.shipment_id", leg_fk)

    # WeightMeasurement -> Shipment
    wm_fk = all(r["shipment_id"] in shipments for r in tables.get("weight_measurement.csv", []))
    record_check("FOREIGN_KEY_INTEGRITY", "weight_measurement -> shipment.shipment_id", wm_fk)

    # Accessorial -> Shipment
    acc_fk = all(r["shipment_id"] in shipments for r in tables.get("accessorial.csv", []))
    record_check("FOREIGN_KEY_INTEGRITY", "accessorial -> shipment.shipment_id", acc_fk)

    # FreightInvoice -> Carrier, RateCard
    inv_carrier_fk = all(r["carrier_id"] in carriers for r in tables.get("freight_invoice.csv", []))
    inv_rate_fk = all(r["source_rate_id"] in rates for r in tables.get("freight_invoice.csv", []))
    record_check("FOREIGN_KEY_INTEGRITY", "freight_invoice -> carrier.carrier_id", inv_carrier_fk)
    record_check("FOREIGN_KEY_INTEGRITY", "freight_invoice -> rate_card.rate_id", inv_rate_fk)

    # FreightInvoice -> Shipment (Controlled Anomaly: UNKNOWN_SHIPMENT is verified against ground truth)
    inv_shp_valid = True
    for inv in tables.get("freight_invoice.csv", []):
        sid = inv["shipment_id"]
        inv_id = inv["invoice_id"]
        if sid not in shipments:
            if inv_id not in gt_unknown_shipments:
                inv_shp_valid = False
                break
    record_check(
        "FOREIGN_KEY_INTEGRITY",
        "freight_invoice -> shipment.shipment_id (allowing labelled UNKNOWN_SHIPMENT anomalies)",
        inv_shp_valid,
        f"Verified {len(gt_unknown_shipments)} controlled test anomaly cases."
    )

    # InvoiceLine -> FreightInvoice
    line_fk = all(r["invoice_id"] in invoices for r in tables.get("invoice_line.csv", []))
    record_check("FOREIGN_KEY_INTEGRITY", "invoice_line -> freight_invoice.invoice_id", line_fk)

    # AuditException -> FreightInvoice, Carrier
    if "audit_exception.csv" in tables:
        ex_fk = all(
            r["invoice_id"] in invoices and r["carrier_id"] in carriers
            for r in tables["audit_exception.csv"]
        )
        record_check("FOREIGN_KEY_INTEGRITY", "audit_exception -> freight_invoice, carrier", ex_fk)

    # CreditNote -> Exception, FreightInvoice, Carrier
    if "credit_note.csv" in tables:
        cn_fk = all(
            r["invoice_id"] in invoices and r["carrier_id"] in carriers and
            (not r.get("exception_id") or r["exception_id"] in exceptions)
            for r in tables["credit_note.csv"]
        )
        record_check("FOREIGN_KEY_INTEGRITY", "credit_note -> audit_exception, invoice, carrier", cn_fk)

    # 4. Allowed Enums Validation
    enum_rules = [
        ("carrier.csv", "status", {"ACTIVE", "INACTIVE", "SUSPENDED"}),
        ("carrier.csv", "payment_terms", {"NET15", "NET30", "NET45", "NET60"}),
        ("rate_card.csv", "service", {"STANDARD", "EXPRESS"}),
        ("rate_card.csv", "status", {"ACTIVE", "EXPIRED", "SUPERSEDED"}),
        ("shipment.csv", "service", {"STANDARD", "EXPRESS"}),
        ("shipment.csv", "delivery_status", {"DELIVERED", "IN_TRANSIT", "EXCEPTION"}),
        ("accessorial.csv", "code", {"LIFTGATE", "RESIDENTIAL", "DETENTION", "HAZMAT", "APPOINTMENT_DELIVERY", "INSIDE_PICKUP"}),
        ("invoice_line.csv", "line_type", {"BASE", "FUEL", "LIFTGATE", "RESIDENTIAL", "DETENTION", "HAZMAT", "APPOINTMENT_DELIVERY", "INSIDE_PICKUP"}),
        ("freight_invoice.csv", "status", {"RECEIVED", "AUDITED", "APPROVED", "DISPUTED", "REJECTED"})
    ]

    for tname, col, allowed in enum_rules:
        rows = tables.get(tname, [])
        if rows:
            bad_vals = [r[col] for r in rows if r.get(col) not in allowed]
            record_check(
                "ENUM_VALIDATION",
                f"{tname}.{col} in {sorted(allowed)}",
                len(bad_vals) == 0,
                f"Found {len(bad_vals)} invalid values." if bad_vals else "All values match allowed enums."
            )

    # 5. Date Ordering Validation
    # RateCard: effective_from <= effective_to
    rc_dates = all(r["effective_from"] <= r["effective_to"] for r in tables.get("rate_card.csv", []))
    record_check("DATE_ORDERING", "rate_card: effective_from <= effective_to", rc_dates)

    # Shipment: ship_date <= delivery_date
    shp_dates = all(r["ship_date"] <= r["delivery_date"] for r in tables.get("shipment.csv", []))
    record_check("DATE_ORDERING", "shipment: ship_date <= delivery_date", shp_dates)

    # FreightInvoice: invoice_date >= delivery_date (for known shipments)
    inv_dates = True
    for inv in tables.get("freight_invoice.csv", []):
        s = shipments.get(inv["shipment_id"])
        if s and inv["invoice_date"] < s["delivery_date"]:
            inv_dates = False
            break
    record_check("DATE_ORDERING", "freight_invoice: invoice_date >= shipment.delivery_date", inv_dates)

    # 6. Arithmetic Reconciliation
    # Shipment: dimensional weight = (L * W * H) / 5000
    dim_wt_reconciled = True
    chargeable_reconciled = True
    for s in tables.get("shipment.csv", []):
        l, w, h = float(s["length_cm"]), float(s["width_cm"]), float(s["height_cm"])
        expected_dim = round((l * w * h) / 5000.0, 2)
        actual_wt = float(s["actual_weight_kg"])
        expected_chargeable = round(max(actual_wt, expected_dim), 2)
        if abs(float(s["dimensional_weight_kg"]) - expected_dim) > 0.02:
            dim_wt_reconciled = False
        if abs(float(s["chargeable_weight_kg"]) - expected_chargeable) > 0.02:
            chargeable_reconciled = False

    record_check(
        "ARITHMETIC_RECONCILIATION",
        "shipment: dimensional_weight_kg == round((L*W*H)/5000, 2)",
        dim_wt_reconciled
    )
    record_check(
        "ARITHMETIC_RECONCILIATION",
        "shipment: chargeable_weight_kg == max(actual_weight, dim_weight)",
        chargeable_reconciled
    )

    # Invoice: sum of invoice_line amounts == billed_total
    lines_by_inv = defaultdict(list)
    for line in tables.get("invoice_line.csv", []):
        lines_by_inv[line["invoice_id"]].append(float(line["amount"]))

    line_sums_match = True
    for inv in tables.get("freight_invoice.csv", []):
        sum_lines = round(sum(lines_by_inv.get(inv["invoice_id"], [])) + 1e-9, 2)
        billed = round(float(inv["billed_total"]) + 1e-9, 2)
        if abs(sum_lines - billed) > 0.01:
            line_sums_match = False
            break
    record_check(
        "ARITHMETIC_RECONCILIATION",
        "freight_invoice: billed_total == sum(invoice_line.amount)",
        line_sums_match
    )

    # 7. Checksums
    checksums = {}
    for p in sorted(d.glob("*.csv")):
        checksums[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()

    all_passed = all(c["passed"] for c in checks)
    summary = {
        "status": "PASSED" if all_passed else "FAILED",
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["passed"]),
        "failed_checks": sum(1 for c in checks if not c["passed"]),
        "all_checks_passed": all_passed,
        "table_counts": counts,
        "checks": checks,
        "sha256": checksums
    }

    out_p = Path(out_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": summary["status"],
        "total_checks": summary["total_checks"],
        "passed_checks": summary["passed_checks"],
        "all_checks_passed": all_passed
    }, indent=2))

    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dataset integrity and reconciliation validator")
    parser.add_argument("--data", default="data", help="Data directory containing CSV tables")
    parser.add_argument("--out", default="outputs/validation_summary.json", help="Output summary path")
    args = parser.parse_args()
    validate_all(args.data, args.out)
