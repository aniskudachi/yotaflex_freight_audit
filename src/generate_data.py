#!/usr/bin/env python3
"""Deterministic synthetic freight data generator.

Generates 11 core freight entities and an evaluation ground truth table:
- Master data: Carrier, Lane, RateCard
- Transactions & events: Shipment, ShipmentLeg, WeightMeasurement, Accessorial
- Invoicing & settlement: FreightInvoice, InvoiceLine, AuditException, CreditNote
- Event audit trail: AuditEventHistory
- Out-of-band evaluation: GroundTruth (never consumed by the audit engine)

Adheres strictly to the nomenclature conventions:
- Carrier: CAR-000001
- RateCard: RATE-<carrier-id>-2026-01-...
- Shipment: SHP-2026-000001
- FreightInvoice: FINV-2026-000001
- InvoiceLine: FLINE-<invoice-id>-01
- AuditException: FEX-2026-000001
- CreditNote: CN-2026-000001
"""
import argparse
import csv
import hashlib
import json
import os
import random
from datetime import date, timedelta
from pathlib import Path

SEED_DEFAULT = 20261022

ANOMALY_TYPES = [
    "UNKNOWN_SHIPMENT",
    "EXPIRED_RATE_CARD",
    "WEIGHT_TIER_MISMATCH",
    "DUPLICATE_SURCHARGE",
    "INVALID_ACCESSORIAL",
    "DUPLICATE_INVOICE",
    "EXCESS_CREDIT",
]

def money(v):
    return round(float(v) + 1e-9, 2)

def iso(d):
    return d.isoformat()

def write_csv(path, rows, fields=None):
    rows = list(rows)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return len(rows)

