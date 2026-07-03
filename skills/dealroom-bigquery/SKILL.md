---
name: dealroom-bigquery
description: Write SQL queries against Dealroom's BigQuery dataset (intelligence_unit, formerly dealroom_intelligence), write structured prompts for the BigQuery agent, and review/correct agent-generated SQL. Trigger when the user mentions BigQuery, BQ, SQL queries against Dealroom data, the BigQuery agent, intelligence_unit, dealroom_intelligence, or wants to pull startup/VC/funding/investor/people/jobs data from the database. Also trigger for phrases like 'write a query for', 'fix this SQL', 'prompt the agent', 'how many unicorns', 'VC funding by year', 'investor activity', 'job openings', 'investor ranking', 'power law', 'top investors', or any question that implies querying Dealroom's structured data. If they paste SQL to review, paste agent output for a second opinion, or want help prompting the BQ agent, use this skill. Do NOT trigger for spreadsheet enrichment tasks (use dealroom-excel-enrichment) or general data visualisation requests that don't involve writing SQL.
---

# Dealroom BigQuery — SQL, Agent Prompting & Benchmarking

This skill has three jobs:

1. **Write SQL queries** directly against the `intelligence_unit` dataset in BigQuery.
2. **Write structured natural-language prompts** for the Dealroom BigQuery AI Agent so it produces correct SQL on the first try.
3. **Review and correct SQL** the agent has produced — targeting the recurring error patterns from testing.

**First step — always load the schema references:**
Before writing or reviewing any query, read both files in this skill's directory:

- **`schema.json`** — authoritative column list for all 17 tables (every column + nested STRUCT field, with data types and descriptions). All tables now live in the single **`intelligence_unit`** dataset, qualified as `` `omega-dahlia-347111.intelligence_unit.<table>` ``. Core tables carry an `_iu` suffix: `entities_iu`, `funding_iu`, `vc_funding_iu`, `investors_iu`, `people_iu`, `people_organizations_iu`, `jobs_iu`, `news_iu`, `dim_lists_iu`, `timeseries_data_iu`, `headcount_breakdown_iu`, `web_traffic_iu`, `dim_locations_iu`, `dim_tags_iu`, `dim_currency_rates_iu`. The two power-law tables are listed in `schema.json` for column reference but live in a **separate `reporting_iu` dataset** — qualify them as `` `omega-dahlia-347111.reporting_iu.power_law` `` / `` `omega-dahlia-347111.reporting_iu.power_law_rising_star_usa` `` (no `_iu` suffix on the table name itself). (⚠ `vc_funding_investors` was previously documented but is **not deployed** in production — use the `funding_investors` array on `funding_iu`/`vc_funding_iu` instead; see `schema.md`.) `headcount_breakdown_iu` and `web_traffic_iu` are **new** tables in this schema generation. Every column name used in a query must appear in this file — never guess. If a column name in your draft query isn't in `schema.json`, stop and verify before continuing.
- **`schema.md`** — narrative context: the entity model, join paths, enum values, INT↔label mappings, geography/region logic, critical field corrections, and query gotchas.

Do not rely on memory alone.

> **⚠ Migration note.** The dataset moved to a canonical entity model. Entities are classified by **`entity_type`**
> (`'person'`/`'organization'`) + **`organization_subtype`** (`'company'`/`'university'`/`'gov_ngo'`/`'fund'`) +
> role flags. The old `flg_is_company`/`flg_is_person`/`flg_is_organization`/`flg_is_university` and `type`/`type_desc`
> columns are **gone**. The `*_desc` text columns still exist but are being retired — **prefer the coded INT partners**:
> `growth_stage` and `company_status` (on `entities_iu`), and `gender` (on `people_iu`, alongside `gender_desc`). Tables refresh **hourly**.

---

## Who This Skill Serves

The team has a mix of SQL experience levels. Adapt accordingly:
- **SQL-literate users:** Show the query, briefly note which patterns you applied and why, highlight anything non-obvious.
- **Non-SQL users:** Write the query, explain in plain language what it does, what filters are applied, and what the output columns mean.

