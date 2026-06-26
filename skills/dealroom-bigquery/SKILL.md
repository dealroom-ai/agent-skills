---
name: dealroom-bigquery
description: Write SQL queries against Dealroom's BigQuery dataset (dealroom_intelligence), write structured prompts for the BigQuery agent, and review/correct agent-generated SQL. Trigger when the user mentions BigQuery, BQ, SQL queries against Dealroom data, the BigQuery agent, dealroom_intelligence, or wants to pull startup/VC/funding/investor data from the database. Also trigger for phrases like 'test the agent', 'compare agent output', 'write a query for', 'pull data on', 'prompt the agent', 'fix this SQL', 'how many unicorns', 'VC funding by year', 'investor activity', or any question that implies querying Dealroom's structured data. If they paste SQL and ask you to review it, paste agent output and want a second opinion, or want help writing a prompt for the BQ agent, this is the right skill. Do NOT trigger for spreadsheet enrichment tasks (use dealroom-excel-enrichment) or general data visualisation requests that don't involve writing SQL.
---

# Dealroom BigQuery — SQL, Agent Prompting & Benchmarking

This skill has three jobs:

1.  **Write SQL queries** directly against the dealroom_intelligence dataset in BigQuery.

2.  **Write structured natural-language prompts** for the Dealroom BigQuery AI Agent so it produces correct SQL on the first try.

3.  **Review and correct SQL** the agent has produced — targeting the recurring error patterns from testing.

**First step — always load the schema references:** Before writing or reviewing any query, read both files in this skill's references/ directory:

- **references/schema.json** — authoritative column list for 10 core tables (199 columns with data types, nested STRUCT definitions, and descriptions). Tables covered: entities, funding, vc_funding, investors, people, people_organizations, timeseries_data, dim_locations, dim_tags, dim_currency_rates. Every column name used in a query against these tables must appear in this file — never guess. If a column name in your draft query isn't in schema.json, stop and verify before continuing.

- **references/schema.md** — narrative context: join paths, enum values, critical field corrections, query gotchas, and coverage for three peripheral tables not in the JSON (news, eco_index_cities, dim_microapps_locations). If a query touches one of those three, flag to the user that column names aren't JSON-verified.

Do not rely on memory alone.

## Who This Skill Serves

The team has a mix of SQL experience levels. Adapt accordingly:

- **SQL-literate users:** Show the query, briefly note which patterns you applied and why, highlight anything non-obvious.

- **Non-SQL users:** Write the query, explain in plain language what it does, what filters are applied, and what the output columns mean.

Always show the full SQL in every response — never summarise or skip it.

# PART 1 — Writing SQL Queries

Use this when the user wants Claude to write the SQL directly.

## Step 1: Clarify the question

Before writing SQL, make sure you understand:

- **What entity type?** Companies/startups, investors, people, universities?

- **What geography?** Country, region, continent? (Use country_region for sub-continental groupings like Nordics, DACH — never use continent, which misclassifies Türkiye and Israel.)

- **What time range?** Remember: funding/vc_funding use integer year/month columns, not date fields.

- **What metric?** Funding amounts, counts, employee growth, valuations?

- **Row-level or aggregate?** This affects the deduplication strategy (see Step 3).

If the user's question is clear enough, proceed directly — don't over-interview.

## Step 2: Apply default filters

**Defaults apply to two query categories: VC funding and enterprise value (EV).** For all other query types, apply no defaults unless the user explicitly asks.

### VC funding queries — always apply these three exclusions

Any query that pulls VC funding data (using vc_funding, or funding with flg_is_vc_round = TRUE):

**1. Exclude outside tech:**

```sql
AND NOT EXISTS (
SELECT 1 FROM UNNEST(e.sectors) s
WHERE LOWER(s.name) = 'outside tech'
)
```

**2. Exclude mature growth stage:**

```sql
AND (e.growth_stage_desc IS NULL OR e.growth_stage_desc != 'Mature')
```

**3. Exclude SPAC private placement and grant rounds:**

```sql
AND f.round NOT IN ('SPAC PRIVATE PLACEMENT', 'GRANT')
```

These match the Dealroom platform defaults for VC funding views. vc_funding already pre-filters outside tech and mature at the table level, so those two are belt-and-braces when using vc_funding but still worth including for clarity. The SPAC PP and grant round exclusion must be applied explicitly even when using vc_funding.