def generate(out_dir, scale="starter", seed=SEED_DEFAULT):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    if scale == "full":
        n_carriers = 100
        n_shipments = 20000
        n_invoices = 15000
    else:  # starter
        n_carriers = 10
        n_shipments = 200
        n_invoices = 150

    today = date(2026, 10, 1)

    # -------------------------------------------------------------
    # 1. Master Data: Carriers
    # -------------------------------------------------------------
    carrier_names_prefix = [
        "Apex Freight", "SwiftHaul Logistics", "Blue Dart Express", "TransGlobal Carriers",
        "Pinnacle Line", "Vanguard Logistics", "Titan Freightway", "Pacific Cargo",
        "Eagle Freight", "Beacon Transport", "Summit Dispatch", "Frontier Freight",
        "Atlas Roadways", "DirectRoute Express", "Meridian Line", "Prime Logistics"
    ]
    payment_terms_pool = ["NET30", "NET15", "NET45", "NET60"]
    carriers = []
    for i in range(1, n_carriers + 1):
        cid = f"CAR-{i:06d}"
        prefix = carrier_names_prefix[(i - 1) % len(carrier_names_prefix)]
        name = f"{prefix} {i:03d}"
        scac = f"C{i:03d}X"[:4]
        status = "INACTIVE" if (i % 23 == 0) else "ACTIVE"
        created = today - timedelta(days=365 + (i * 3))
        carriers.append({
            "carrier_id": cid,
            "carrier_name": name,
            "scac_code": scac,
            "contact_email": f"billing@{scac.lower()}.freight.com",
            "phone": f"+1-555-{100 + (i % 900):03d}-{1000 + (i % 9000):04d}",
            "payment_terms": payment_terms_pool[i % len(payment_terms_pool)],
            "status": status,
            "created_at": iso(created)
        })

    # -------------------------------------------------------------
    # 2. Master Data: Lanes
    # -------------------------------------------------------------
    hub_cities = [
        ("BLR", "Bengaluru", "KA"),
        ("BOM", "Mumbai", "MH"),
        ("DEL", "Delhi", "DL"),
        ("MAA", "Chennai", "TN"),
        ("HYD", "Hyderabad", "TS"),
        ("PNQ", "Pune", "MH"),
        ("CCU", "Kolkata", "WB"),
        ("COK", "Kochi", "KL"),
        ("AMD", "Ahmedabad", "GJ"),
        ("JAI", "Jaipur", "RJ"),
    ]
    lanes = []
    lane_idx = 1
    for o_code, o_city, o_st in hub_cities:
        for d_code, d_city, d_st in hub_cities:
            if o_code == d_code:
                continue
            # Pick a subset of lanes so lane count is realistic (e.g. 20 primary lanes)
            if (lane_idx <= 20) or (scale == "full" and lane_idx <= 40):
                dist = 300 + (lane_idx * 65) % 1800
                std_days = max(1, int(dist / 450))
                exp_days = max(1, int(std_days / 2))
                lanes.append({
                    "lane_id": f"LANE-{lane_idx:04d}",
                    "origin_code": o_code,
                    "origin_city": o_city,
                    "origin_state": o_st,
                    "destination_code": d_code,
                    "destination_city": d_city,
                    "destination_state": d_st,
                    "distance_km": dist,
                    "transit_days_std": std_days,
                    "transit_days_exp": exp_days
                })
                lane_idx += 1
            if len(lanes) >= (30 if scale == "full" else 12):
                break
        if len(lanes) >= (30 if scale == "full" else 12):
            break

    # -------------------------------------------------------------
    # 3. Master Data: Rate Cards
    # -------------------------------------------------------------
    services = ["STANDARD", "EXPRESS"]
    # 4 standard weight tiers: 0-5kg, 5-15kg, 15-30kg, 30+kg
    tiers = [
        (0.0, 5.0, 80.0),
        (5.0, 15.0, 140.0),
        (15.0, 30.0, 220.0),
        (30.0, 999999.0, 360.0)
    ]

    rate_cards = []
    rate_lookup = {}  # (carrier_id, lane_id, service, tier_idx) -> rate_card
    expired_rate_lookup = {}  # (carrier_id, lane_id, service, tier_idx) -> expired_rate_card

    for c in carriers:
        c_num = int(c["carrier_id"].split("-")[1])
        carrier_adj = 1.0 + (c_num % 7) * 0.02
        for l in lanes:
            dist_factor = 1.0 + (l["distance_km"] / 2000.0)
            for s in services:
                svc_mult = 1.30 if s == "EXPRESS" else 1.0
                for t_idx, (w_lo, w_hi, base_val) in enumerate(tiers, 1):
                    rate_id = f"RATE-{c['carrier_id']}-2026-01-L{l['lane_id'][-4:]}-{s[:3]}-T{t_idx}"
                    calc_base = money(base_val * carrier_adj * dist_factor * svc_mult)
                    fuel_pct = 0.12  # Contracted 12% fuel surcharge

                    rc = {
                        "rate_id": rate_id,
                        "carrier_id": c["carrier_id"],
                        "lane_id": l["lane_id"],
                        "service": s,
                        "weight_min_kg": f"{w_lo:.1f}",
                        "weight_max_kg": f"{w_hi:.1f}",
                        "base_rate": f"{calc_base:.2f}",
                        "fuel_pct": f"{fuel_pct:.2f}",
                        "currency": "USD",
                        "effective_from": "2026-01-01",
                        "effective_to": "2026-12-31",
                        "status": "ACTIVE"
                    }
                    rate_cards.append(rc)
                    rate_lookup[(c["carrier_id"], l["lane_id"], s, t_idx)] = rc

                    # Create an explicitly expired prior-year rate card for expired rate card testing
                    exp_rate_id = f"RATE-{c['carrier_id']}-2025-01-L{l['lane_id'][-4:]}-{s[:3]}-T{t_idx}"
                    exp_rc = {
                        "rate_id": exp_rate_id,
                        "carrier_id": c["carrier_id"],
                        "lane_id": l["lane_id"],
                        "service": s,
                        "weight_min_kg": f"{w_lo:.1f}",
                        "weight_max_kg": f"{w_hi:.1f}",
                        "base_rate": f"{money(calc_base * 0.95):.2f}",
                        "fuel_pct": "0.10",
                        "currency": "USD",
                        "effective_from": "2025-01-01",
                        "effective_to": "2025-12-31",
                        "status": "EXPIRED"
                    }
                    rate_cards.append(exp_rc)
                    expired_rate_lookup[(c["carrier_id"], l["lane_id"], s, t_idx)] = exp_rc

    # -------------------------------------------------------------
    # 4. Shipments, Legs, Weights, and Accessorials
    # -------------------------------------------------------------
    shipments = []
    legs = []
    weights = []
    accessorials = []
    shipment_by_id = {}
    shipment_rates = {}
    accessorials_by_shipment = {}

    accessorial_catalog = {
        "LIFTGATE": 35.00,
        "RESIDENTIAL": 25.00,
        "DETENTION": 50.00,
        "HAZMAT": 65.00,
        "APPOINTMENT_DELIVERY": 20.00
    }

    signatory_pool = ["J. Smith", "A. Sharma", "R. Davis", "K. Patel", "M. Taylor", "S. Kumar"]

    for i in range(1, n_shipments + 1):
        sid = f"SHP-2026-{i:06d}"
        carrier = carriers[(i - 1) % n_carriers]
        lane = lanes[(i * 3) % len(lanes)]
        service = "EXPRESS" if (i % 3 == 0) else "STANDARD"

        # Actual weight and physical dimensions
        actual_wt = round(rng.uniform(1.5, 48.0), 2)
        # Dimensions (length, width, height) in cm
        dim_l = round(rng.uniform(15.0, 110.0), 1)
        dim_w = round(rng.uniform(15.0, 90.0), 1)
        dim_h = round(rng.uniform(10.0, 85.0), 1)
        # Dimensional weight with standard IATA / domestic factor 5000:
        dim_wt = round((dim_l * dim_w * dim_h) / 5000.0, 2)
        chargeable_wt = round(max(actual_wt, dim_wt), 2)

        # Match weight tier
        tier_idx = 1
        for idx, (w_lo, w_hi, _) in enumerate(tiers, 1):
            if w_lo <= chargeable_wt < w_hi:
                tier_idx = idx
                break

        matched_rate = rate_lookup[(carrier["carrier_id"], lane["lane_id"], service, tier_idx)]
        shipment_rates[sid] = (matched_rate, tier_idx)

        # Dates: ship date within past 180 days, delivery date following transit schedule
        days_ago = rng.randint(5, 180)
        ship_dt = today - timedelta(days=days_ago)
        transit_days = lane["transit_days_exp"] if service == "EXPRESS" else lane["transit_days_std"]
        delivery_dt = ship_dt + timedelta(days=transit_days)

        shipment_row = {
            "shipment_id": sid,
            "carrier_id": carrier["carrier_id"],
            "lane_id": lane["lane_id"],
            "service": service,
            "ship_date": iso(ship_dt),
            "delivery_date": iso(delivery_dt),
            "actual_weight_kg": f"{actual_wt:.2f}",
            "length_cm": f"{dim_l:.1f}",
            "width_cm": f"{dim_w:.1f}",
            "height_cm": f"{dim_h:.1f}",
            "dimensional_weight_kg": f"{dim_wt:.2f}",
            "chargeable_weight_kg": f"{chargeable_wt:.2f}",
            "delivery_status": "DELIVERED",
            "rate_id": matched_rate["rate_id"],
            "pod_signatory": signatory_pool[i % len(signatory_pool)]
        }
        shipments.append(shipment_row)
        shipment_by_id[sid] = shipment_row

        # Shipment Leg
        legs.append({
            "leg_id": f"LEG-2026-{i:06d}-01",
            "shipment_id": sid,
            "sequence_no": 1,
            "origin": lane["origin_code"],
            "destination": lane["destination_code"],
            "depart_date": iso(ship_dt),
            "arrive_date": iso(delivery_dt),
            "status": "COMPLETED"
        })

        # Certified Weight Measurement at origin terminal
        weights.append({
            "measurement_id": f"WM-2026-{i:06d}",
            "shipment_id": sid,
            "measured_weight_kg": f"{actual_wt:.2f}",
            "unit": "kg",
            "scale_id": f"SCALE-{lane['origin_code']}-01",
            "certified": "true",
            "measured_at": iso(ship_dt)
        })

        # Accessorial service (approx 12% of shipments qualify)
        if rng.random() < 0.12:
            acc_code = rng.choice(list(accessorial_catalog.keys()))
            acc_amt = accessorial_catalog[acc_code]
            acc_row = {
                "accessorial_id": f"ACC-2026-{len(accessorials) + 1:06d}",
                "shipment_id": sid,
                "code": acc_code,
                "amount": f"{acc_amt:.2f}",
                "eligible": "true",
                "approved": "true",
                "approval_ref": f"AUTH-{lane['origin_code']}-{i % 999:03d}"
            }
            accessorials.append(acc_row)
            accessorials_by_shipment.setdefault(sid, []).append(acc_row)

    # -------------------------------------------------------------
    # 5. Invoicing, Exceptions, Credit Notes, and Ground Truth
    # -------------------------------------------------------------
    invoices = []
    invoice_lines = []
    audit_exceptions = []
    credit_notes = []
    ground_truth = []
    audit_events = []

    # Inject edge cases at controlled slots so every anomaly category has multiple realistic cases
    # Target approx 6-8% overall anomaly rate
    anomaly_map = {}
    if scale == "starter":
        # 14 distinct anomalies spread across the 150 starter invoices (2 of each type)
        slots = [
            (10, "UNKNOWN_SHIPMENT"), (25, "UNKNOWN_SHIPMENT"),
            (35, "EXPIRED_RATE_CARD"), (45, "EXPIRED_RATE_CARD"),
            (55, "WEIGHT_TIER_MISMATCH"), (65, "WEIGHT_TIER_MISMATCH"),
            (75, "DUPLICATE_SURCHARGE"), (85, "DUPLICATE_SURCHARGE"),
            (95, "INVALID_ACCESSORIAL"), (105, "INVALID_ACCESSORIAL"),
            (115, "DUPLICATE_INVOICE"), (125, "DUPLICATE_INVOICE"),
            (135, "EXCESS_CREDIT"), (145, "EXCESS_CREDIT")
        ]
        anomaly_map = dict(slots)
    else:
        # Full scale: inject across 15,000 invoices (approx 150 of each type = ~1,050 total anomalies)
        step = 14
        types_cycle = ANOMALY_TYPES * 160
        for idx, typ in enumerate(types_cycle):
            slot_num = 15 + idx * step
            if slot_num <= n_invoices:
                anomaly_map[slot_num] = typ

    exception_counter = 0
    credit_counter = 0
    gt_counter = 0
    event_counter = 0

    # Track billed shipments to simulate duplicate invoices
    billed_shipment_to_inv = {}

    for i in range(1, n_invoices + 1):
        inv_id = f"FINV-2026-{i:06d}"
        anomaly = anomaly_map.get(i, "")

        # Default: pick unique shipment matching invoice index
        shipment_idx = ((i - 1) % n_shipments) + 1
        sid = f"SHP-2026-{shipment_idx:06d}"
        shipment = shipment_by_id[sid]
        matched_rate, current_tier_idx = shipment_rates[sid]

        billed_rate = matched_rate
        invoice_sid = sid
        carrier_id = shipment["carrier_id"]
        deliv_dt = date.fromisoformat(shipment["delivery_date"])
        inv_dt = deliv_dt + timedelta(days=2)

        # Baseline expected line components
        base_amt = float(matched_rate["base_rate"])
        fuel_amt = money(base_amt * float(matched_rate["fuel_pct"]))
        eligible_accs = accessorials_by_shipment.get(sid, [])

        lines_for_inv = [
            {"line_type": "BASE", "amount": base_amt, "description": "Contracted base freight charge"},
            {"line_type": "FUEL", "amount": fuel_amt, "description": "Contracted fuel surcharge (12%)"}
        ]
        for acc in eligible_accs:
            lines_for_inv.append({
                "line_type": acc["code"],
                "amount": float(acc["amount"]),
                "description": f"Approved {acc['code']} accessorial"
            })

        # Inject Anomaly Logic
        expected_decision = "PASS"
        expected_variance = 0.00
        gt_detail = "Valid invoice matching rate card and shipment attributes."

        if anomaly == "UNKNOWN_SHIPMENT":
            invoice_sid = "SHP-2026-999999"
            expected_decision = "REJECT"
            gt_detail = "Invoice references non-existent shipment SHP-2026-999999."
            expected_variance = money(sum(l["amount"] for l in lines_for_inv))

        elif anomaly == "EXPIRED_RATE_CARD":
            # Point to an expired rate card from the rate_card table (effective 2025)
            exp_card = expired_rate_lookup[(carrier_id, shipment["lane_id"], shipment["service"], current_tier_idx)]
            billed_rate = exp_card
            expected_decision = "REJECT"
            gt_detail = f"Invoice uses expired tariff {exp_card['rate_id']} (expired 2025-12-31)."

        elif anomaly == "WEIGHT_TIER_MISMATCH":
            # Overbill by charging at Tier 4 rate instead of Tier 1/2 rate
            overcharge_bump = 75.00
            lines_for_inv[0]["amount"] = money(lines_for_inv[0]["amount"] + overcharge_bump)
            lines_for_inv[0]["description"] = "Misapplied weight tier (charged higher tier)"
            expected_decision = "REVIEW"
            expected_variance = overcharge_bump
            gt_detail = f"Base freight billed at higher tier; overcharge of ${overcharge_bump:.2f}."

        elif anomaly == "DUPLICATE_SURCHARGE":
            # Duplicate the fuel line
            lines_for_inv.append({
                "line_type": "FUEL",
                "amount": fuel_amt,
                "description": "Duplicate fuel surcharge billed in error"
            })
            expected_decision = "REJECT"
            expected_variance = fuel_amt
            gt_detail = f"Duplicate fuel surcharge line of ${fuel_amt:.2f}."

        elif anomaly == "INVALID_ACCESSORIAL":
            # Add an accessorial not approved for this shipment
            unapproved_amt = 50.00
            lines_for_inv.append({
                "line_type": "DETENTION",
                "amount": unapproved_amt,
                "description": "Unapproved detention fee billed"
            })
            expected_decision = "REJECT"
            expected_variance = unapproved_amt
            gt_detail = f"Unapproved DETENTION accessorial fee of ${unapproved_amt:.2f}."

        elif anomaly == "DUPLICATE_INVOICE":
            # Reference an earlier shipment that was already billed
            earlier_inv_num = max(1, i - 10)
            earlier_sid = invoices[earlier_inv_num - 1]["shipment_id"]
            if earlier_sid != "SHP-2026-999999":
                invoice_sid = earlier_sid
            expected_decision = "REJECT"
            gt_detail = f"Duplicate invoice billing for already-billed shipment {invoice_sid}."
            expected_variance = money(sum(l["amount"] for l in lines_for_inv))

        elif anomaly == "EXCESS_CREDIT":
            # Invoice is otherwise normal, but linked credit note will exceed dispute amount
            expected_decision = "REVIEW"
            gt_detail = "Credit note issued for amount exceeding approved dispute limit."

        inv_total = money(sum(l["amount"] for l in lines_for_inv))
        invoice_status = "RECEIVED"

        invoices.append({
            "invoice_id": inv_id,
            "carrier_id": carrier_id,
            "shipment_id": invoice_sid,
            "invoice_number": f"INV-{carrier_id[-4:]}-{i:06d}",
            "invoice_date": iso(inv_dt),
            "due_date": iso(inv_dt + timedelta(days=30)),
            "currency": "USD",
            "billed_total": f"{inv_total:.2f}",
            "source_rate_id": billed_rate["rate_id"],
            "status": invoice_status
        })

        # Invoice Lines
        for line_no, l_data in enumerate(lines_for_inv, 1):
            invoice_lines.append({
                "line_id": f"FLINE-{inv_id}-{line_no:02d}",
                "invoice_id": inv_id,
                "line_no": line_no,
                "line_type": l_data["line_type"],
                "amount": f"{l_data['amount']:.2f}",
                "description": l_data["description"]
            })

        # Event: Invoice Received
        event_counter += 1
        audit_events.append({
            "event_id": f"EVT-2026-{event_counter:06d}",
            "entity_type": "INVOICE",
            "entity_id": inv_id,
            "previous_state": "NONE",
            "new_state": "RECEIVED",
            "actor": "Carrier",
            "notes": f"Invoice {inv_id} received from carrier {carrier_id}.",
            "timestamp": f"{iso(inv_dt)}T09:00:00Z"
        })

        # Ground Truth record for evaluation (if anomaly present)
        if anomaly:
            gt_counter += 1
            ground_truth.append({
                "case_id": f"GT-{gt_counter:06d}",
                "invoice_id": inv_id,
                "issue_type": anomaly,
                "expected_decision": expected_decision,
                "expected_variance": f"{expected_variance:.2f}",
                "details": gt_detail
            })

            # Create operational AuditException and CreditNote records for discrepancy cases
            exception_counter += 1
            ex_id = f"FEX-2026-{exception_counter:06d}"
            severity = "REJECT" if expected_decision == "REJECT" else "REVIEW"

            audit_exceptions.append({
                "exception_id": ex_id,
                "invoice_id": inv_id,
                "shipment_id": invoice_sid,
                "carrier_id": carrier_id,
                "issue_type": anomaly,
                "severity": severity,
                "expected_amount": f"{money(inv_total - expected_variance):.2f}" if anomaly != "UNKNOWN_SHIPMENT" else "",
                "billed_amount": f"{inv_total:.2f}",
                "variance": f"{expected_variance:.2f}" if anomaly != "UNKNOWN_SHIPMENT" else "",
                "explanation": gt_detail,
                "status": "OPEN",
                "assigned_to": "Logistics Analyst",
                "created_at": iso(inv_dt + timedelta(days=1))
            })

            # Credit note handling:
            # For anomalies that result in approved disputes, carriers issue credit notes
            if anomaly in ("WEIGHT_TIER_MISMATCH", "DUPLICATE_SURCHARGE", "EXCESS_CREDIT"):
                credit_counter += 1
                cn_id = f"CN-2026-{credit_counter:06d}"
                approved_dispute = expected_variance if anomaly != "EXCESS_CREDIT" else 50.00
                credit_amount = approved_dispute if anomaly != "EXCESS_CREDIT" else 5000.00
                validation_stat = "VALID" if anomaly != "EXCESS_CREDIT" else "EXCESS_CREDIT"

                credit_notes.append({
                    "credit_note_id": cn_id,
                    "exception_id": ex_id,
                    "invoice_id": inv_id,
                    "carrier_id": carrier_id,
                    "credit_note_no": f"CR-{carrier_id[-4:]}-{credit_counter:05d}",
                    "credit_date": iso(inv_dt + timedelta(days=5)),
                    "amount": f"{credit_amount:.2f}",
                    "approved_dispute_amount": f"{approved_dispute:.2f}",
                    "validation_status": validation_stat,
                    "status": "RECEIVED"
                })

    # -------------------------------------------------------------
    # 6. Export Tables & Compute SHA-256 Checksums
    # -------------------------------------------------------------
    tables = {
        "carrier.csv": carriers,
        "lane.csv": lanes,
        "rate_card.csv": rate_cards,
        "shipment.csv": shipments,
        "shipment_leg.csv": legs,
        "weight_measurement.csv": weights,
        "accessorial.csv": accessorials,
        "freight_invoice.csv": invoices,
        "invoice_line.csv": invoice_lines,
        "audit_exception.csv": audit_exceptions,
        "credit_note.csv": credit_notes,
        "audit_event_history.csv": audit_events,
        "ground_truth.csv": ground_truth
    }

    counts = {}
    for name, rows in tables.items():
        counts[name] = write_csv(out / name, rows)

    # Export Ground Truth as JSON as well for convenient evaluation ingestion
    (out / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")

    checksums = {}
    for name in tables:
        checksums[name] = hashlib.sha256((out / name).read_bytes()).hexdigest()

    manifest = {
        "generator_version": "2.0.0",
        "seed": seed,
        "scale": scale,
        "provenance": "Synthetically generated with deterministic RNG and domain business rules; zero confidential data.",
        "counts": counts,
        "sha256": checksums
    }
    (out / "source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({
        "output_dir": str(out),
        "seed": seed,
        "scale": scale,
        "counts": counts
    }, indent=2))
    return counts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic freight synthetic data generator")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter",
                        help="starter (fast demo) or full (100 carriers, 20k shipments, 15k invoices)")
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT, help="RNG seed for reproducibility")
    parser.add_argument("--out", default="data", help="Output directory path")
    args = parser.parse_args()
    generate(args.out, args.scale, args.seed)
