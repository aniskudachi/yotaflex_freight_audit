#!/usr/bin/env python3
"""Export SQLite database or CSV tables as a standalone SQL seed script (freight_audit_seed.sql)."""
import argparse
import csv
import re
from pathlib import Path

def sql_escape(v):
    if v is None or v == "":
        return "NULL"
    escaped = str(v).replace("'", "''")
    return f"'{escaped}'"

def export_sql(data_dir, out_file):
    d = Path(data_dir)
    out_p = Path(out_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)

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

    sql_statements = [
        "-- ====================================================================",
        "-- Freight Invoice Validation & Audit — Standalone SQL Seed Script",
        "-- Auto-generated for relational database initialization",
        "-- ====================================================================",
        "BEGIN TRANSACTION;",
        ""
    ]

    for fname in order:
        p = d / fname
        if not p.exists():
            continue
        table_name = re.sub(r"\W", "_", p.stem)
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            cols = reader.fieldnames or []

        if not cols:
            continue

        sql_statements.append(f"-- Table: {table_name}")
        sql_statements.append(f"DROP TABLE IF EXISTS {table_name};")
        col_defs = [f'"{c}" TEXT' for c in cols]
        sql_statements.append(f'CREATE TABLE {table_name} ({", ".join(col_defs)});')

        if rows:
            for r in rows:
                val_list = [sql_escape(r[c]) for c in cols]
                col_list = ", ".join(f'"{c}"' for c in cols)
                sql_statements.append(f'INSERT INTO {table_name} ({col_list}) VALUES ({", ".join(val_list)});')
        sql_statements.append("")

    sql_statements.append("COMMIT;")
    sql_statements.append("")

    out_p.write_text("\n".join(sql_statements), encoding="utf-8")
    print(f"Exported SQL seed script to {out_p} ({len(sql_statements)} lines)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export SQL seed script from CSV data")
    parser.add_argument("--data", default="data", help="Input directory containing CSV tables")
    parser.add_argument("--out", default="outputs/freight_audit_seed.sql", help="Output SQL script path")
    args = parser.parse_args()
    export_sql(args.data, args.out)