### Enterprise value (EV) queries — always apply these four exclusions

**Scope — what counts as an EV query:** any query that filters, sorts, or aggregates on a valuation field (latest_valuation_usd, latest_valuation_eur, the valuations array, timeseries_data.valuation_usd), or uses flg_is_unicorn (unicorn status is itself a valuation threshold). Exit valuations live separately on funding.valuation_usd with flg_is_exit = TRUE and do not take these defaults.

**1. Exclude outside tech:**

```sql
AND NOT EXISTS (
SELECT 1 FROM UNNEST(e.sectors) s
WHERE LOWER(s.name) = 'outside tech'
)
```

**2. Exclude mature growth stage:**

```sql
AND (e.growth_stage_desc IS NULL OR e.growth_stage_desc != 'Mature')
```

**3. Exclude pre-1990 founding year (strict):**

```sql
AND e.launch_year >= 1990
```

Deliberately strict — companies with a missing launch_year are dropped. This is a departure from the skill's general NULL-handling rule; the intent is to guarantee a clean post-1990 cohort for EV analysis.

**4. Exclude 'mature company' sector tag:**

```sql
AND NOT EXISTS (
SELECT 1 FROM UNNEST(e.sectors) s
WHERE LOWER(s.name) = 'mature company'
)
```

The mature-stage (filter 2) and mature-company-tag (filter 4) exclusions overlap but are not identical — keep both.

### Mixed queries (both VC funding and EV)

For queries that touch both (e.g. "unicorns by VC raised"), take the **union of exclusions** — apply all six unique filters. The VC and EV exclusions overlap on outside tech and mature stage; the EV-only additions (launch_year >= 1990, mature company tag) just narrow further.

### Other query types — no default filters

Do not apply flg_is_startup = TRUE, flg_is_verified = TRUE, or the mature/outside tech exclusions on queries that aren't VC or EV. Let the user specify what they want filtered.

### Conditional — exclude closed companies

When the user says "exclude closed" or similar, use:

```sql
AND (e.company_status_desc IS NULL OR LOWER(e.company_status_desc) != 'closed')
```

Never use = 'operational' — that also excludes acquired companies.

## Step 3: Apply established SQL patterns

**Location deduplication — ROW_NUMBER() vs EXISTS:**

Use the right pattern depending on whether the output is row-level or aggregate:

- **Row-level output** (list of companies, Connected Sheets export) → use ROW_NUMBER() to assign each company to one region, prioritising HQ over founding:

```sql
ROW_NUMBER() OVER (
PARTITION BY e.id
ORDER BY CASE WHEN loc.flg_is_hq THEN 1 WHEN loc.flg_is_founding THEN 2 ELSE 3 END
) AS loc_rank
-- Then filter WHERE loc_rank = 1
```

- **Aggregate counts** ("how many companies in Europe") → use EXISTS to avoid losing companies that were founded in one region but moved HQ to another:

```sql
WHERE EXISTS (
SELECT 1 FROM UNNEST(e.locations) loc
WHERE (loc.flg_is_hq = TRUE OR loc.flg_is_founding = TRUE)
AND 'Europe' IN UNNEST(loc.country_region)
)
```

ROW_NUMBER() forces single-region assignment and can lose 10–15 companies in a typical European analysis.

**Default location scope depends on query type:**

| **Query type** | **Default scope** | **Reasoning** |
|:---|:---|:---|
| VC funding | **HQ-only** | Matches Dealroom platform default for VC flow; a round is attributed to where the company is headquartered at the time. |
| Enterprise value (EV) | **HQ or founding** | Captures "value originated here" — unicorns founded in a country that later moved HQ still count for the ecosystem. |
| Mixed (both) | **HQ or founding** | Entity-scope question dominates funding-attribution question. |
| Other | Specify based on user intent; default to HQ or founding if unclear. | — |

Override when the user explicitly asks for a different scope.

**Dedup implication:** with VC queries defaulting to HQ-only, row-level VC output doesn't need ROW_NUMBER() — a simple WHERE loc.flg_is_hq = TRUE in the UNNEST join gives one row per company. ROW_NUMBER() is only needed for row-level output that includes founding locations (EV, mixed, explicit HQ+founding).

**VC funding fallback** — When calculating total VC raised per company, individual rounds may be incomplete:

```sql
COALESCE(NULLIF(SUM(f.amount_usd), 0), e.total_vc_funding_usd)
```

