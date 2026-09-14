---
name: dealroom-bigquery
description: >-
  Write CORRECT SQL against Dealroom's BigQuery warehouse (`intelligence_unit`) and run it with
  the `run_bigquery` tool. This is the WAREHOUSE half of the correctness layer; `api-intelligence-unit`
  is the REST API half. Read this BEFORE writing any SQL: it carries the authoritative column list
  (`schema.json`, 20 tables — Grep it, never Read it whole), the entity model and join paths (`schema.md`), the default VC-funding
  and enterprise-value exclusions the platform applies, the deduplication patterns, and the recurring
  mistakes that silently return a plausible wrong number. Trigger whenever a question is going to be
  answered from the warehouse rather than the REST API — anything reaching for people, founders,
  jobs, news, web traffic, headcount breakdowns, LP relationships, investor power-law rankings, or a
  join/grain the API cannot express. Also trigger before running ANY `run_bigquery` call, including a
  schema-discovery one, and when a warehouse query returned something that looks wrong. Prefer the
  REST API tools when they can answer the question: they are faster, cheaper and already carry these
  invariants in code.
---

# Dealroom BigQuery — writing SQL that returns the right number

This skill has two jobs in the workbench:

1. **Write SQL** against the `intelligence_unit` dataset and run it with `run_bigquery`.
2. **Review your own SQL** before and after running it, against the recurring error patterns below.

**When to be here at all.** The REST API tools (`run_api_query`, `rank_entities`, `aggregate_rounds`
and the rest) are the default: they are faster, cheaper, and the platform's default filters are
enforced in code rather than by you remembering them. Reach for the warehouse only when the API
genuinely cannot answer — people and founders, jobs, news, web traffic, headcount breakdowns, LP
relationships, investor power-law rankings, or a join/grain the API has no endpoint for. If you
find yourself writing SQL that reproduces something `rank_companies_by_funding` already does, stop
and use the tool.

**Cost and shape of a `run_bigquery` call.** Every query is dry-run first and rejected if it would
scan past the byte ceiling, so narrow column lists and a real `WHERE` clause are not style advice —
an unfiltered `SELECT *` will simply fail. The full result is cached server-side and shown to the
user as a table; you get back the schema, the row count and a few sample rows. Do not ask for large
`maxSampleRows`; you are shape-checking column names and types, not reading the data.

**First step — load the schema references, CHEAPLY.**

Read `schema.md` (a few hundred lines, one Read). Then **Grep `schema.json`; do NOT Read it.** It is several thousand lines
and the Read tool returns at most 2,000 per call, so reading it whole costs two calls and ~30k tokens
of context before you have written a single line of SQL — on a latency-sensitive turn that is the
difference between an answer in seconds and an answer in minutes.

It is a flat array of `{table_name, column_name, description, data_type}` records, which is exactly
what Grep is for:

- every column on a table: \`Grep("\\"table_name\\": \\"vc_funding_iu\\"", ".claude/skills/dealroom-bigquery/schema.json")\`
- verify one column exists: \`Grep("\\"column_name\\": \\"amount_usd\\"", ".claude/skills/dealroom-bigquery/schema.json")\`

Read a slice of `schema.json` with offset/limit only when you need a whole table's block at once.

**Discovery vs verification — do not confuse the two greps.** `"column_name": "x"` only CONFIRMS a name you already typed; it can never surface a column you didn't think of. For discovery use **`schema.md` → "Complete Column Index"** (the tail of the file you just read): every column on all 20 tables, names only. **Scan it before telling the user the warehouse cannot answer something** — that failure mode has already happened once, on `entities_iu.flg_is_exited` / `year_of_exit`, which were in `schema.json` the whole time.

- **`schema.json`** — authoritative column list for all 20 tables (every column + nested STRUCT field, with data types and descriptions). All tables now live in the single **`intelligence_unit`** dataset, qualified as `` `omega-dahlia-347111.intelligence_unit.<table>` ``. Core tables carry an `_iu` suffix: `entities_iu`, `funding_iu`, `vc_funding_iu`, `vc_combined_rounds_iu`, `investors_iu`, `vc_investor_returns_iu`, `people_iu`, `people_organizations_iu`, `jobs_iu`, `news_iu`, `dim_lists_iu`, `timeseries_data_iu`, `headcount_breakdown_iu`, `web_traffic_iu`, `dim_locations_iu`, `dim_tags_iu`, `dim_currency_rates_iu`. The two power-law tables are listed in `schema.json` for column reference but live in a **separate `reporting_iu` dataset** — qualify them as `` `omega-dahlia-347111.reporting_iu.power_law` `` / `` `omega-dahlia-347111.reporting_iu.power_law_rising_star_usa` `` (no `_iu` suffix on the table name itself). (⚠ `vc_funding_investors` was previously documented but is **not deployed** in production — use the `funding_investors` array on `funding_iu`/`vc_funding_iu` instead; see `schema.md`.) `headcount_breakdown_iu` and `web_traffic_iu` are **new** tables in this schema generation. Also included is the curated **`main_hq_regions`** table (not a dbt model; canonical HQ-region dimension — see `schema.md`). Every column name used in a query must appear in this file — never guess. If a column name in your draft query isn't in `schema.json`, stop and verify before continuing.
- **`schema.md`** — narrative context: the entity model, join paths, enum values, INT↔label mappings, geography/region logic, critical field corrections, and query gotchas. Its tail carries the **Complete Column Index** — every column name on every table, generated from `schema.json`; that is your discovery surface.

Do not rely on memory alone — but verify by Grep, not by bulk reading. "Every column must appear in
schema.json" is a rule about checking each column you use, not an instruction to load the file.

> **⚠ Migration note.** The dataset moved to a canonical entity model. Entities are classified by **`entity_type`**
> (`'person'`/`'organization'`) + **`organization_subtype`** (`'company'`/`'university'`/`'gov_ngo'`/`'fund'`) +
> role flags. The old `flg_is_company`/`flg_is_person`/`flg_is_organization`/`flg_is_university` and `type`/`type_desc`
> columns are **gone**. The `*_desc` text columns still exist but are being retired — **prefer the coded INT partners**:
> `growth_stage` and `company_status` (on `entities_iu`), and `gender` (on `people_iu`, alongside `gender_desc`). Tables refresh **hourly**.

---

## How this reads in the workbench

The user is not reading your SQL — they are reading a table, a chart and your closing answer. So:

- **Do not paste the SQL into the chat answer.** It is already on the tool call, and the workbench
  shows the result. Say in one line what population you counted and which filters you applied
  (for example "VC rounds, outside-tech and mature-stage excluded, 2015 onwards"), because that
  sentence is what makes the number checkable.
- **State the definition you chose whenever more than one was available** — which "Europe", HQ vs
  founding location, valuation source. A number without its definition is not an answer.
- **Run the companion sanity check yourself** (PART 4) rather than handing it to the user. You have
  `run_bigquery`; a second cheap aggregate query is a few seconds. If a check fails, say so and
  either fix the query or caveat the number. Do not quietly present a figure a check contradicted.

---

# PART 1 — Writing SQL Queries

Use this when the user wants Claude to write the SQL directly.

## Step 1: Clarify the question

Before writing SQL, make sure you understand:
- **What entity type?** Companies (`entity_type='organization' AND organization_subtype='company'`), funds, universities, gov/NGOs, or persons (`entity_type='person'`)?
- **What geography?** HQ region (`loc.continent` — single, clean) vs a specific named region from `loc.country_region[]` (Nordics, DACH, "Europe", …)? See Step 3 → Geography. Use `country_region` for a *named* sub-continental/curated region; use `continent` for a clean continental partition.
- **What time range?** Remember: `funding_iu`/`vc_funding_iu` use integer `year`/`month` columns, not date fields.
- **What metric?** Funding amounts, counts, employee growth, valuations, exits, job openings?
- **Row-level or aggregate?** This affects the deduplication strategy (see Step 3).

If the user's question is clear enough, proceed directly — don't over-interview.

## Step 2: Apply default filters

**Defaults apply to two query categories: VC funding and enterprise value (EV).** For all other query types, apply no defaults unless the user explicitly asks.

### VC funding queries — always apply these two exclusions

Any query that pulls VC funding data (using `vc_funding_iu`, or `funding_iu` with `flg_is_vc_round = TRUE`):

**1. Exclude outside tech:**
```sql
AND NOT EXISTS (
  SELECT 1 FROM UNNEST(e.sectors) s
  WHERE LOWER(s.name) = 'outside tech'
)
```

**2. Exclude mature growth stage** (coded INT — `4` = 'Mature'):
```sql
AND (e.growth_stage IS NULL OR e.growth_stage != 4)
```

**`flg_is_vc_round = TRUE` is the VC-round selection.** It already excludes grants, SPAC private placements and debt by definition (owner, 2026-08-25), so `round NOT IN ('SPAC PRIVATE PLACEMENT', 'GRANT')` on top of it is **redundant — do not add it** (a hand-listed set of round names also silently misses variants the flag already handles). The one exception: the flag does **not** exclude `CONVERTIBLE` rounds (convertible notes are VC financing; ~10.6k are flagged VC), so add `AND round != 'CONVERTIBLE'` only if an analysis specifically needs to drop them. On `funding_iu`, state `flg_is_vc_round = TRUE` explicitly; `vc_funding_iu` carries the same column, where stating it is harmless.

These match the Dealroom platform defaults for VC funding views. `vc_funding_iu` already pre-filters outside tech and mature at the table level, so those two are belt-and-braces when using `vc_funding_iu` but still worth including for clarity.

**Exception — `vc_combined_rounds_iu` needs none of them.** Round-size (median/quartile) queries run off `vc_combined_rounds_iu`, which has its whole population baked in at build time: verified VC rounds only (exits excluded), startups founded ≥ 1990, Mature excluded, `amount_usd >= $1M` floor. **Do not re-apply these exclusions** — you'd be filtering an already-filtered table. See Common Query Templates → "Median / quartile VC round size by stage".

### Enterprise value (EV) queries — always apply these three exclusions

**Scope — what counts as an EV query:** any query that filters, sorts, or aggregates on a valuation field (`latest_valuation_usd`, `latest_valuation_eur`, the `valuations` array, `timeseries_data.valuation_usd`), or uses `flg_is_unicorn` (unicorn status is itself a valuation threshold). Exit valuations live separately on `funding.valuation_usd` with `flg_is_exit = TRUE` and do not take these defaults.

#### ⚠ Valuation source — for COMBINED/aggregate EV, use the yearly time series, NOT `latest_valuation_usd`

The Dealroom platform's "Combined EV" (and its EV-over-time chart) is the **sum of `timeseries_data_iu.valuation_usd` for a given `year`** — Dealroom's forward-filled / estimated per-year valuations. **`entities_iu.latest_valuation_usd` is a single stale scalar and systematically UNDERCOUNTS** the platform figure (measured **~4–10% low across a 10-country VC-backed test**; e.g. Israel 2026 combined EV = **$625.9B** via the time series vs **$572.8B** via `latest_valuation_usd`, matching the app at $626B). The undercount is not the company set (nearly identical) — it's the per-company value: the time series grows/forward-fills the last disclosed valuation, `latest_valuation_usd` does not.

**Rule:**
- **Combined / aggregate EV, EV per country/region, EV-over-time → `timeseries_data_iu.valuation_usd` filtered to the target `year`.** For "current combined EV", use the latest year present. Verified grain: **one row per `entity_id` per `year`** — safe to `SUM` directly (no month-level dup).
- **`latest_valuation_usd` → only for a single company's current headline valuation, or company-level ranking/sorting.** Do not use it to sum an ecosystem's EV.

```sql
-- Combined EV by country for a given year (mirrors the platform stat)
WITH ev_year AS (
  SELECT entity_id, valuation_usd
  FROM `omega-dahlia-347111.intelligence_unit.timeseries_data_iu`
  WHERE year = 2026                              -- change year; whole series → EV-over-time chart
)
SELECT cc.country,
  COUNT(DISTINCT cc.id)   AS company_count,      -- ALL matching companies (incl. unvalued)
  SUM(ev.valuation_usd)   AS combined_ev_usd
