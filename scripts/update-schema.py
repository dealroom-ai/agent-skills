#!/usr/bin/env python3
"""Regenerate skills/dealroom-bigquery/references/schema.json from BigQuery.

Pulls column names, types and descriptions straight from
INFORMATION_SCHEMA (descriptions are the ones dbt persists via persist_docs),
so after a dbt run just execute this to refresh the skill's schema reference.

Usage:
    python3 scripts/update-schema.py           # rewrite schema.json + show diff
    python3 scripts/update-schema.py --check    # diff only, don't write (CI-friendly)

Requires the `bq` CLI, authenticated with read access to the project below.
schema.md is hand-written narrative and is NOT touched — the printed diff tells
you whether it needs a manual edit (new/removed tables or columns).
"""
import json, subprocess, sys, os
from pathlib import Path

PROJECT = "omega-dahlia-347111"
# dataset -> ordered list of tables the skill documents
TABLES = {
    "intelligence_unit": [
        "entities_iu", "funding_iu", "vc_funding_iu", "investors_iu",
        "people_iu", "people_organizations_iu", "timeseries_data_iu",
        "headcount_breakdown_iu", "web_traffic_iu", "news_iu", "jobs_iu",
        "dim_lists_iu", "dim_tags_iu", "dim_locations_iu", "dim_currency_rates_iu",
    ],
    "reporting_iu": ["power_law", "power_law_rising_star_usa"],
}

OUT = Path(__file__).resolve().parent.parent / "skills/dealroom-bigquery/references/schema.json"


def fetch(dataset, tables):
    in_list = ", ".join(f"'{t}'" for t in tables)
    sql = f"""
    SELECT p.table_name, p.field_path AS column_name, p.description, p.data_type
    FROM `{PROJECT}.{dataset}`.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS p
    JOIN `{PROJECT}.{dataset}`.INFORMATION_SCHEMA.COLUMNS c
      ON p.table_name = c.table_name AND p.column_name = c.column_name
    WHERE p.table_name IN ({in_list})
    ORDER BY p.table_name, c.ordinal_position, p.field_path
    """
    out = subprocess.run(
        ["bq", f"--project_id={PROJECT}", "query", "--use_legacy_sql=false",
         "--format=json", "--max_rows=100000", sql],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        sys.exit(f"bq query failed for {dataset}:\n{out.stderr}")
    return json.loads(out.stdout or "[]")


def build():
    rows = []
    for dataset, tables in TABLES.items():
        by_table = {}
        for r in fetch(dataset, tables):
            by_table.setdefault(r["table_name"], []).append({
                "table_name": r["table_name"],
                "column_name": r["column_name"],
                "description": r.get("description") or "",
                "data_type": r["data_type"],
            })
        for t in tables:  # preserve the configured table order
            rows.extend(by_table.get(t, []))
    return rows


def diff(old, new):
    key = lambda r: (r["table_name"], r["column_name"])
    o, n = {key(r): r for r in old}, {key(r): r for r in new}
    added = [k for k in n if k not in o]
    removed = [k for k in o if k not in n]
    changed = [k for k in n if k in o and (o[k]["data_type"], o[k]["description"]) != (n[k]["data_type"], n[k]["description"])]
    for label, ks in (("+ added", added), ("- removed", removed), ("~ changed", changed)):
        for t, c in sorted(ks):
            print(f"  {label}: {t}.{c}")
    return added, removed, changed


def main():
    check = "--check" in sys.argv
    old = json.loads(OUT.read_text()) if OUT.exists() else []
    new = build()
    print(f"Fetched {len(new)} columns across {sum(len(v) for v in TABLES.values())} tables.")
    a, r, c = diff(old, new)
    if not (a or r or c):
        print("No schema changes.")
        return
    print(f"\n{len(a)} added, {len(r)} removed, {len(c)} changed.")
    if a or r:
        print("NOTE: tables/columns added or removed — review references/schema.md narrative.")
    if check:
        sys.exit(1 if (a or r or c) else 0)
    OUT.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