**Deep tech filtering** — Two definitions, NOT interchangeable:

| **Term** | **Array** | **Filter** | **Companies** |
|:---|:---|:---|:---|
| Deep tech | technologies | id = 6 or LOWER(name) = 'deep tech' | ~52,000 |
| Deep tech + life sciences | sectors | LOWER(name) = 'dt and ls' | ~73,000 |

The ~40% gap materially changes any analysis. Always clarify which definition the user means. Never search sectors for "deep tech" — it returns 0 rows.

**Entity type filtering:**

- Do not apply flg_is_startup = TRUE by default — it excludes legitimately funded startups the user may want to include.

- Use flg_is_startup = TRUE only when the user explicitly asks to exclude governments, non-profits, or service providers.

- Use flg_is_company = TRUE only when the user explicitly wants all companies including corporates.

**Time range filtering on funding:**

```sql
-- "Last 12 months" using year/month integers:
WHERE (f.year > EXTRACT(YEAR FROM DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH))
OR (f.year = EXTRACT(YEAR FROM DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH))
AND f.month >= EXTRACT(MONTH FROM DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH))))
-- NEVER use f.timecreate (DB timestamp) or f.announced_on (doesn't exist)
```

**Round type filtering:**

- round — broad, always populated: SEED, SERIES A, IPO, EARLY VC, etc.

- standardised_round_label — granular (PRE-SEED, MICRO-SEED, SEED EXTENSION) but NULL for ~79% of rows

- When mixing granular + broad types, use standardised_round_label with a fallback:

```sql
(
LOWER(f.standardised_round_label) IN ('pre-seed', 'seed extension')
OR (f.standardised_round_label IS NULL AND LOWER(f.round) IN ('seed', 'series a'))
)
```

**Funding table & flag usage:**

- vc_funding = pre-filtered VC rounds, excludes outside tech + mature. No exit data.

- funding = everything. Exit data (flg_is_exit = TRUE) lives ONLY here.

- flg_is_vc_round = TRUE for VC queries. NOT flg_is_funding_round (which includes grants, debt, convertibles).

- flg_is_funding_round AND flg_is_vc_round is redundant — second alone suffices.

**Exit aggregates:**

```sql
-- For median exit valuation:
APPROX_QUANTILES(f.valuation_usd, 2)[OFFSET(1)] AS median_valuation_usd
-- Exits require: flg_is_exit = TRUE, funding table (not vc_funding)
```

**NULL handling in exclusions:** When excluding a value, BigQuery's three-valued logic means != 'X' also excludes NULLs. Always use:

```sql
(field IS NULL OR field != 'X')
```

Unless NULLs genuinely should be excluded (binary/always-populated fields).

**People data patterns:**

- Prefer standardised fields (flg_is_founder, structured titles array, university degree fields) over LIKE/REGEX on raw fields

- Dual check is the best pattern for titles:

```sql
REGEXP_CONTAINS(LOWER(po.raw_title), r'professor|researcher')
OR EXISTS (
SELECT 1 FROM UNNEST(po.titles) t
WHERE REGEXP_CONTAINS(LOWER(t.name), r'professor|researcher')
)
```

- Resolve companies to entity IDs first; fall back to LOWER(name) LIKE '%company%' only for less well-known entities

**Currency conversion:** dim_currency_rates.eur_rate = units of local currency per 1 EUR. To convert: amount_local / eur_rate. Entity-level EUR fields also available: latest_valuation_eur, valuations sub-array value_eur.

## Step 4: Choose the right table

| **Question type** | **Primary table** | **Notes** |
|:---|:---|:---|
| VC funding by year/region | vc_funding or funding + flg_is_vc_round | vc_funding pre-excludes outside tech + mature |
| Total funding incl. grants/debt | funding | Apply default exclusions manually |
| Employee/revenue/valuation trends | timeseries_data | Join on entity_id (NOT bobject_id) |
| Investor portfolios | investors + funding | UNNEST funding_investors to link |
| Founder backgrounds | people + people_organizations | Use flg_is_founder = TRUE, not LIKE on titles |
| Company counts/lists | entities | No default exclusions — let user specify filters |
| Exit data | funding only | vc_funding does NOT contain exits |
| Dealroom Signal ranking | entities | Use e.dealroom_signal.rating (STRUCT, no UNNEST) |

## Step 5: Write clean SQL