Always show the full SQL in every response — never summarise or skip it.

**Pair every substantive query with a companion sanity-check query (see PART 4).** Present it immediately after the main query so the user can run both in BigQuery in parallel; when they return the two CSVs (main + check), reconcile them before the number goes into a graph.

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

### VC funding queries — always apply these three exclusions

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

**3. Exclude SPAC private placement and grant rounds:**
```sql
AND f.round NOT IN ('SPAC PRIVATE PLACEMENT', 'GRANT')
```

These match the Dealroom platform defaults for VC funding views. `vc_funding_iu` already pre-filters outside tech and mature at the table level, so those two are belt-and-braces when using `vc_funding_iu` but still worth including for clarity. The SPAC PP and grant round exclusion must be applied explicitly even when using `vc_funding_iu`.

### Enterprise value (EV) queries — always apply these four exclusions

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

**4. Exclude 'mature company' sector tag:**
```sql
AND NOT EXISTS (
  SELECT 1 FROM UNNEST(e.sectors) s
  WHERE LOWER(s.name) = 'mature company'
)
```

The mature-stage (filter 2) and mature-company-tag (filter 4) exclusions overlap but are not identical — keep both.

> **⚠ These four defaults are NOT the platform's EV view chip-set.** When a user is replicating a specific Dealroom app view (they'll often show the filter chips), match *their* chips, not these defaults. A typical platform EV view uses: `outside tech`, `mature` (growth stage), **`closed`** (`company_status != 3`), **government nonprofit** (already excluded by `organization_subtype = 'company'`), **service provider** (see below), `founded since 1990`, and `VC Backed` (`flg_is_vcbacked = TRUE`) — and does **not** apply the `mature company` *sector tag* (filter 4). So to mirror a platform view you usually **drop filter 4 and add `company_status != 3`**. Keep the four defaults only for a generic "EV analysis" ask with no platform view to match.
>
> **`service provider` has no field in this schema.** The platform's `company_type = service provider` exclusion maps to the retired `type` column; `organization_subtype` only has `company / university / gov_ngo / investor`, and the literal `service provider` *sector tag* covers just ~154 entities (not the same population). Leave it unexcluded and note the residual (~0.2%, and effectively nil once `flg_is_vcbacked = TRUE` is required, since service providers are rarely VC-backed).

### Mixed queries (both VC funding and EV)

For queries that touch both (e.g. "unicorns by VC raised"), take the **union of exclusions** — apply all six unique filters. The VC and EV exclusions overlap on outside tech and mature stage; the EV-only additions (`launch_year >= 1990`, `mature company` tag) just narrow further.

### Other query types — no default filters

Do not apply `flg_is_startup = TRUE`, `flg_is_verified = TRUE`, or the mature/outside tech exclusions on queries that aren't VC or EV. Let the user specify what they want filtered.

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

## Step 4: Choose the right table