FROM company_country cc                            -- filtered entities, one row per (id, country)
LEFT JOIN ev_year ev ON ev.entity_id = cc.id      -- LEFT JOIN: never drops the company from the count
GROUP BY cc.country ORDER BY combined_ev_usd DESC
```

**Company count vs valued count:** use a `LEFT JOIN` so the company count includes companies with no valuation (the platform's "# companies" does). Do **not** filter `valuation_usd IS NOT NULL` on the entity set — that conflates "matches the filters" with "has a valuation" and undercounts the company total.

**1. Exclude outside tech:**
```sql
AND NOT EXISTS (
  SELECT 1 FROM UNNEST(e.sectors) s
  WHERE LOWER(s.name) = 'outside tech'
)
```

**2. Exclude mature growth stage** (coded INT — `4` = 'Mature'):
```sql
AND (e.growth_stage IS NULL OR e.growth_stage != 4)
```

**3. Exclude pre-1990 founding year (strict):**
```sql
AND e.launch_year >= 1990
```
Deliberately strict — companies with a missing `launch_year` are dropped. This is a departure from the skill's general NULL-handling rule; the intent is to guarantee a clean post-1990 cohort for EV analysis.

**Do NOT exclude the 'mature company' sector tag.** It used to be a fourth default here and was removed (owner, 2026-08-25): the platform's EV view never applied it, so it made workbench numbers diverge from the app for no reason. The tag still exists in the taxonomy — apply it only when the user explicitly asks for it, and say so when you do.

> **⚠ These three defaults are NOT the platform's full EV view chip-set.** When a user is replicating a specific Dealroom app view (they'll often show the filter chips), match *their* chips, not these defaults. A typical platform EV view uses: `outside tech`, `mature` (growth stage), **`closed`** (`company_status != 3`), **government nonprofit** (already excluded by `organization_subtype = 'company'`), **service provider** (see below), `founded since 1990`, and `VC Backed` (`flg_is_vcbacked = TRUE`). So to mirror a platform view you usually just **add `company_status != 3`** (and `flg_is_vcbacked = TRUE` when the view carries the VC Backed chip). Keep the three defaults for a generic "EV analysis" ask with no platform view to match.
>
> **`service provider` has no field in this schema.** The platform's `company_type = service provider` exclusion maps to the retired `type` column; `organization_subtype` only has `company / university / gov_ngo / investor`, and the literal `service provider` *sector tag* covers just ~154 entities (not the same population). Leave it unexcluded and note the residual (~0.2%, and effectively nil once `flg_is_vcbacked = TRUE` is required, since service providers are rarely VC-backed).

### Mixed queries (both VC funding and EV)

For queries that touch both (e.g. "unicorns by VC raised"), take the **union of exclusions** — outside tech, mature stage, `launch_year >= 1990`, plus `flg_is_vc_round = TRUE` on the funding rows. The VC and EV exclusions overlap on outside tech and mature stage; the EV-only addition (`launch_year >= 1990`) just narrows further.

### Other query types — no default filters

Do not apply `flg_is_startup = TRUE` or the mature/outside tech exclusions on queries that aren't VC or EV. Let the user specify what they want filtered.

**`flg_is_verified` is a ROUNDS concept — never a company filter.** `entities_iu.flg_is_verified` exists in the schema but must not be used to filter companies, on any query type. Verified-ness belongs to funding rounds (`funding_iu` / `vc_funding_iu` / the `fundings[]` array), and even there apply it only when the user explicitly asks for verified rounds.

### Conditional — exclude closed companies

When the user says "exclude closed" or similar, use the coded INT (`3` = 'Closed'):
```sql
AND (e.company_status IS NULL OR e.company_status != 3)
```
Never use `= 1` / `= 'Operational'` to mean "still alive" — that also excludes Acquired (2) **and** Low Activity (4). `company_status` values: `0`=NULL/persons, `1`=Operational, `2`=Acquired, `3`=Closed, `4`=Low Activity.

## Step 3: Apply established SQL patterns

**Entity classification — the new model:**
- Companies: `e.entity_type = 'organization' AND e.organization_subtype = 'company'`.
- Funds / universities / gov-NGOs: `organization_subtype` `'fund'` / `'university'` / `'gov_ngo'`.
- Persons: `e.entity_type = 'person'`.
- Investors: `e.flg_is_investor = TRUE` (a role flag; applies to persons and organizations, independent of subtype).
- Do **not** use `flg_is_company` / `flg_is_person` / `flg_is_organization` / `flg_is_university` (removed) or `type`/`type_desc` (removed).
- `flg_is_startup` is opt-in — only when the user explicitly wants to exclude non-startups; don't apply by default.

**Location deduplication — ROW_NUMBER() vs EXISTS:**

Use the right pattern depending on whether the output is row-level or aggregate:

- **Row-level output** (list of companies, Connected Sheets export) → use `ROW_NUMBER()` to assign each company to one region, prioritising HQ over founding:
```sql
ROW_NUMBER() OVER (
  PARTITION BY e.id
  ORDER BY CASE WHEN loc.flg_is_hq THEN 1 WHEN loc.flg_is_founding THEN 2 ELSE 3 END
) AS loc_rank
-- Then filter WHERE loc_rank = 1
```

- **Aggregate counts** ("how many companies in Europe") → use `EXISTS` to avoid losing companies that were founded in one region but moved HQ to another:
```sql
WHERE EXISTS (
  SELECT 1 FROM UNNEST(e.locations) loc
  WHERE (loc.flg_is_hq = TRUE OR loc.flg_is_founding = TRUE)
    AND 'Europe' IN UNNEST(loc.country_region)
)
```
`ROW_NUMBER()` forces single-region assignment and can lose 10–15 companies in a typical European analysis.

- **Per-country / per-region breakdown that must match the platform** (e.g. "combined EV by country" across a country list) → **do NOT use `ROW_NUMBER()`.** The Dealroom app uses **`founding_or_hq anyof`**: a company counts under *every* country/region where it has founding **or** HQ. Force each company to one country and you pull founding-abroad companies out of their founding ecosystem, undercounting the smaller ones. Use per-(company, region) dedup instead:
```sql
SELECT DISTINCT e.id, LOWER(loc.country) AS country
FROM `omega-dahlia-347111.intelligence_unit.entities_iu` e, UNNEST(e.locations) loc
WHERE (loc.flg_is_hq = TRUE OR loc.flg_is_founding = TRUE)
  AND LOWER(loc.country) IN (/* target list */)
  -- + entity filters