- Fully-qualified table names: `omega-dahlia-347111.dealroom_intelligence.\<table>`

- CTEs for clarity — avoid deeply nested subqueries

- CONCAT() for string concatenation (not ||)

- No SELECT *

- BigQuery GoogleSQL syntax only

# PART 2 — Prompting the BigQuery Agent

Use this when the user wants help writing a prompt to send to the Dealroom BigQuery agent.

## Core Principle

**Name the exact fields and arrays.** The agent guesses when you're vague — and often guesses wrong. Specificity is the single biggest lever for accuracy.

| **Vague prompt** | **What happens** | **Structured prompt** | **What happens** |
|:---|:---|:---|:---|
| "AI startups" | Broad regex across arrays | "technology tag 'Artificial Intelligence' in technologies array" | Exact match |
| "in Europe" | Sometimes uses continent | "country_region = 'Europe'" | Correct field |
| "deep tech" | Checks sectors (0 rows) | "technology tag 'Deep Tech' in technologies array" | Correct match |
| "exclude mature" | Skips or over-excludes | "exclude growth_stage_desc = 'Mature'" | Precise exclusion |

**Don't over-specify the SQL logic.** Name the fields, arrays, and values — the agent handles joins, CTEs, and aggregations reliably. Asking it to "think step by step" actually makes results worse.

## Prompt Template

```sql
[What you want — one sentence]
Filters:
- [Field/array]: [exact value]
- Location: [method] = [value], [HQ only for VC funding | HQ or founding for EV/unicorn/other]
- Funding: [table and flags]
- Output: [columns], [ordering], [limit]
- Show the SQL
```

**For VC funding queries, always include these three exclusions plus HQ-only location:**

```sql
- Location: HQ only (single location per company)
- Exclude sector 'outside tech' from sectors array
- Exclude growth_stage_desc = 'Mature'
- Exclude rounds: SPAC PRIVATE PLACEMENT, GRANT
```

**For EV queries (valuations, unicorns), always include these four exclusions plus HQ-or-founding location:**

```sql
- Location: HQ or founding, deduplicate so each company is counted once
- Exclude sector 'outside tech' from sectors array
- Exclude growth_stage_desc = 'Mature'
```

- Exclude launch_year \< 1990 (strict, drop NULL launch_year)

```sql
- Exclude sector 'mature company' from sectors array
```

### Example Prompt (VC funding query)

```sql
Count VC-backed startups in Europe with the following filters:
- Must have technology tag 'Artificial Intelligence' in the technologies array
- Must have industry 'health' in the industries array
- Location: country_region = 'Europe', HQ only
- Exclude sector 'outside tech' from sectors array
- Exclude growth_stage_desc = 'Mature'
- Exclude rounds: SPAC PRIVATE PLACEMENT, GRANT
- Funding: use vc_funding table OR funding table with flg_is_vc_round = TRUE
- Show: country, company count, total VC funding
- Top 15 by company count
- Show the SQL
```

**Always include "Show the SQL"** — the agent stops showing SQL after ~3 messages in a thread unless asked.

**For non-VC-funding queries**, do not auto-include the standard exclusions. Let the user specify what they want filtered.

**For NULL handling**, be explicit: "Exclude X but keep NULL values" → agent uses field != 'X' OR field IS NULL.

**For output shape**, be explicit: "Return a single number" or "Group by country only" — otherwise the agent may add unrequested GROUP BY dimensions.

## Complex Sub-Segments

For queries combining multiple sector/technology/industry filters (e.g., "medical devices AND AI but NOT pharmaceutical"):

1.  Break into sequential messages — counts → breakdowns → derived variables

2.  Catch errors at each step before building further

3.  For queries past ~200 lines, provide a SQL template and ask the agent to modify specific parts

# PART 3 — Reviewing & Correcting Agent SQL

When a user pastes agent-generated SQL, run this checklist. Most errors hit at least one of these.

## Quick Correction Checklist

**For VC funding queries, check all four defaults:**

1.  [ ] Outside tech excluded from sectors array?

2.  [ ] Mature excluded? (growth_stage_desc IS NULL OR != 'Mature') — not LIKE '%mature%'

3.  [ ] SPAC PRIVATE PLACEMENT and GRANT rounds excluded?

4.  [ ] flg_is_vc_round (not flg_is_funding_round) for VC queries?

**For EV queries (valuations, unicorns), check all four defaults:**