| Question type | Primary table | Notes |
|---|---|---|
| VC funding by year/region | `vc_funding_iu` or `funding_iu` + `flg_is_vc_round` | `vc_funding_iu` pre-excludes outside tech + mature |
| Total funding incl. grants/debt | `funding_iu` | Apply default exclusions manually |
| Employee/revenue/valuation/EBITDA/market-cap trends | `timeseries_data_iu` | Join on `entity_id` (NOT `bobject_id`); forward-filled |
| **Combined / aggregate EV, EV per country/region, EV-over-time** | **`timeseries_data_iu.valuation_usd` (filter `year`)** | Mirrors the platform stat; `latest_valuation_usd` undercounts ~4–10%. One row/entity/year — safe to `SUM`. See Step 2 → EV valuation source. |
| Single company's headline valuation / valuation ranking | `entities_iu.latest_valuation_usd` | Scalar "latest" only — do NOT sum across an ecosystem |
| Investor portfolios | `investors_iu` + `funding_iu` | UNNEST `funding_investors` to link; `entities_invested_in` for portfolio |
| Investor participation per round | `funding_iu` or `vc_funding_iu` + `UNNEST(funding_investors)` | One array element per investor (`bobject_investor_id`, `flg_is_lead_investor`); join → entities.id. (⚠ the `vc_funding_investors` table with per-investor `bucket_usd` is NOT deployed) |
| Investor ranking / power-law / top investors | `reporting_iu.power_law` (US: `power_law_rising_star_usa`) | Filter region+region_type AND sector+sector_type together; rank by `score_total`/`percentile`. Separate `reporting_iu` dataset (these two tables keep plain names, no `_iu`). Score columns are `FLOAT64`. |
| Founder/exec/partner backgrounds | `people_iu` + `people_organizations_iu` | Use `flg_is_founder`/`flg_is_executive`/`flg_is_partner`, not LIKE on titles |
| Company counts/lists | `entities_iu` | Filter `entity_type`/`organization_subtype`; no default exclusions unless VC/EV |
| Exit data | `funding_iu` only | `vc_funding_iu` does NOT contain exits; or use entity `flg_is_exited`/`year_of_exit` |
| Job openings / hiring | `jobs_iu` | Join `entity_id` → entities.id; entity-level `flg_is_hiring` |
| Lists & landscapes | `dim_lists_iu` | UNNEST `entity_ids` to get members |
| News / press | `news_iu` | UNNEST `mentioned_entities` (join `.id` → entities.id) |
| Dealroom Signal ranking | `entities_iu` | Use `e.dealroom_signal.rating` (STRUCT, no UNNEST) |

## Step 5: Write clean SQL

- Fully-qualified table names: `` `omega-dahlia-347111.intelligence_unit.<table>` ``
- CTEs for clarity — avoid deeply nested subqueries
- `CONCAT()` for string concatenation (not `||`)
- No `SELECT *`
- BigQuery GoogleSQL syntax only

## Step 6: Emit the companion sanity-check query

After the main query, produce its companion sanity-check query (PART 4) so the user can run both in parallel.

---

# PART 2 — Prompting the BigQuery Agent

Use this when the user wants help writing a prompt to send to the Dealroom BigQuery agent.

## Core Principle

**Name the exact fields and arrays.** The agent guesses when you're vague — and often guesses wrong. Specificity is the single biggest lever for accuracy.

| Vague prompt | What happens | Structured prompt | What happens |
|---|---|---|---|
| "AI startups" | Broad regex across arrays | "technology tag 'Artificial Intelligence' in technologies array" | Exact match |
| "in Europe" | Sometimes uses `continent` | "country_region contains 'Europe'" | Correct field + explicit definition |
| "deep tech" | Checks sectors (0 rows) | "technology tag 'Deep Tech' in technologies array" | Correct match |
| "exclude mature" | Skips or over-excludes | "exclude growth_stage = 4 (Mature)" | Precise exclusion |
| "companies" | Mixes in persons/funds | "entity_type='organization' and organization_subtype='company'" | Correct population |

**Don't over-specify the SQL logic.** Name the fields, arrays, and values — the agent handles joins, CTEs, and aggregations reliably. Asking it to "think step by step" actually makes results worse.

## Prompt Template

```
[What you want — one sentence]

Filters:
- [Field/array]: [exact value]
- Entity: entity_type / organization_subtype as needed
- Location: [HQ region via continent | named region via country_region], [HQ only for VC funding | HQ or founding for EV/other]
- Funding: [table and flags]
- Output: [columns], [ordering], [limit]
- Show the SQL
```

**For VC funding queries, always include these three exclusions plus HQ-only location:**
```
- Location: HQ only (single location per company)
- Exclude sector 'outside tech' from sectors array
- Exclude growth_stage = 4 (Mature)
- Exclude rounds: SPAC PRIVATE PLACEMENT, GRANT
```