```
**Trade-off:** a company with founding + HQ in two different target countries appears in both, so the per-country column **does not sum to a unique grand total** — that's correct for platform-matching per-country stats. If you specifically need a de-duplicated grand total, take `COUNT(DISTINCT id)` / sum EV over the distinct entity set separately (or fall back to `ROW_NUMBER()` single-assignment for the total only). Quantify the overlap with a sanity check (`COUNTIF(n_countries > 1)`).

**Geography — HQ region vs other (membership) regions:**

There are two distinct notions of "region" on `loc` — keep them separate (full detail in `schema.md` → Geography):

- **`loc.continent` = the single, canonical HQ macro-region.** 7 clean, mutually-exclusive values: `North America`, `Europe`, `Asia`, `Oceania`, `South America`, `Africa`, `Decentralised`. Use this for "the HQ region" and for a clean continental partition. It is *geographic* — Israel and Türkiye are `Asia`.
- **`loc.country_region[]` = a ~77-value membership grab-bag** (macro-regions + blocs like EU27/OECD/G20/NATO + sub-regions like Nordics/DACH/Benelux + income tiers). A country belongs to ~10–19 of these. Use it **only by filtering to an exact named region** — **never** unnest-and-group the whole array (overlapping memberships triple-count).

**Three "Europe" definitions** — be explicit about which: `continent='Europe'` (excludes Türkiye **and** Israel); `'Europe'` ∈ `country_region` (includes Türkiye, excludes Israel); `'Europe incl Israel'` ∈ `country_region` (includes both). **Default to the plain `country_region` value `'Europe'`** when the user just says "Europe" — and state which definition you used. For region comparisons (e.g. Nordics vs rest of Europe), confirm the definition with the user rather than assuming, since it can materially move the result.

**Platform-style region export** — one `hq_region` (continent) + one `hq_other_regions` (the array):
```sql
SELECT
  loc.country,
  ANY_VALUE(loc.continent)         AS hq_region,
  ARRAY_AGG(DISTINCT r ORDER BY r) AS hq_other_regions
FROM `omega-dahlia-347111.intelligence_unit.entities_iu` e,
  UNNEST(e.locations) loc,
  UNNEST(loc.country_region) r
WHERE loc.flg_is_hq = TRUE
  AND loc.country IS NOT NULL
GROUP BY loc.country
ORDER BY loc.country
```
No `dim_locations_iu` join is needed to resolve region names — `entities.locations` already carries them.

**Default location scope depends on query type:**

| Query type | Default scope | Reasoning |
|---|---|---|
| VC funding | **HQ-only** | Matches Dealroom platform default for VC flow; a round is attributed to where the company is headquartered at the time. |
| Enterprise value (EV) | **HQ or founding** | Captures "value originated here" — unicorns founded in a country that later moved HQ still count for the ecosystem. |
| Mixed (both) | **HQ or founding** | Entity-scope question dominates funding-attribution question. |
| Other | Specify based on user intent; default to HQ or founding if unclear. | — |

Override when the user explicitly asks for a different scope.

**Dedup implication:** with VC queries defaulting to HQ-only, row-level VC output doesn't need `ROW_NUMBER()` — a simple `WHERE loc.flg_is_hq = TRUE` in the UNNEST join gives one row per company. `ROW_NUMBER()` is only needed for row-level output that includes founding locations (EV, mixed, explicit HQ+founding).

**VC funding fallback** — When calculating total VC raised per company, individual rounds may be incomplete:
```sql
COALESCE(NULLIF(SUM(f.amount_usd), 0), e.total_vc_funding_usd)
```

**Deep tech filtering** — Two definitions, NOT interchangeable:

| Term | Array | Filter | Companies |
|---|---|---|---|
| Deep tech | `technologies` | `id = 6` or `LOWER(name) = 'deep tech'` | ~54,700 |
| Deep tech + life sciences | `sectors` | `LOWER(name) = 'dt and ls'` | ~75,500 |

The ~40% gap materially changes any analysis. Always clarify which definition the user means. Never search `sectors` for "deep tech" — it returns 0 rows. Note `technologies` id=6 'Deep Tech' is distinct from id=10 'Deep Learning' and id=2 'Artificial Intelligence'.

**Time range filtering on funding:**
```sql
-- "Last 12 months" using year/month integers:
WHERE (f.year > EXTRACT(YEAR FROM DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH))
   OR (f.year = EXTRACT(YEAR FROM DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH))
       AND f.month >= EXTRACT(MONTH FROM DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH))))