E1. ☐ Outside tech excluded from sectors array? E2. ☐ Mature excluded? (growth_stage_desc IS NULL OR != 'Mature') E3. ☐ launch_year >= 1990 applied (strict — drops NULLs)? E4. ☐ 'mature company' sector tag excluded from sectors array?

**General SQL correctness checks (apply to any query):**

5.  [ ] Deep tech on correct array? technologies for 'Deep Tech', sectors for 'DT and LS'

6.  [ ] country_region not continent?

7.  [ ] Location scope correct for query type? VC → HQ-only; EV/mixed → HQ or founding; other → as specified

8.  [ ] Deduplication matches output type? ROW_NUMBER() for row-level, EXISTS for aggregates (VC HQ-only doesn't need ROW_NUMBER())

9.  [ ] Right table? funding for exits, vc_funding OK for VC-only-no-exits

10. [ ] standardised_round_label used when granular round types named?

11. [ ] Not = 'operational' when user said "exclude closed"? (Excludes acquired companies)

12. [ ] Median uses APPROX_QUANTILES, not row-level list?

13. [ ] Exact array match, not LIKE '%…%' across multiple arrays?

14. [ ] All table/column names exist in schema.json? (Common agent errors: entities_timeseries_data instead of timeseries_data, raised_amount_usd_total instead of amount_usd, announced_on instead of year/month, last_valuation_usd instead of latest_valuation_usd.)

15. [ ] Date filtering uses year/month integers, not timecreate?

16. [ ] Output shape matches request? No unrequested GROUP BYs?

17. [ ] NULL handling in exclusions preserves NULLs where appropriate?

18. [ ] People queries use standardised fields (flg_is_founder, titles array) before LIKE/REGEX fallbacks?

19. [ ] No flg_is_startup = TRUE applied unless user explicitly asked? (Excludes legitimate funded startups)

20. [ ] No flg_is_verified = TRUE applied unless user explicitly asked?

### Array cheat sheet — verify the agent picked the right one:

| **Array** | **Contains** | **Examples** |
|:---|:---|:---|
| technologies | Technology tags | 'Deep Tech', 'Artificial Intelligence', 'Quantum' |
| sectors | Classification tags | 'DT and LS', 'outside tech', 'climate tech' |
| industries | Industry verticals | 'health', 'food', 'robotics', 'energy' |
| sub_industries | Granular sub-sectors | 'biotechnology', 'medical devices', 'pharmaceutical' |

If a direct industry match exists (e.g., 'space' industry), prefer the industry field over fuzzy tag matching across multiple arrays.

**Present your review as:**

- What the query does (plain English)

- Issues found (specific problems with line references)

- Corrected query (full rewritten SQL if issues are material)

- Expected impact (how issues affect the numbers — inflated? deflated? wrong grouping?)

# Common Query Templates

Starting points — adapt to the user's specific question.

### VC funding by year for a country

```sql
WITH filtered_entities AS (
SELECT e.id
FROM `omega-dahlia-347111.dealroom_intelligence.entities` e,
UNNEST(e.locations) loc
WHERE (e.growth_stage_desc IS NULL OR e.growth_stage_desc != 'Mature')
AND NOT EXISTS (SELECT 1 FROM UNNEST(e.sectors) s WHERE LOWER(s.name) = 'outside tech')
AND loc.flg_is_hq = TRUE
AND LOWER(loc.country) = 'australia'
GROUP BY e.id
)
SELECT
f.year,
SUM(f.amount_usd) AS total_vc_funding_usd,
COUNT(DISTINCT f.entity_id) AS companies_funded
FROM `omega-dahlia-347111.dealroom_intelligence.vc_funding` f
JOIN filtered_entities fe ON f.entity_id = fe.id
WHERE f.round NOT IN ('SPAC PRIVATE PLACEMENT', 'GRANT')
AND f.year BETWEEN 2015 AND 2025
GROUP BY f.year
ORDER BY f.year
```

### Unicorn count by region (aggregate — uses EXISTS, EV defaults applied)

```sql
SELECT
r AS country_region,
COUNT(DISTINCT e.id) AS unicorn_count
FROM `omega-dahlia-347111.dealroom_intelligence.entities` e,
UNNEST(e.locations) loc,
UNNEST(loc.country_region) r
WHERE e.flg_is_unicorn = TRUE
AND (loc.flg_is_hq = TRUE OR loc.flg_is_founding = TRUE)
-- EV defaults:
AND NOT EXISTS (SELECT 1 FROM UNNEST(e.sectors) s WHERE LOWER(s.name) = 'outside tech')
AND (e.growth_stage_desc IS NULL OR e.growth_stage_desc != 'Mature')
AND e.launch_year >= 1990
AND NOT EXISTS (SELECT 1 FROM UNNEST(e.sectors) s WHERE LOWER(s.name) = 'mature company')
GROUP BY r
ORDER BY unicorn_count DESC
```

Uses flg_is_unicorn → EV query → all four EV defaults apply. HQ or founding (EV default).

### Deep tech companies list (row-level — uses ROW_NUMBER)

```sql
WITH entity_region AS (
SELECT e.id, e.name,
loc.country,
ROW_NUMBER() OVER (PARTITION BY e.id
ORDER BY CASE WHEN loc.flg_is_hq THEN 1 WHEN loc.flg_is_founding THEN 2 ELSE 3 END
) AS rn
FROM `omega-dahlia-347111.dealroom_intelligence.entities` e,
UNNEST(e.locations) loc
WHERE EXISTS (SELECT 1 FROM UNNEST(e.technologies) dt WHERE dt.id = 6)
AND (loc.flg_is_hq = TRUE OR loc.flg_is_founding = TRUE)
)
SELECT id, name, country FROM entity_region WHERE rn = 1
ORDER BY name
```

Note: this is a company list query, not a VC funding query, so no default exclusions applied.

# Things That Will Silently Break Your Query

1.  **announced_on does not exist** on funding/vc_funding. Use year and month (INT64).

2.  **raised_amount_usd_total does not exist.** The field is amount_usd.

3.  **timecreate is not the round date.** It's when the record was added to the database.

4.  **entities_timeseries_data does not exist.** The table is timeseries_data. Join on entity_id.

5.  **dealroom_signal is a STRUCT, not an ARRAY.** Access with e.dealroom_signal.rating — no UNNEST.

6.  **Searching sectors for "deep tech" returns 0 rows.** Use technologies array, id = 6.

7.  **!= 'Mature' excludes NULLs too.** Use (field IS NULL OR field != 'value').

8.  **standardised_round_label is NULL for ~79% of rows.** Don't rely on it for broad filtering.

9.  **preferred_round on investors is sparsely populated.** Derive from funding participation history.

10. **company_status_desc = 'operational' excludes acquired companies.** Use != 'closed' instead.

11. **flg_is_funding_round includes grants and debt.** Use flg_is_vc_round for VC queries.

12. **Agent ORing both deep tech definitions** silently mixes 52K and 73K populations. Pick one.

13. **EV default launch_year >= 1990 drops NULLs.** Deliberate (clean post-1990 cohort) but means companies with missing launch year are silently excluded from EV analyses.

14. **last_valuation_usd does not exist** as an entity column. The field is latest_valuation_usd (with "est"); EUR equivalent is latest_valuation_eur. IPO/exit valuations live on funding.valuation_usd with flg_is_exit = TRUE — there is no ipo_valuation_usd entity column.

15. **is_founder does not exist** on people or people_organizations. The flag is **flg_is_founder** (BOOL) on both tables.

16. **growth_stage_desc values are 'Early Growth' / 'Breakout Stage' / 'Late Growth' / 'Mature'** — not 'Early' / 'Breakout' / 'Late'. Note 'Breakout Stage' (not 'Breakout Growth'). A tiny ~423-row legacy 'Early' bucket exists; fold into Early Growth. Filtering with IN ('Early','Breakout','Late') silently drops the entire 3.5M-row population.

17. **People_organizations dates are integers, not DATE columns.** Use year_start/month_start/year_end/month_end — there are no start_date/end_date columns.

# Improving the BigQuery Agent

Two approaches are being explored:

**Instruction-level changes:** Revised high-priority instructions have been drafted covering the four VC-funding exclusions (outside tech, mature, SPAC PP, grant rounds), deep tech definition, location logic, SQL visibility, and people data routing.

**Schema-level annotations:** ALTER TABLE ... SET OPTIONS(description = '...') can attach guidance directly to tables and columns. If the agent reads schema metadata, this may be more reliable than instruction text. Not yet tested at scale.

When team members discover new agent issues, document: the prompt used, the SQL produced, what's wrong, and the corrected SQL.