**For EV queries (valuations, unicorns), always include these four exclusions plus HQ-or-founding location:**
```
- Location: HQ or founding, deduplicate so each company is counted once
- Exclude sector 'outside tech' from sectors array
- Exclude growth_stage = 4 (Mature)
- Exclude launch_year < 1990 (strict, drop NULL launch_year)
- Exclude sector 'mature company' from sectors array
```

### Example Prompt (VC funding query)

```
Count VC-backed companies in Europe with the following filters:
- Entity: entity_type='organization' and organization_subtype='company'
- Must have technology tag 'Artificial Intelligence' in the technologies array
- Must have industry 'health' in the industries array
- Location: country_region contains 'Europe', HQ only
- Exclude sector 'outside tech' from sectors array
- Exclude growth_stage = 4 (Mature)
- Exclude rounds: SPAC PRIVATE PLACEMENT, GRANT
- Funding: use vc_funding table OR funding table with flg_is_vc_round = TRUE
- Show: country, company count, total VC funding
- Top 15 by company count
- Show the SQL
```

**Always include "Show the SQL"** — the agent stops showing SQL after ~3 messages in a thread unless asked. Then emit the companion sanity-check query (PART 4) so it can be run alongside.

**For non-VC-funding queries**, do not auto-include the standard exclusions. Let the user specify what they want filtered.

**For NULL handling**, be explicit: "Exclude X but keep NULL values" → agent uses `field != 'X' OR field IS NULL`.

**For output shape**, be explicit: "Return a single number" or "Group by country only" — otherwise the agent may add unrequested GROUP BY dimensions.

**For monetary amounts, always return the full raw value.** Do not divide by 1,000,000 or 1,000,000,000, and do not append an "m"/"b" suffix or otherwise abbreviate. The agent sometimes defaults to `ROUND(SUM(amount_usd)/1e6, 1)` with an "m" label or `/1e9` with a "b" — we never want this. Amounts like `amount_usd` and valuation columns must be output in full (e.g. `1500000000`, not `1.5b` or `1500m`). When prompting, add: "Return all monetary amounts as full raw values in USD — do not divide by million/billion or add m/b suffixes."

**For time-series output, pivot years horizontally by default — one column per year, not one row per year.** The agent defaults to a long format (a `year` column with one row per year), but we want wide format so it pastes straight into Datawrapper: each year is its own column and each metric is a single row across those columns. Use BigQuery's `PIVOT` operator with an explicit year list, or conditional aggregation:
```sql
SELECT
  'total_capital_usd' AS metric,
  SUM(CASE WHEN year = 2015 THEN amount_usd END) AS y2015,
  SUM(CASE WHEN year = 2016 THEN amount_usd END) AS y2016,
  -- … one column per year through the latest …
  SUM(CASE WHEN year = 2025 THEN amount_usd END) AS y2025
FROM …
```
When the result has multiple metrics (e.g. `total_rounds`, `total_capital_usd`, `pct_foreign`), emit one row per metric with years as columns. When prompting, add: "Pivot years horizontally — one column per year, one row per metric — so it pastes into Datawrapper. Do not output a long format with one row per year."

**The year columns must span the full range present in the data, not a fixed start.** Because pivoting requires naming each year column explicitly, any year not named is *silently dropped* — there's no error, and in wide format it doesn't even leave a visible gap, so totals quietly undercount. The `2015 … 2025` range above is illustrative only; it is **not** a floor. Before pivoting, determine the actual range (e.g. check `MIN(year)`/`MAX(year)` for the filtered set) and generate a column for every year in it — including years before 2015 if the data has them. If a deliberate cutoff is wanted (e.g. "from 2015 onward"), apply it as an explicit `WHERE year >= 2015` filter and state that earlier years are excluded by design — don't achieve it implicitly by omitting columns.

## Complex Sub-Segments

For queries combining multiple sector/technology/industry filters (e.g., "medical devices AND AI but NOT pharmaceutical"):
1. Break into sequential messages — counts → breakdowns → derived variables
2. Catch errors at each step before building further
3. For queries past ~200 lines, provide a SQL template and ask the agent to modify specific parts