-- NEVER use f.timecreate (DB timestamp) or f.announced_on (doesn't exist)
```

**Round stage — prefer `standardised_round_label` over raw `round`:**
- **`standardised_round_label` is Dealroom's unified, definition-based *true stage*** (PRE-SEED, MICRO-SEED, SEED, SEED+, SEED EXTENSION, SERIES A … SERIES F, plus the `SERIES x EXTENSION` rounds). It re-derives the real stage from round size + time-since-founding, so **it's the field to use for any cross-round / cross-company stage comparison.** See `schema.md` → "Standardised rounds" for the full methodology.
- **`round` is the self-reported round name — largely marketing, and does NOT reliably reflect the true stage** (a self-labelled "Series A" may really be a Seed by size/timing). Use `round` only for event types *outside* the standardised stage taxonomy — exits (or `flg_is_exit`), grants, debt — or when you explicitly want the self-reported label.
- **A NULL `standardised_round_label` means the round was deliberately not classified as a standard stage** (it didn't meet the size/timing definition, or isn't a VC stage event). For stage analysis, **exclude NULLs — do NOT backfill from raw `round`**, which would re-introduce the marketing labels the standardisation removes.
```sql
-- Stage analysis / comparison: filter on the standardised label.
WHERE LOWER(f.standardised_round_label) IN ('series a', 'series a extension')
-- (NULL labels are excluded by this — that's correct; they aren't a standardised Series A.)
```
- Coverage (labeled share by self-reported `round`): SERIES A 63% · B 74% · C 81% · D 83% · E 85%; lower for seed/angel; 0% on exits/grants/debt. The unlabeled remainder is **deliberate** (didn't meet the definition), not missing data.

**Funding table & flag usage:**
- `vc_funding_iu` = pre-filtered VC rounds, excludes outside tech + mature. No exit data.
- `funding_iu` = everything. Exit data (`flg_is_exit = TRUE`) lives ONLY here.
- `flg_is_vc_round = TRUE` for VC queries. NOT `flg_is_funding_round` (which includes grants, debt, convertibles).
- `flg_is_funding_round AND flg_is_vc_round` is redundant — second alone suffices.
- New round flags **on `funding_iu` and `entities.fundings` only — NOT on `vc_funding_iu`**: `flg_is_vc_backed_round` (VC-backed defining round), `flg_is_pe_round` (BUYOUT / GROWTH EQUITY NON VC).

**Exits:**
```sql
-- For median exit valuation:
APPROX_QUANTILES(f.valuation_usd, 2)[OFFSET(1)] AS median_valuation_usd
-- Exits require: flg_is_exit = TRUE, funding table (not vc_funding)
-- Exit round types: ACQUISITION, IPO, BUYOUT, SPAC IPO
```
Entity-level shortcuts now exist: `e.flg_is_exited` (has ≥1 exit) and `e.year_of_exit` — use for "exited companies" filters without joining `funding_iu`.

**⚠ Acquisition DIRECTION — "of" vs "by" flips the join. Read the phrasing before writing SQL.**
An `flg_is_exit = TRUE AND round = 'ACQUISITION'` row on `funding_iu` links two sides:
- **`funding_iu.entity_id` = the TARGET** — the company that got acquired.
- **`funding_iu.funding_investors[].bobject_investor_id` = the ACQUIRER(s)** — the buyer. Verified empirically: on ACQUISITION rows these parties are the acquiring companies (`flg_is_investor = TRUE`; e.g. American Express→TheFork, Rocket Software→Vertica, Otovo→Green Panel), **not** the target's old VCs. `bobject_investor_id` joins to `entities_iu.id`.

Map the analyst's wording to the side:
- **"acquisitions/exits OF company X"** → X is the TARGET → join `f.entity_id = c.id`.
- **"acquisitions BY company X" / "M&A X made" / "X acquiring companies globally"** → X is the ACQUIRER → `UNNEST(f.funding_investors) inv` then join `c.id = inv.bobject_investor_id`; leave the TARGET's geography UNFILTERED (that is the "globally" part); count distinct deals with `COUNT(DISTINCT f.id)`.

Either direction is an **exits query — NOT a VC-funding or EV query**, so the default exclusion packs do **not** auto-apply. Scope the company cohort deliberately (both templates below share it): `entity_type='organization'` + `organization_subtype='company'` + `flg_is_vcbacked = TRUE`; exclude `'outside tech'` (VC-backed = the tech universe); **do NOT apply the mature growth-stage exclusion** (`growth_stage != 4` wrongly drops mature companies that exited/acquired); Europe via **HQ or founding** with `EXISTS`.
```sql
-- OF-SIDE: global acquisitions OF European VC-backed companies (they GOT acquired), by year
WITH euro_vc_companies AS (
  SELECT e.id
  FROM `omega-dahlia-347111.intelligence_unit.entities_iu` e
  WHERE e.entity_type = 'organization' AND e.organization_subtype = 'company'
    AND e.flg_is_vcbacked = TRUE
    AND NOT EXISTS (SELECT 1 FROM UNNEST(e.sectors) s WHERE LOWER(s.name) = 'outside tech')
    AND EXISTS (SELECT 1 FROM UNNEST(e.locations) loc
                WHERE (loc.flg_is_hq = TRUE OR loc.flg_is_founding = TRUE)
                  AND 'Europe' IN UNNEST(loc.country_region))   -- incl. Türkiye, excl. Israel
  GROUP BY e.id
)
SELECT f.year,
  COUNT(*)                    AS acquisitions,        -- acquisition EVENTS
  COUNT(DISTINCT f.entity_id) AS companies_acquired
FROM `omega-dahlia-347111.intelligence_unit.funding_iu` f
JOIN euro_vc_companies c ON f.entity_id = c.id        -- the European company IS the TARGET
WHERE f.flg_is_exit = TRUE AND f.round = 'ACQUISITION' AND f.year >= 2010
GROUP BY f.year ORDER BY f.year;
```
```sql
-- BY-SIDE: global acquisitions MADE BY European VC-backed companies (they are the BUYER), by year
WITH euro_vc_acquirers AS (   -- same cohort filters as OF-SIDE
  SELECT e.id
  FROM `omega-dahlia-347111.intelligence_unit.entities_iu` e
  WHERE e.entity_type = 'organization' AND e.organization_subtype = 'company'
    AND e.flg_is_vcbacked = TRUE
    AND NOT EXISTS (SELECT 1 FROM UNNEST(e.sectors) s WHERE LOWER(s.name) = 'outside tech')
    AND EXISTS (SELECT 1 FROM UNNEST(e.locations) loc
                WHERE (loc.flg_is_hq = TRUE OR loc.flg_is_founding = TRUE)
                  AND 'Europe' IN UNNEST(loc.country_region))
  GROUP BY e.id
)
SELECT f.year,
  COUNT(DISTINCT f.id) AS acquisitions_made,   -- distinct DEALS with a European VC-backed buyer
  COUNT(DISTINCT a.id) AS distinct_acquirers
FROM `omega-dahlia-347111.intelligence_unit.funding_iu` f
JOIN UNNEST(f.funding_investors) inv ON TRUE
JOIN euro_vc_acquirers a ON a.id = inv.bobject_investor_id   -- the European company IS the BUYER
WHERE f.flg_is_exit = TRUE AND f.round = 'ACQUISITION' AND f.year >= 2010  -- target geography unfiltered = "globally"
GROUP BY f.year ORDER BY f.year;
```

**NULL handling in exclusions:**
When excluding a value, BigQuery's three-valued logic means `!= 'X'` (or `!= N`) also excludes NULLs. Always use:
```sql
(field IS NULL OR field != 'X')
```
Unless NULLs genuinely should be excluded (binary/always-populated fields).

**People data patterns:**
- Prefer standardised fields (`flg_is_founder`, structured `titles` array, university degree fields) over LIKE/REGEX on raw fields. Role flags also exist at entity level (`e.flg_is_founder` / `flg_is_executive` / `flg_is_partner`) and on `people_organizations_iu` (`flg_is_founder` / `flg_is_executive` / `flg_is_partner`).
- Dual check is the best pattern for titles:
```sql
REGEXP_CONTAINS(LOWER(po.raw_title), r'professor|researcher')
OR EXISTS (
  SELECT 1 FROM UNNEST(po.titles) t
  WHERE REGEXP_CONTAINS(LOWER(t.name), r'professor|researcher')
)
```
- Resolve companies to entity IDs first; fall back to `LOWER(name) LIKE '%company%'` only for less well-known entities

**Investor round preference:**
- `investors_iu.preferred_round` is now reliable (~90.8% populated) — the investor's most-frequent round type (manual value when set, else mode of participations). **Use it directly.** Only fall back to deriving the mode from `funding_iu` participations for the ~9% of NULLs.
- `investors_iu.funds` STRUCT note: `fund_type` is a coded `INT64` (not a text label — match against the INT), `fund_date` is a `STRING` (parse/cast before date arithmetic), and `source_url` (STRING) is available.

**Currency conversion:**
`dim_currency_rates.eur_rate` = units of local currency per 1 EUR. To convert: `amount_local / eur_rate`. Entity-level EUR fields also available: `latest_valuation_eur`, valuations sub-array `value_eur`.

**Revenue — three ways to read it, and a flat-FX caveat:**

Pick deliberately and don't mix the array and the time-series in one metric.
- **Scalar shortcut — `entities_iu.latest_revenue_usd` (FLOAT64) + `latest_revenue_year` (INT64).** The most recent year's revenue without unnesting — fastest for a "current revenue" filter/sort or a single-company headline figure. ⚠ It can **lag the max year in `revenues[]`** (which may carry a forward estimate — e.g. a company with a 2027 estimate row can still have `latest_revenue_year = 2026`); if you need a specific year, read the array.
- **`entities_iu.revenues[]`** — `ARRAY<STRUCT<year, value_eur, value_usd, flg_is_estimate>>`: full **fiscal-year** history, one row per year. Use for revenue history or a specific past year.
- **`timeseries_data_iu.revenue_usd`** — **forward-filled** yearly revenue (last disclosed value carried forward), aligned with the other time-series metrics. Use for revenue-over-time charts and cross-metric time-series work.
- **⚠ `value_usd` is NOT a real FX conversion — it's a flat `value_eur × 1.1`** (this applies to `revenues.value_usd` **and** the derived `latest_revenue_usd`). `value_eur` (INT64) is the primary figure. For anything USD-precise, convert `value_eur` with `dim_currency_rates_iu` at the appropriate rate rather than trusting the `_usd` field.
- **Revenue is estimate-heavy:** `flg_is_estimate = TRUE` (on `revenues[]`) marks modelled (non-filing) figures — filter or flag it when precision matters.
- **Threshold shortcuts** (avoid recomputing from `revenues`): `flg_is_colt` (revenue $25M–$100M, ex-Thoroughbreds), `flg_is_thoroughbred` ($100M+ revenue, a sector-tag membership), and `year_became_thoroughbred` (year the company first reached ≥$100M revenue).

## Step 4: Choose the right table

| Question type | Primary table | Notes |
|---|---|---|
| VC funding by year/region | `vc_funding_iu` or `funding_iu` + `flg_is_vc_round` | `vc_funding_iu` pre-excludes outside tech + mature |
| **Median / quartile / average VC round size by stage** | **`vc_combined_rounds_iu`** | **The combined-round table — base round + extensions summed, mega-rounds clustered. This is the only correct source for round-size stats; per-event `vc_funding_iu.amount_usd` answers a different question. Population baked in — apply no VC defaults. See Common Query Templates.** |
| Total funding incl. grants/debt | `funding_iu` | Apply default exclusions manually |
| Employee/valuation/EBITDA/market-cap trends over time | `timeseries_data_iu` | Join on `entity_id` (NOT `bobject_id`); forward-filled |
| Single company's current/headline revenue | `entities_iu.latest_revenue_usd` (+ `latest_revenue_year`) | Scalar shortcut; flat `value_eur × 1.1`; may lag the max year in `revenues[]` |
| Company revenue — fiscal-year actuals/estimates | `entities_iu.revenues[]` | One row per fiscal `year`; `value_usd` is a flat `value_eur × 1.1` approx (convert `value_eur` for precision); `flg_is_estimate` marks modelled figures |
| Revenue over time (forward-filled series) | `timeseries_data_iu.revenue_usd` | Aligned with other time-series metrics; last value carried forward. Don't mix with `revenues[]` in one metric |
| A company's "last / current round" | `entities_iu.last_funding_round_id` → join `funding_iu.id` | Entity pointer to the most recent funding round (excludes exits; may be a grant/non-VC round). See Common Query Templates → "Most-recent round per company" |
| **Combined / aggregate EV, EV per country/region, EV-over-time** | **`timeseries_data_iu.valuation_usd` (filter `year`)** | Mirrors the platform stat; `latest_valuation_usd` undercounts ~4–10%. One row/entity/year — safe to `SUM`. See Step 2 → EV valuation source. |
| Single company's headline valuation / valuation ranking | `entities_iu.latest_valuation_usd` | Scalar "latest" only — do NOT sum across an ecosystem |
| Investor portfolios | `investors_iu` + `funding_iu` | UNNEST `funding_investors` to link; `entities_invested_in` for portfolio |
| Investor participation per round | `funding_iu` or `vc_funding_iu` + `UNNEST(funding_investors)` | One array element per investor (`bobject_investor_id`, `flg_is_lead_investor`); join → entities.id. (⚠ the `vc_funding_investors` table with per-investor `bucket_usd` is NOT deployed) |
| Investor ranking / power-law / top investors | `reporting_iu.power_law` (US: `power_law_rising_star_usa`) | Filter region+region_type AND sector+sector_type together; rank by `score_total`/`percentile`. Separate `reporting_iu` dataset (these two tables keep plain names, no `_iu`). Score columns are `FLOAT64`. |
| Investor returns / profit / MOIC / TVPI | `vc_investor_returns_iu` | One row per investor×company — aggregate it directly, do NOT derive from rounds (double-counts). Realized value is mostly estimated: filter `exit_value_source='disclosed_exit_amount'` for booked returns |
| Companies by main HQ region / region rankings | `main_hq_regions` | Join via `entities_iu.main_hq_region_unique_id` (declared, pending build) → `dim_locations_iu_unique_id`; filter `source='curated'` |
| Founder/exec/partner backgrounds | `people_iu` + `people_organizations_iu` | Use `flg_is_founder`/`flg_is_executive`/`flg_is_partner`, not LIKE on titles |
| Company counts/lists | `entities_iu` | Filter `entity_type`/`organization_subtype`; no default exclusions unless VC/EV |
| Exit data | `funding_iu` only | `vc_funding_iu` does NOT contain exits; or use entity `flg_is_exited`/`year_of_exit` |
| Job openings / hiring | `jobs_iu` | Join `entity_id` → entities.id; entity-level `flg_is_hiring` |
| Lists & landscapes | `dim_lists_iu` | UNNEST `entity_ids` to get members |
| News / press | `news_iu` | UNNEST `mentioned_entities`, join `.id` → `entities_iu.id` (⚠ schema in flux) |
| Dealroom Signal ranking | `entities_iu` | Use `e.dealroom_signal.rating` (STRUCT, no UNNEST) |

## Step 5: Write clean SQL

- Fully-qualified table names: `` `omega-dahlia-347111.intelligence_unit.<table>` ``
- CTEs for clarity — avoid deeply nested subqueries
- `CONCAT()` for string concatenation (not `||`)
- No `SELECT *`
- BigQuery GoogleSQL syntax only

## Step 6: Run the companion sanity check

After the main query returns, build its companion sanity-check query (PART 4) and run it with
**`run_sanity_check`** — NOT a second `run_bigquery`. The check tool routes the result to the analysis
panel as a pass/flag verdict; `run_bigquery` would open a second results tab, and a validation
aggregate sitting next to the answer in identical styling reads as a second answer. Then reconcile the
two yourself before the number reaches the answer or a chart.

Run it when the Sanity toggle is on, or when the analyst asks for it. Each check is a second billed
query, so for a pure schema/discovery lookup just say no check was needed.

---

# PART 3 — Review your SQL before you run it

Run this checklist over your own draft. These are the mistakes that recur, and every one of them
returns a plausible-looking number rather than an error, so nothing downstream will catch them.

## Quick Correction Checklist

**For VC funding queries, check all four defaults:**

1. ☐ Outside tech excluded from sectors array?
2. ☐ Mature excluded? `(growth_stage IS NULL OR growth_stage != 4)` — not `growth_stage_desc LIKE '%mature%'` and not a fixed `= 'Operational'`
3. ☐ No round-name exclusions added? (`flg_is_vc_round = TRUE` is the complete VC selection — `round NOT IN ('SPAC PRIVATE PLACEMENT', 'GRANT')` is redundant with it; never add it)
4. ☐ `flg_is_vc_round` (not `flg_is_funding_round`) for VC queries?

**For EV queries (valuations, unicorns), check the three defaults:**

E1. ☐ Outside tech excluded from sectors array?
E2. ☐ Mature excluded? `(growth_stage IS NULL OR growth_stage != 4)`
E3. ☐ `launch_year >= 1990` applied (strict — drops NULLs)?
E4. ☐ `'mature company'` sector tag NOT excluded? (Removed from the defaults 2026-08-25 — the platform's EV view never applied it. Apply only on an explicit user ask.)
E5. ☐ **Combined/aggregate EV uses `timeseries_data_iu.valuation_usd` for the target year, NOT `SUM(latest_valuation_usd)`?** (latter undercounts ~4–10%.)
E6. ☐ **Per-country/region EV: multi-membership dedup (`DISTINCT id, country`, `founding_or_hq anyof`), NOT `ROW_NUMBER()` single-assignment?** Company count via `LEFT JOIN` (includes unvalued), not `valuation IS NOT NULL`?

**General SQL correctness checks (apply to any query):**

5. ☐ Deep tech on correct array? `technologies` for 'Deep Tech' (id 6), `sectors` for 'DT and LS'
6. ☐ Region field correct for intent? `continent` for a clean HQ-region partition; an **exact** `country_region` name for a named/curated region (don't unnest-and-group the whole `country_region` array). "Europe" → which of the three definitions?
7. ☐ Location scope correct for query type? VC → HQ-only; EV/mixed → HQ or founding; other → as specified
8. ☐ Deduplication matches output type? `ROW_NUMBER()` for row-level, `EXISTS` for aggregates (VC HQ-only doesn't need `ROW_NUMBER()`)
9. ☐ Right table? `funding_iu` for exits, `vc_funding_iu` OK for VC-only-no-exits
10. ☐ Stage comparisons use `standardised_round_label` (the true stage), not raw `round` (self-reported/marketing)? NULLs excluded, not backfilled from `round`?
11. ☐ "Exclude closed" → `(company_status IS NULL OR company_status != 3)`? Not `= 'operational'` (drops Acquired + Low Activity)?
12. ☐ Median uses `APPROX_QUANTILES`, not row-level list?
12b. ☐ **Round-size medians/quartiles read `vc_combined_rounds_iu.total_amount_usd`, not per-event `vc_funding_iu.amount_usd`?** And no VC defaults re-applied on top (population is baked in)? Filters applied at round grain via a join to `entities_iu` — not to a pre-aggregated medians result?
13. ☐ Exact array match, not `LIKE '%…%'` across multiple arrays?
14. ☐ All table/column names exist in `schema.json`? (Unsure a field exists at all? `schema.md` → "Complete Column Index" lists every column by name.) (Common agent errors: removed `flg_is_company`/`type_desc`; `entities_timeseries_data` instead of `timeseries_data_iu`; `raised_amount_usd_total` instead of `amount_usd`; `announced_on` instead of `year`/`month`; `last_valuation_usd` instead of `latest_valuation_usd`.)
15. ☐ Date filtering uses `year`/`month` integers, not `timecreate`?
16. ☐ Output shape matches request? No unrequested GROUP BYs?
16b. ☐ Monetary amounts returned as full raw USD values? No `/1e6`/`/1000000` with "m" suffix, no `/1e9` with "b" suffix, no abbreviation.
16c. ☐ Time-series pivoted wide (one column per year, one row per metric), not long (one row per year)? And do the year columns cover the full range in the data — no years silently dropped by an incomplete column list? Any cutoff should be an explicit `WHERE year >= …`, not implied by missing columns.
17. ☐ NULL handling in exclusions preserves NULLs where appropriate?
18. ☐ People queries use standardised fields (`flg_is_founder`, `titles` array) before LIKE/REGEX fallbacks?
19. ☐ No `flg_is_startup = TRUE` applied unless user explicitly asked? (Excludes legitimate funded startups)
20. ☐ `flg_is_verified` never applied to `entities_iu` (companies)? On funding rounds, only when the user explicitly asked?
21. ☐ Entity population correct? Companies = `entity_type='organization' AND organization_subtype='company'`; persons = `entity_type='person'`. No use of removed `flg_is_company`/`flg_is_person`/`type`.
22. ☐ Companion sanity-check query provided (PART 4), targeting this query's specific risks?
23. ☐ Revenue: correct source (`entities_iu.latest_revenue_usd` scalar vs `entities_iu.revenues[]` fiscal-year vs `timeseries_data_iu.revenue_usd` forward-filled, not mixed)? `value_usd`/`latest_revenue_usd` treated as approximate (flat `value_eur × 1.1`), not an exact FX figure? `flg_is_estimate` considered?
24. ☐ "Last round": used `entities_iu.last_funding_round_id` → `funding_iu.id` (excludes exits; may be grant/non-VC)? Or, where a stricter definition is needed, derived the latest `(year, month)` per `entity_id`? True stage via `standardised_round_label`?

### Array cheat sheet — verify the agent picked the right one:

| Array | `dim_tags.tag_type` | Contains | Examples |
|---|---|---|---|
| `technologies` | `technology` | Technology tags | 'Deep Tech' (id 6), 'Artificial Intelligence' (id 2), 'Quantum' |
| `sectors` | `sector` | Classification tags | 'DT and LS', 'Outside Tech', 'mature company', 'Climate Tech' |
| `industries` | `category` | Industry verticals | 'health', 'food', 'robotics', 'energy' |
| `sub_industries` | `sub_category` | Granular sub-sectors | 'biotechnology', 'medical devices', 'pharmaceutical' |

If a direct industry match exists (e.g., 'space' industry), prefer the industry field over fuzzy tag matching across multiple arrays.

**Present your review as:**
- What the query does (plain English)
- Issues found (specific problems with line references)
- Corrected query (full rewritten SQL if issues are material)
- Expected impact (how issues affect the numbers — inflated? deflated? wrong grouping?)

---

# PART 4 — The companion sanity-check query

Every substantive query gets **one companion sanity-check query**, which you run yourself with
**`run_sanity_check`** and reconcile against the main result. The check is computed **independently
from the database** (not from the main result) — so it *validates* the number rather than echoing it —
and exists to **anticipate that query's specific failure modes** before the number reaches a chart.

Keep it cheap. It is aggregates over the same filters, so it should scan a fraction of the main query.
If a check would be expensive, pick a cheaper check rather than skipping the step.

**Proportional**: 3–6 checks for an analytical query, 1–2 for a simple one; for a pure
schema/discovery lookup, just say no check is needed. It runs when the Sanity toggle is on or the
analyst asks — each one is a second billed query, so it is not unconditional.

## How to build it (flexible — tailor to each query)

1. **Name the query's risk surface** — what could be silently wrong *here*? (double-counting, a default quietly
   dropping rows, small-N medians, overlapping buckets, data outliers, an ambiguous region/stage definition…)
2. **Pick the 2–6 checks** from the catalog below that target those risks — not all of them.
3. **Emit ONE query**, `UNION ALL`-ing the checks into a tidy shape: `check STRING, value STRING, note STRING`
   (CAST every value to STRING). Keep it cheap — aggregates / `INFORMATION_SCHEMA`, reuse the main query's filters
   in a CTE, no heavy new joins. Respect skill conventions (full raw USD amounts, coded-INT filters, etc.).
4. **Label it** in the `label` argument, e.g. `"sanity check — VC funding by country"`, and pass a
   one-line `conclusion` plus a `pass`/`flag` `verdict` — those two are what the analysis panel shows.

## Risk → check catalog

| Risk | When | What the check computes |
|---|---|---|
| Grain / double-counting | any `UNNEST` of locations/arrays | `COUNT(*)` vs `COUNT(DISTINCT id)`; entities with >1 row |
| Group overlap | overlapping buckets (Europe⊇Nordics, HQ-or-founding) | count entities landing in >1 group |
| Totals reconciliation | any GROUP BY | an independent grand total to compare against the SUM of the grouped output |
| Filter impact | VC/EV defaults applied | rows dropped by each major exclusion (`growth_stage=4`, outside tech, `launch_year>=1990`, closed) |
| NULL / coverage | a key field could be NULL | NULL share of the columns used (`amount_usd`, `year_became_unicorn`, `standardised_round_label`, `launch_year`) |
| Denominator / small-N | medians / percentages | the N behind each cell; flag N below ~5–10 |
| Outliers / bounds | any computed measure | min/max/extremes (negative durations, implausible amounts, out-of-range years) |
| Cross-field consistency | derived flags | e.g. `flg_is_unicorn` vs `latest_valuation_usd >= 1e9`; `year_became_unicorn` present when unicorn |
| Region definition | "Europe"/region queries | counts under the chosen definition vs alternatives (the three "Europe"s) so the geo choice is explicit |
| Stage-label coverage | stage queries | labeled vs NULL `standardised_round_label` share, so the excluded set is known |
| Known-entity spot check | optional | assert a couple of expected entities land in the expected bucket |

## Reconciling the two results

Compare the main-query aggregates against the independent check values: do totals reconcile? does
`distinct = rows` (no double-count)? are overlaps expected? are dropped/NULL shares acceptable? any
small-N medians or outliers?

What you do with the outcome:

- **All pass** — say nothing about the check. It is plumbing, not content.
- **A check flags** — fix the query and re-run if the fix is clear. If it is a real property of the
  data rather than a bug (a thin cell, a definition overlap), keep the number and state the caveat in
  your answer, and pass it to `present_insights` so it lands in the analysis panel.
- **Never** present a figure a check contradicted without saying so.

## Example shape (adapt per query)

```sql
-- SANITY CHECK for: VC-backed companies by European country.
WITH base AS ( /* same entity filters as the main query, pre-GROUP BY: e.id, loc.country */ )
SELECT 'grain (rows)'            AS check, CAST(COUNT(*) AS STRING)                       AS value, 'compare to distinct below'            AS note FROM base
UNION ALL SELECT 'distinct_companies',     CAST(COUNT(DISTINCT id) AS STRING),                       'should equal the main-query total'            FROM base
UNION ALL SELECT 'in_multiple_countries',  CAST(COUNTIF(n > 1) AS STRING),                           'HQ+founding overlap → cross-bucket counting'  FROM (SELECT id, COUNT(DISTINCT country) n FROM base GROUP BY id)
UNION ALL SELECT 'null_share_launch_year', CAST(ROUND(COUNTIF(launch_year IS NULL)/COUNT(*)*100,1) AS STRING), 'launch_year>=1990 silently drops NULLs' FROM base_unfiltered;
```

---

# Common Query Templates

Starting points — adapt to the user's specific question.

### VC funding by year for a country
```sql
WITH filtered_entities AS (
  SELECT e.id
  FROM `omega-dahlia-347111.intelligence_unit.entities_iu` e,
    UNNEST(e.locations) loc
  WHERE (e.growth_stage IS NULL OR e.growth_stage != 4)
    AND NOT EXISTS (SELECT 1 FROM UNNEST(e.sectors) s WHERE LOWER(s.name) = 'outside tech')
    AND loc.flg_is_hq = TRUE
    AND LOWER(loc.country) = 'australia'
  GROUP BY e.id
)
SELECT
  f.year,
  SUM(f.amount_usd) AS total_vc_funding_usd,
  COUNT(DISTINCT f.entity_id) AS companies_funded
FROM `omega-dahlia-347111.intelligence_unit.vc_funding_iu` f
JOIN filtered_entities fe ON f.entity_id = fe.id
WHERE f.flg_is_vc_round = TRUE
  AND f.year BETWEEN 2015 AND 2025
GROUP BY f.year
ORDER BY f.year
```

### Median / quartile VC round size by stage (`vc_combined_rounds_iu`)

Round-size stats run off the **combined-round** table, not per-event funding rows. One row per combined round per company: a base round plus **all its extensions** summed and dated to its earliest year, with unnamed mega-rounds (≥ $100M `LATE VC`/`GROWTH EQUITY VC`, within 6 months of each other) clustered into Series C+. So `total_amount_usd` is the **total capital a company raised in that round**, which is the figure the median is meant to describe.

**Medians/quartiles are computed on the fly so they can be filtered.** The standard output is one row per `(round_stage, year)` with 25th pct, median, mean, 75th pct, and round count. Canonical global query:

```sql
SELECT
  round_stage,
  year,
  CAST(ROUND(APPROX_QUANTILES(total_amount_usd, 100)[OFFSET(25)]) AS NUMERIC) AS percentile_25,
  CAST(ROUND(APPROX_QUANTILES(total_amount_usd, 100)[OFFSET(50)]) AS NUMERIC) AS median,
  ROUND(AVG(total_amount_usd), 2)                                             AS average,
  CAST(ROUND(APPROX_QUANTILES(total_amount_usd, 100)[OFFSET(75)]) AS NUMERIC) AS percentile_75,
  COUNT(*)                                                                    AS num_rounds
FROM `omega-dahlia-347111.intelligence_unit.vc_combined_rounds_iu`
WHERE year >= 2019
GROUP BY round_stage, year
ORDER BY round_stage, year DESC
```

**To add filters** (geography, sector, health, year, …): join `entities_iu` on `entity_id` and add a `WHERE` — **everything else stays the same**. Company attributes all live on `entities_iu`: the `locations` array with `flg_is_hq` plus `country` / `country_region` / `continent`; the `sectors` / `technologies` / `industries` arrays; use `dim_locations_iu.flg_is_curated` for the curated-geography set. Example — EU AI Series A:

```sql
SELECT r.year,
  CAST(ROUND(APPROX_QUANTILES(r.total_amount_usd, 100)[OFFSET(50)]) AS NUMERIC) AS median
FROM `omega-dahlia-347111.intelligence_unit.vc_combined_rounds_iu` r
JOIN `omega-dahlia-347111.intelligence_unit.entities_iu` e ON e.id = r.entity_id
WHERE r.round_stage = 'Series A'
  AND EXISTS (SELECT 1 FROM UNNEST(e.locations) loc WHERE loc.flg_is_hq AND 'Europe' IN UNNEST(loc.country_region))
  AND EXISTS (SELECT 1 FROM UNNEST(e.technologies) t WHERE LOWER(t.name) = 'artificial intelligence')
GROUP BY r.year ORDER BY r.year DESC
```

- **Apply no VC defaults** — the population is baked into the table (see Step 2 → Exception).
- **Never pre-aggregate to a medians table and then filter it.** A collapsed median can't be re-filtered. Always filter at round grain, then aggregate — which is why the table ships at round level and no pre-computed medians table exists.
- **Sanity numbers** (all years): Seed ≈ $2.5M · Series A ≈ $11M · Series B ≈ $21M · Series C+ ≈ $43M. ~145K rows / ~94K companies.
- **Prefer medians/quartiles over `AVG`/`SUM` for headline stats** — a handful of real mega-cap rows (> $10B) skew the mean. See `schema.md` → "VC Combined Rounds Table" for the full caveat list (6-month transitive chaining, extreme amounts, stray `year < 1990` rows).

### Unicorn count by HQ region (aggregate — EV defaults applied)
```sql
SELECT
  loc.continent AS hq_region,
  COUNT(DISTINCT e.id) AS unicorn_count
FROM `omega-dahlia-347111.intelligence_unit.entities_iu` e,
  UNNEST(e.locations) loc
WHERE e.flg_is_unicorn = TRUE
  AND loc.flg_is_hq = TRUE          -- one clean region per company; HQ continent
  -- EV defaults:
  AND NOT EXISTS (SELECT 1 FROM UNNEST(e.sectors) s WHERE LOWER(s.name) = 'outside tech')
  AND (e.growth_stage IS NULL OR e.growth_stage != 4)
  AND e.launch_year >= 1990
GROUP BY hq_region
ORDER BY unicorn_count DESC
```
Uses `flg_is_unicorn` → EV query → all three EV defaults apply. Grouped on the single HQ macro-region (`loc.continent`).
For a *named* region instead (e.g. "Europe" unicorns), filter `country_region` to that exact value with `EXISTS` rather than grouping the whole array.

### Companies list (row-level — uses ROW_NUMBER)
```sql
WITH entity_region AS (
  SELECT e.id, e.name,
    loc.country,
    loc.continent AS hq_region,
    ROW_NUMBER() OVER (PARTITION BY e.id
      ORDER BY CASE WHEN loc.flg_is_hq THEN 1 WHEN loc.flg_is_founding THEN 2 ELSE 3 END
    ) AS rn
  FROM `omega-dahlia-347111.intelligence_unit.entities_iu` e,
    UNNEST(e.locations) loc
  WHERE e.entity_type = 'organization' AND e.organization_subtype = 'company'
    AND EXISTS (SELECT 1 FROM UNNEST(e.technologies) dt WHERE dt.id = 6)   -- deep tech
    AND (loc.flg_is_hq = TRUE OR loc.flg_is_founding = TRUE)
)
SELECT id, name, country, hq_region FROM entity_region WHERE rn = 1
ORDER BY name
```
Note: this is a company list query, not a VC funding query, so no default exclusions applied.

### Most-recent ("last") round per company
There is no `last_round` **label** column, but there IS an entity pointer — **`entities_iu.last_funding_round_id`** — to the company's most recent funding round. **Prefer the pointer; it's a simple join, no window function:**
```sql
SELECT
  e.id, e.name,
  f.round,                       -- self-reported label
  f.standardised_round_label,    -- true stage (NULL = not a standardised VC stage)
  f.year, f.month, f.amount_usd,
  f.flg_is_vc_round
FROM `omega-dahlia-347111.intelligence_unit.entities_iu` e
JOIN `omega-dahlia-347111.intelligence_unit.funding_iu` f
  ON f.id = e.last_funding_round_id
```
- **Scope of `last_funding_round_id`:** the most recent **funding** round — verified to **exclude exits** (IPO/M&A), and it may point to a **grant or other non-VC round** (~76% are VC, ~14% grants). If you specifically want the last *VC* round, filter the joined row on `f.flg_is_vc_round = TRUE`, or use the derivation below.
- For the **true stage** of the last round, read `standardised_round_label` (NULL = not a standardised stage; **don't backfill from `round`**).

**Derivation fallback** — use this when you need a definition the pointer doesn't give (e.g. last VC round *only*, most recent event *including* exits, or a per-company history rank):
```sql
WITH ranked AS (
  SELECT
    f.entity_id, f.round, f.standardised_round_label, f.year, f.month, f.amount_usd,
    ROW_NUMBER() OVER (
      PARTITION BY f.entity_id
      ORDER BY f.year DESC, f.month DESC, f.amount_usd DESC   -- tie-break same (year,month) by size
    ) AS rn
  FROM `omega-dahlia-347111.intelligence_unit.funding_iu` f
  WHERE f.flg_is_vc_round = TRUE     -- "last VC round". DROP for last round of ANY type (then exits/debt/grant can win).
)
SELECT entity_id, round, standardised_round_label, year, month, amount_usd
FROM ranked WHERE rn = 1
```
Same derivation works off `entities_iu.fundings[]` via `UNNEST(e.fundings) f` if you're already scanning entities.

---

# Things That Will Silently Break Your Query

1. **`type` / `type_desc` and `flg_is_company`/`flg_is_person`/`flg_is_organization`/`flg_is_university` no longer exist.** Use `entity_type` (`'person'`/`'organization'`) and `organization_subtype` (`'company'`/`'university'`/`'gov_ngo'`/`'fund'`).
2. **`entity_type` is `'person'`, not `'people'`**, and `organization_subtype` is lowercase (`'gov_ngo'`, not "Gov/NGO").
3. **`growth_stage` is a 6-value INT** — live values `0,1,2,3,4,6`: 0 not applicable (persons/universities, desc NULL), 1 Seed (rare), 2 Early Growth, 3 Late Growth, 4 Mature, 6 Breakout Stage. **Code 5 does not exist.** "Exclude mature" = `growth_stage != 4`. The text `growth_stage_desc` still exists but is being retired — prefer the INT.
4. **`company_status` codes:** 0 NULL/persons, 1 Operational, 2 Acquired, 3 Closed, 4 Low Activity. "Exclude closed" = `company_status != 3`; `= 'Operational'`/`= 1` also drops Acquired and Low Activity.
5. **`announced_on` does not exist** on funding/vc_funding. Use `year` and `month` (INT64).
6. **`raised_amount_usd_total` does not exist.** The field is `amount_usd`.
7. **`timecreate` is not the round date.** It's when the record was added to the database.
8. **`entities_timeseries_data` does not exist.** The table is `timeseries_data_iu`. Join on `entity_id`.
9. **`dealroom_signal` is a STRUCT, not an ARRAY.** Access with `e.dealroom_signal.rating` — no UNNEST.
10. **Searching sectors for "deep tech" returns 0 rows.** Use `technologies` array, id = 6.
11. **`!= 'Mature'` / `!= 4` excludes NULLs too.** Use `(field IS NULL OR field != value)`.
12. **Use `standardised_round_label` for stage comparison, not raw `round`.** Raw `round` is self-reported/marketing and doesn't reflect the true stage; `standardised_round_label` applies Dealroom's size + timing-from-founding definitions (see `schema.md` → "Standardised rounds"). A NULL label means the round isn't a standardised stage — **exclude it; don't backfill from `round`.** Use raw `round` only for non-stage events (exits/grants/debt).
13. **Don't unnest-and-group the whole `country_region` array.** Each country is in ~10–19 overlapping regions → triple-counts. Group by `loc.continent` for a clean partition, or filter `country_region` to one exact name.
14. **Three different "Europe"s** — `continent='Europe'` (no Israel/Türkiye), `country_region 'Europe'` (Türkiye yes, Israel no — **the skill default**), `country_region 'Europe incl Israel'` (both). Pick deliberately and say which.
15. **`region_parent` (dim_locations) is names, not IDs** — `region_parent_ids` holds the INTs. And there's no need to join `dim_locations_iu` for region names; `entities.locations` already has them.
16. **Agent ORing both deep tech definitions** silently mixes 54.7K and 75.5K populations. Pick one.
17. **EV default `launch_year >= 1990` drops NULLs.** Deliberate (clean post-1990 cohort) but means companies with missing launch year are silently excluded from EV analyses.
18. **`last_valuation_usd` does not exist** as an entity column. The field is `latest_valuation_usd` (with "est"); EUR equivalent is `latest_valuation_eur`. IPO/exit valuations live on `funding.valuation_usd` with `flg_is_exit = TRUE` — there is no `ipo_valuation_usd` entity column. **But do not SUM `latest_valuation_usd` for combined/aggregate EV** — it undercounts the platform figure by ~4–10%; use `timeseries_data_iu.valuation_usd` for the target year instead (see Step 2 → "Valuation source").
19. **`is_founder` does not exist.** The flag is **`flg_is_founder`** (BOOL) on `entities_iu`, `people_iu`, and `people_organizations_iu`.
20. **People_organizations dates are integers, not DATE columns.** Use `year_start`/`month_start`/`year_end`/`month_end` — there are no `start_date`/`end_date` columns.
21. **`vc_funding_iu` has no exits.** Use `funding_iu` (`flg_is_exit = TRUE`) or entity `flg_is_exited`/`year_of_exit`.
21b. **Acquisition "of" vs "by" flips the join — read the phrasing.** On an ACQUISITION exit row, `funding_iu.entity_id` is the TARGET (got acquired) and `funding_investors[].bobject_investor_id` is the ACQUIRER (the buyer — verified, not the target's VCs; joins to `entities_iu.id`). "Acquisitions OF X" → join `f.entity_id = X.id`; "acquisitions BY X" → `UNNEST(funding_investors)` + join `X.id = inv.bobject_investor_id` with the target geography unfiltered. (See PART 1 → Exits for both templates.)
22. **`news_iu` schema is in flux** — confirm its columns against `schema.json` before relying on them.
23. **Dataset rename:** the core dataset is now `intelligence_unit` (was `dealroom_intelligence`) and all core tables carry an `_iu` suffix (`entities_iu`, `funding_iu`, …). Fully qualify as `` `omega-dahlia-347111.intelligence_unit.<table>` ``. The two `power_law*` tables are the exception — they keep their plain names and still live in the **`reporting_iu`** dataset: `` `omega-dahlia-347111.reporting_iu.power_law` ``.
24. **`investors_iu.funds` STRUCT changed.** `fund_type` is now `INT64` (was a string label) — compare against the coded INT, not a text value. `fund_date` is now `STRING` (was `DATE`) — don't apply date arithmetic to it without casting/parsing. A new `funds.source_url` (STRING) field is available.
25. **`power_law` / `power_law_rising_star_usa` score columns are `FLOAT64`** (were `INT64`) — `colt_seed_score`, `tb_seed_score`/`tb_early_score`/`tb_late_score`, `unicorn_seed_score`/`unicorn_early_score`/`unicorn_late_score`, `rising_star_seed_score`. Don't assume integer scores; rounding/equality comparisons should account for floats.
26. **`dim_tags_iu` has a new `is_muted` (BOOL) column** — muted tags may need excluding depending on the use case; check it when tag selection matters.
27. **Two new tables: `headcount_breakdown_iu` and `web_traffic_iu`.** Confirm their columns against `schema.json` before use.
28. **STRUCT timestamp sub-fields are now `DATETIME`, not `TIMESTAMP`** in places (e.g. `dim_lists_iu.landscape_categories.timecreated`/`timeupdated`, `dim_lists_iu.users.timecreated`). Use `DATETIME` functions; and `landscape_categories.order` is a reserved word — backtick it (`` `order` ``).
29. **`revenues.value_usd` is a flat `value_eur × 1.1`, not a real FX conversion.** It's a fixed-rate approximation. For USD-precise revenue, convert `value_eur` (the primary INT64 figure) via `dim_currency_rates_iu`. And `revenues` is estimate-heavy — check `flg_is_estimate` before treating a figure as a filing.
30. **Two different revenue fields — don't mix them.** `entities_iu.revenues[]` = per-fiscal-year actuals/estimates (one row per `year`); `timeseries_data_iu.revenue_usd` = forward-filled series aligned with the other time-series metrics. Combining them in one metric double-counts or conflates disclosed vs carried-forward values.
31. **"Last round": there's no `last_round` *label*, but there IS `entities_iu.last_funding_round_id`** — join it to `funding_iu.id` to read the company's most recent funding round (a simple join; no `ROW_NUMBER` needed). Scope: it **excludes exits** and may point to a **grant/non-VC round** (~76% VC, ~14% grant) — filter `flg_is_vc_round` if you need the last VC round. Read the true stage from `standardised_round_label`. For definitions the pointer doesn't give (last VC-only, incl. exits), derive via `ROW_NUMBER`. See Common Query Templates → "Most-recent round per company".
32. **Round-size medians must come from `vc_combined_rounds_iu`, not `vc_funding_iu`.** Taking `APPROX_QUANTILES` of per-event `vc_funding_iu.amount_usd` answers a different question — it treats a base round and each of its extensions as separate rounds, so it understates the capital a company actually raised at that stage. Use `vc_combined_rounds_iu.total_amount_usd`. And **don't re-apply the VC defaults** to it: the population is baked in.
33. **`dim_tags_iu` has a new `is_alias` (BOOL) column.** True for sector/technology/category/sub_category rows that alias another canonical tag; NULL for the other tag types. For canonical-only tags filter **`is_alias IS NOT TRUE`** — a bare `is_alias = FALSE` silently drops every NULL (not-applicable) row. Alias rows are kept deliberately because entities can be tagged via an alias id.
34. **New `investor_type` tag type in `dim_tags_iu` (`tag_type_id = 13`) has no shared integer id.** Unlike every other tag family, join it by label: `dim_tags_iu.name = <label> AND tag_type = 'investor_type'` — there is no id to match against `investors_iu.investor_types` (an array of label strings). Note also that `investor_types` merges coarse types (angel, corporate, crowdfunding, university, government & non-profit, service provider) with fine fund sub-types (venture capital, private equity, family office, angel fund, accelerator, advisor, incubator, pension fund, fund of funds, sovereign wealth fund): **`'angel fund'` (a fund) is distinct from `'angel'` (a person)**, there is no `'investment fund'` label, and a fund with no sub-type falls back to `'other'`.

