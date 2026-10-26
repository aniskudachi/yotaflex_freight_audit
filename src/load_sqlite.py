#!/usr/bin/env python3
"""Load CSV tables into SQLite database with primary keys, foreign keys, and typed indices."""
import argparse
import csv
import re
import sqlite3
from pathlib import Path

PKS = {
    "carrier": "carrier_id",
    "lane": "lane_id",
    "rate_card": "rate_id",
    "shipment": "shipment_id",
    "shipment_leg": "leg_id",
    "weight_measurement": "measurement_id",
    "accessorial": "accessorial_id",
    "freight_invoice": "invoice_id",
    "invoice_line": "line_id",
    "audit_exception": "exception_id",
    "credit_note": "credit_note_id",
    "audit_event_history": "event_id",
    "audit_results": "invoice_id",
    "credit_note_validation": "credit_note_id"
}

FKS = {
    "rate_card": [
        ("carrier_id", "carrier", "carrier_id"),
        ("lane_id", "lane", "lane_id")
    ],
    "shipment": [
        ("carrier_id", "carrier", "carrier_id"),
        ("lane_id", "lane", "lane_id"),
        ("rate_id", "rate_card", "rate_id")
    ],
    "shipment_leg": [
        ("shipment_id", "shipment", "shipment_id")
    ],
    "weight_measurement": [
        ("shipment_id", "shipment", "shipment_id")
    ],
    "accessorial": [
        ("shipment_id", "shipment", "shipment_id")
    ],
    "freight_invoice": [
        ("carrier_id", "carrier", "carrier_id"),
        ("source_rate_id", "rate_card", "rate_id")
    ],
    "invoice_line": [
        ("invoice_id", "freight_invoice", "invoice_id")
    ],
    "audit_exception": [
        ("invoice_id", "freight_invoice", "invoice_id"),
        ("carrier_id", "carrier", "carrier_id")
    ],
    "credit_note": [
        ("invoice_id", "freight_invoice", "invoice_id"),
        ("carrier_id", "carrier", "carrier_id")
    ]
}

def load(data_dir, db_path, outputs_dir="outputs"):
    d = Path(data_dir)
    dbp = Path(db_path)
    out_d = Path(outputs_dir)
    dbp.parent.mkdir(parents=True, exist_ok=True)

    if dbp.exists():
        dbp.unlink()

    con = sqlite3.connect(dbp)
    con.execute("PRAGMA foreign_keys=OFF")  # Loaded in order; enabled after load

    order = [
        "carrier.csv",
        "lane.csv",
        "rate_card.csv",
        "shipment.csv",
        "shipment_leg.csv",
        "weight_measurement.csv",
        "accessorial.csv",
        "freight_invoice.csv",
        "invoice_line.csv",
        "audit_exception.csv",
        "credit_note.csv",
        "audit_event_history.csv"
    ]

    loaded_tables = []

    # Load data files
    for name in order:
        p = d / name
        if not p.exists():
            continue
        table = re.sub(r"\W", "_", p.stem)
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            cols = reader.fieldnames or []
        if not cols:
            continue

        pk = PKS.get(table)
        definitions = []
        for c in cols:
            col_def = f'"{c}" TEXT'
            if c == pk:
                col_def += " PRIMARY KEY"
            definitions.append(col_def)

        for a, b, c in FKS.get(table, []):
            definitions.append(f'FOREIGN KEY("{a}") REFERENCES "{b}"("{c}")')

        con.execute(f'DROP TABLE IF EXISTS "{table}"')
        create_sql = f'CREATE TABLE "{table}" ({", ".join(definitions)})'
        con.execute(create_sql)

        if rows:
            placeholders = ",".join("?" for _ in cols)
            col_list = ",".join(f'"{c}"' for c in cols)
            con.executemany(
                f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})',
                [[r[c] for c in cols] for r in rows]
            )
        loaded_tables.append((table, len(rows)))

    # Also load audit result tables if they exist
    for out_name in ["audit_results.csv", "exceptions.csv", "credit_note_validation.csv", "audit_events.csv"]:
        op = out_d / out_name
        if not op.exists():
            continue
        table = re.sub(r"\W", "_", op.stem)
        with open(op, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            cols = reader.fieldnames or []
        if not cols:
            continue

        pk = PKS.get(table)
        definitions = [f'"{c}" TEXT' + (" PRIMARY KEY" if c == pk else "") for c in cols]
        con.execute(f'DROP TABLE IF EXISTS "{table}"')
        con.execute(f'CREATE TABLE "{table}" ({", ".join(definitions)})')
        if rows:
            placeholders = ",".join("?" for _ in cols)
            col_list = ",".join(f'"{c}"' for c in cols)
            con.executemany(
                f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})',
                [[r[c] for c in cols] for r in rows]
            )
        loaded_tables.append((table, len(rows)))

    # Create indices for query performance
    indices = [
        ("idx_shipment_carrier", "shipment", "carrier_id"),
        ("idx_shipment_lane", "shipment", "lane_id"),
        ("idx_rate_lookup", "rate_card", "carrier_id, lane_id, service"),
        ("idx_invoice_shipment", "freight_invoice", "shipment_id"),
        ("idx_lines_invoice", "invoice_line", "invoice_id"),
        ("idx_exceptions_invoice", "audit_exception", "invoice_id")
    ]
    for idx_name, tbl, cols in indices:
        try:
            con.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON "{tbl}" ({cols})')
        except Exception:
            pass

    con.commit()
    con.close()

    print(f"Loaded {len(loaded_tables)} tables into SQLite database at {dbp}:")
    for tbl, count in loaded_tables:
        print(f"  - {tbl}: {count} rows")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load CSV tables into SQLite database")
    parser.add_argument("--data", default="data", help="Input directory containing CSV tables")
    parser.add_argument("--db", default="outputs/freight_audit.db", help="Target SQLite database file")
    parser.add_argument("--outputs", default="outputs", help="Outputs directory for audit result tables")
    args = parser.parse_args()
    load(args.data, args.db, args.outputs)