---

# PART 3 — Reviewing & Correcting Agent SQL

When a user pastes agent-generated SQL, run this checklist. Most errors hit at least one of these.

## Quick Correction Checklist

**For VC funding queries, check all four defaults:**

1. ☐ Outside tech excluded from sectors array?
2. ☐ Mature excluded? `(growth_stage IS NULL OR growth_stage != 4)` — not `growth_stage_desc LIKE '%mature%'` and not a fixed `= 'Operational'`
3. ☐ SPAC PRIVATE PLACEMENT and GRANT rounds excluded?
4. ☐ `flg_is_vc_round` (not `flg_is_funding_round`) for VC queries?

**For EV queries (valuations, unicorns), check all four defaults:**

E1. ☐ Outside tech excluded from sectors array?
E2. ☐ Mature excluded? `(growth_stage IS NULL OR growth_stage != 4)`
E3. ☐ `launch_year >= 1990` applied (strict — drops NULLs)?
E4. ☐ `'mature company'` sector tag excluded from sectors array? (**Drop this if mirroring a platform view** — the app doesn't apply the tag; add `company_status != 3` instead.)
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
13. ☐ Exact array match, not `LIKE '%…%'` across multiple arrays?
14. ☐ All table/column names exist in `schema.json`? (Common agent errors: removed `flg_is_company`/`type_desc`; `entities_timeseries_data` instead of `timeseries_data_iu`; `raised_amount_usd_total` instead of `amount_usd`; `announced_on` instead of `year`/`month`; `last_valuation_usd` instead of `latest_valuation_usd`.)
15. ☐ Date filtering uses `year`/`month` integers, not `timecreate`?
16. ☐ Output shape matches request? No unrequested GROUP BYs?
16b. ☐ Monetary amounts returned as full raw USD values? No `/1e6`/`/1000000` with "m" suffix, no `/1e9` with "b" suffix, no abbreviation.
16c. ☐ Time-series pivoted wide (one column per year, one row per metric), not long (one row per year)? And do the year columns cover the full range in the data — no years silently dropped by an incomplete column list? Any cutoff should be an explicit `WHERE year >= …`, not implied by missing columns.
17. ☐ NULL handling in exclusions preserves NULLs where appropriate?
18. ☐ People queries use standardised fields (`flg_is_founder`, `titles` array) before LIKE/REGEX fallbacks?
19. ☐ No `flg_is_startup = TRUE` applied unless user explicitly asked? (Excludes legitimate funded startups)
20. ☐ No `flg_is_verified = TRUE` applied unless user explicitly asked?
21. ☐ Entity population correct? Companies = `entity_type='organization' AND organization_subtype='company'`; persons = `entity_type='person'`. No use of removed `flg_is_company`/`flg_is_person`/`type`.
22. ☐ Companion sanity-check query provided (PART 4), targeting this query's specific risks?

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

# PART 4 — Companion Sanity-Check Query (run in parallel)

Every substantive query ships with **one companion sanity-check query**. The user runs the main query and the check
**in parallel** in BigQuery, exports two CSVs (main + check), and pastes both back; you then **reconcile** them. The
check is computed **independently from the database** (not from the main CSV) — so it *validates* the result rather
than echoing it — and exists to **anticipate that query's specific failure modes** before the number reaches a graph.

Default-on and **proportional**: 3–6 checks for an analytical query, 1–2 for a simple one; for a pure
schema/discovery lookup, just say no check is needed.

## How to build it (flexible — tailor to each query)

1. **Name the query's risk surface** — what could be silently wrong *here*? (double-counting, a default quietly
   dropping rows, small-N medians, overlapping buckets, data outliers, an ambiguous region/stage definition…)
2. **Pick the 2–6 checks** from the catalog below that target those risks — not all of them.
3. **Emit ONE query**, `UNION ALL`-ing the checks into a tidy shape: `check STRING, value STRING, note STRING`
   (CAST every value to STRING). Keep it cheap — aggregates / `INFORMATION_SCHEMA`, reuse the main query's filters
   in a CTE, no heavy new joins. Respect skill conventions (full raw USD amounts, coded-INT filters, etc.).
