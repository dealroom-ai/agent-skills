#!/usr/bin/env python3
"""Regenerate skills/dealroom-bigquery/references/schema.json from dbt schema.yml.

Column names + descriptions come from the dbt repo's schema.yml (the source of
truth you maintain, with the richest comments and "how it works" notes, and up to
date with `main` before a prod run). Data types are enriched from live BigQuery
where the column is already built; columns declared in yml but not yet in BigQuery
get an empty data_type and are reported so you know a `dbt run` is still pending.

Usage:
    python3 scripts/update-schema.py                    # rewrite schema.json + diff
    python3 scripts/update-schema.py --check            # diff only, don't write
    python3 scripts/update-schema.py --no-types         # skip BigQuery, yml only
    python3 scripts/update-schema.py --dbt-repo PATH     # point at your dbt clone

The dbt repo path resolves from --dbt-repo, then $DBT_REPO, then a few common
locations. schema.md is hand-written narrative and is NOT touched.
"""
import json, subprocess, sys, os
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: python3 -m pip install --user pyyaml")

PROJECT = "omega-dahlia-347111"
# dataset -> (schema.yml path within the dbt repo, ordered table list)
SOURCES = {
    "intelligence_unit": (
        "dbt/models/intelligence_unit/schema.yml",
        ["entities_iu", "funding_iu", "vc_funding_iu", "vc_combined_rounds_iu",
         "investors_iu", "people_iu",
         "people_organizations_iu", "timeseries_data_iu", "headcount_breakdown_iu",
         "web_traffic_iu", "news_iu", "jobs_iu", "dim_lists_iu", "dim_tags_iu",
         "dim_locations_iu", "dim_currency_rates_iu"],
    ),
    "reporting_iu": (
        "dbt/models/reporting_iu/schema.yml",
        ["power_law", "power_law_rising_star_usa"],
    ),
}

OUT = Path(__file__).resolve().parent.parent / "skills/dealroom-bigquery/references/schema.json"


def find_dbt_repo():
    for cand in (
        next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--dbt-repo=")), None),
        os.environ.get("DBT_REPO"),
        "~/Documents/dealroom/repos/data-dbt-service",
        "~/Documents/dealroom-repos/data-dbt-service",
    ):
        if cand and (p := Path(cand).expanduser()).joinpath("dbt/dbt_project.yml").exists():
            return p
    sys.exit("dbt repo not found. Pass --dbt-repo=/path/to/data-dbt-service or set $DBT_REPO.")


def cols_from_yml(repo):
    """[(table, column, description)] in configured table + yml column order."""
    rows = []
    for _, (rel, tables) in SOURCES.items():
        models = {m["name"]: m for m in yaml.safe_load((repo / rel).read_text())["models"]}
        for t in tables:
            if t not in models:
                print(f"  ! {t} not in {rel}")
                continue
            for c in models[t].get("columns", []):
                rows.append((t, c["name"], (c.get("description") or "").strip()))
    return rows


def bq_types():
    """(table, column) -> data_type for every built column, in ordinal order."""
    types = {}
    for dataset in SOURCES:
        sql = f"""SELECT p.table_name, p.field_path, p.data_type
        FROM `{PROJECT}.{dataset}`.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS p
        JOIN `{PROJECT}.{dataset}`.INFORMATION_SCHEMA.COLUMNS c
          ON p.table_name = c.table_name AND p.column_name = c.column_name
        ORDER BY p.table_name, c.ordinal_position, p.field_path"""
        out = subprocess.run(
            ["bq", f"--project_id={PROJECT}", "query", "--use_legacy_sql=false",
             "--format=json", "--max_rows=100000", sql],
            capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit(f"bq query failed for {dataset} (try --no-types):\n{out.stderr}")
        for r in json.loads(out.stdout or "[]"):
            types[(r["table_name"], r["field_path"])] = r["data_type"]
    return types


def build(repo, use_types):
    """Union of yml-declared and BigQuery-built columns. yml supplies the
    description (your comments); BigQuery supplies the data_type. Nothing that
    exists in either source is dropped."""
    all_tables = [t for _, (_, ts) in SOURCES.items() for t in ts]
    yml_desc, yml_order = {}, {t: [] for t in all_tables}
    for t, c, desc in cols_from_yml(repo):
        yml_desc[(t, c)] = desc
        yml_order[t].append(c)
    types = bq_types() if use_types else {}
    bq_order = {t: [] for t in all_tables}
    for (t, c) in types:
        if t in bq_order:
            bq_order[t].append(c)

    rows, pending, undocumented = [], [], []
    for t in all_tables:
        seen = set()
        # yml columns first, in yml order; then any BQ-only columns
        for c in yml_order[t] + [c for c in bq_order[t] if c not in yml_order[t]]:
            if c in seen:
                continue
            seen.add(c)
            in_yml, dt = (t, c) in yml_desc, types.get((t, c), "")
            if in_yml and use_types and not dt:
                pending.append((t, c))       # declared but not built yet
            if not in_yml:
                undocumented.append((t, c))  # built but not documented in yml
            rows.append({"table_name": t, "column_name": c,
                         "description": yml_desc.get((t, c), ""), "data_type": dt})
    return rows, pending, undocumented


def diff(old, new):
    key = lambda r: (r["table_name"], r["column_name"])
    o, n = {key(r): r for r in old}, {key(r): r for r in new}
    a = [k for k in n if k not in o]
    r = [k for k in o if k not in n]
    c = [k for k in n if k in o and (o[k]["data_type"], o[k]["description"]) != (n[k]["data_type"], n[k]["description"])]
    for label, ks in (("+ added", a), ("- removed", r), ("~ changed", c)):
        for t, col in sorted(ks):
            print(f"  {label}: {t}.{col}")
    return a, r, c


def main():
    check = "--check" in sys.argv
    use_types = "--no-types" not in sys.argv
    repo = find_dbt_repo()
    print(f"dbt repo: {repo}")
    old = json.loads(OUT.read_text()) if OUT.exists() else []
    new, pending, undocumented = build(repo, use_types)
    print(f"Parsed {len(new)} columns from schema.yml"
          + (f"; {len(pending)} not yet built in BigQuery" if use_types else " (types skipped)") + ".")
    a, r, c = diff(old, new)
    if pending:
        print("\nDeclared in yml but NOT yet in BigQuery (run/deploy dbt to build):")
        for t, col in sorted(pending):
            print(f"  · {t}.{col}")
    if undocumented:
        print("\nIn BigQuery but NOT documented in schema.yml (consider adding docs):")
        for t, col in sorted(undocumented):
            print(f"  · {t}.{col}")
    if not (a or r or c):
        print("\nNo changes to schema.json.")
        return
    print(f"\n{len(a)} added, {len(r)} removed, {len(c)} changed.")
    if check:
        sys.exit(1)
    OUT.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