4. **Label it:** `-- SANITY CHECK for <main query>. Run alongside the main query; export as a separate CSV.`

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

## Reconciling the two CSVs

When the user returns the main + check CSVs, compare the main-query aggregates against the independent check values:
do totals reconcile? does `distinct = rows` (no double-count)? are overlaps expected? are dropped/NULL shares
acceptable? any small-N medians or outliers? Present **✅ pass / ⚠️ flag** per check, with the actual numbers and what
each implies for the main result (inflated? deflated? unreliable cell?).

## Example shape (adapt per query)

```sql
-- SANITY CHECK for: VC-backed companies by European country. Run alongside the main query; export as a separate CSV.
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
WHERE f.round NOT IN ('SPAC PRIVATE PLACEMENT', 'GRANT')
  AND f.year BETWEEN 2015 AND 2025
GROUP BY f.year
ORDER BY f.year
```

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
  AND NOT EXISTS (SELECT 1 FROM UNNEST(e.sectors) s WHERE LOWER(s.name) = 'mature company')
GROUP BY hq_region
ORDER BY unicorn_count DESC
```
Uses `flg_is_unicorn` → EV query → all four EV defaults apply. Grouped on the single HQ macro-region (`loc.continent`).
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
22. **`news_iu` schema is in flux** — confirm its columns against `schema.json` before relying on them.
23. **Dataset rename:** the core dataset is now `intelligence_unit` (was `dealroom_intelligence`) and all core tables carry an `_iu` suffix (`entities_iu`, `funding_iu`, …). Fully qualify as `` `omega-dahlia-347111.intelligence_unit.<table>` ``. The two `power_law*` tables are the exception — they keep their plain names and still live in the **`reporting_iu`** dataset: `` `omega-dahlia-347111.reporting_iu.power_law` ``.
24. **`investors_iu.funds` STRUCT changed.** `fund_type` is now `INT64` (was a string label) — compare against the coded INT, not a text value. `fund_date` is now `STRING` (was `DATE`) — don't apply date arithmetic to it without casting/parsing. A new `funds.source_url` (STRING) field is available.
25. **`power_law` / `power_law_rising_star_usa` score columns are `FLOAT64`** (were `INT64`) — `colt_seed_score`, `tb_seed_score`/`tb_early_score`/`tb_late_score`, `unicorn_seed_score`/`unicorn_early_score`/`unicorn_late_score`, `rising_star_seed_score`. Don't assume integer scores; rounding/equality comparisons should account for floats.
26. **`dim_tags_iu` has a new `is_muted` (BOOL) column** — muted tags may need excluding depending on the use case; check it when tag selection matters.
27. **Two new tables: `headcount_breakdown_iu` and `web_traffic_iu`.** Confirm their columns against `schema.json` before use.
28. **STRUCT timestamp sub-fields are now `DATETIME`, not `TIMESTAMP`** in places (e.g. `dim_lists_iu.landscape_categories.timecreated`/`timeupdated`, `dim_lists_iu.users.timecreated`). Use `DATETIME` functions; and `landscape_categories.order` is a reserved word — backtick it (`` `order` ``).

---

# Improving the BigQuery Agent

Two approaches are being explored:

**Instruction-level changes:** Revised high-priority instructions have been drafted covering the four VC-funding exclusions (outside tech, mature, SPAC PP, grant rounds), deep tech definition, location/region logic, the entity_type/organization_subtype model, SQL visibility, and people data routing.

**Schema-level annotations:** the dataset now ships rich column descriptions (visible via `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`) — including `entity_type`/`organization_subtype` value lists, the `growth_stage` mapping, and the `dim_tags.tag_type`→array mapping. If the agent reads schema metadata, lean on these rather than instruction text.

When team members discover new agent issues, document: the prompt used, the SQL produced, what's wrong, and the corrected SQL.
