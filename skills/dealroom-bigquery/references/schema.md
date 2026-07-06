# Intelligence Unit — BigQuery Schema Reference

**Core dataset:** `intelligence_unit`
**Project:** `omega-dahlia-347111`
**Core tables referenced as:** `` `omega-dahlia-347111.intelligence_unit.<table_name>` ``

> **Naming note:** the dataset is `intelligence_unit`, but the table names keep an `_iu` suffix — e.g. `entities_iu`, `funding_iu`. Always include the `_iu` suffix. The peripheral tables below (`eco_index_cities`, `dim_microapps_locations`, `power_law`, `power_law_rising_star_usa`) live in **other** datasets — see their sections for the full path.

---

## Tables Overview

| Table | Dataset | Purpose | Rows (approx) |
|---|---|---|---|
| `entities_iu` | `intelligence_unit` | Central table — companies, investors, people, universities. Distinguished by `entity_type` / `organization_subtype` | Large |
| `funding_iu` | `intelligence_unit` | All funding rounds & exit events (broad — includes grants, debt, exits, VC) | ~1M |
| `vc_funding_iu` | `intelligence_unit` | VC-only funding subset (pre-filtered: excludes outside-tech & mature-stage companies) | ~549K |
| `investors_iu` | `intelligence_unit` | Investor profiles, portfolio arrays, experience tags, LP relationships | — |
| `people_iu` | `intelligence_unit` | Individuals — founder flags, founder scores, gender, education | — |
| `people_organizations_iu` | `intelligence_unit` | Person ↔ org join table (roles, titles, tenure, founder flag) | — |
| `timeseries_data_iu` | `intelligence_unit` | Yearly snapshots per entity (employees, revenue, valuation, EBITDA, vc_funding) | — |
| `headcount_breakdown_iu` | `intelligence_unit` | Headcount split by department & country over time (LinkedIn-derived) | — |
| `web_traffic_iu` | `intelligence_unit` | Monthly website traffic (visits) per company, from SimilarWeb | — |
| `news_iu` | `intelligence_unit` | News items linked to entities — feed articles and editorial notes | — |
| `jobs_iu` | `intelligence_unit` | Active job postings per entity; join on entity_id | — |
| `dim_lists_iu` | `intelligence_unit` | Lists / landscapes — curated entity collections with categories | — |
| `dim_tags_iu` | `intelligence_unit` | Unified tag taxonomy (sectors, technologies, industries, sub_industries, SDGs, …) | — |
| `dim_locations_iu` | `intelligence_unit` | Hierarchical location dimension (continent → country_region → country → state → city) | — |
| `dim_currency_rates_iu` | `intelligence_unit` | FX rates (EUR and USD) | — |
| `eco_index_cities` | `dealroom_intelligence` | Global Tech Ecosystem Index benchmarking | — |
| `dim_microapps_locations` | `dealroom_intelligence` | High-value locations only (use when user asks for curated/high-value hubs) | — |
| `power_law` | `reporting_iu` | Investor power-law ranking model (global) | — |
| `power_law_rising_star_usa` | `reporting_iu` | Investor power-law ranking model (USA, Rising Stars tier) | — |

> ⚠️ There is **no** `vc_funding_investors` table. For investor-per-round analysis, use `vc_funding_iu` / `funding_iu` and `UNNEST(funding_investors)`.

---

## Key Join Paths


```
funding_iu.entity_id                              → entities_iu.id
vc_funding_iu.entity_id                           → entities_iu.id
funding_iu.funding_investors (UNNEST)             → investors_iu.bobject_investor_id
vc_funding_iu.funding_investors (UNNEST)          → investors_iu.bobject_investor_id
investors_iu.entities_invested_in (UNNEST)        → entities_iu.id
people_organizations_iu.person_id                 → entities_iu.id  (where entity_type = 'person')
people_organizations_iu.entity_id                 → entities_iu.id  (where entity_type = 'organization')
people_iu.id                                      → entities_iu.id  (person entity)
people_iu.founded_entities_ids (UNNEST)           → entities_iu.id
people_iu.universities (UNNEST).bobject_university_id → entities_iu.id  (where organization_subtype = 'university')
timeseries_data_iu.entity_id                      → entities_iu.id
headcount_breakdown_iu.entity_id                  → entities_iu.id
web_traffic_iu.entity_id                          → entities_iu.id
news_iu.mentioned_entities (UNNEST).id            → entities_iu.id
jobs_iu.entity_id                                 → entities_iu.id
dim_lists_iu.entity_ids (UNNEST).entity_id        → entities_iu.id
Entity arrays (sectors, technologies, industries, sub_industries) UNNEST → dim_tags_iu.id
Entity locations array UNNEST → dim_locations_iu by name/id
```


---

## Entities Table (`entities_iu`) — Key Fields

### Identity & Classification Flags
- `id` (NUMERIC) — primary key; `uuid` — stable UUID
- `name`, `tagline`, `about`, `summary` (AI-generated short summary)
- `entity_type` (STRING) — `'person'` or `'organization'` — use this instead of old `flg_is_person` / `flg_is_organization`
- `organization_subtype` (STRING) — for organizations: `'company'`, `'university'`, `'gov_ngo'`, `'investor'` — use this instead of old `flg_is_company` / `flg_is_university` (note: the value is `'investor'`, not `'fund'`)
- `flg_is_startup`, `flg_is_investor` — still present
- **Entity-level role flags (persons only):** `flg_is_founder`, `flg_is_executive`, `flg_is_partner`
- `flg_is_unicorn` — current unicorn status ($1B+ valuation)
- `flg_is_rising_star`, `flg_is_colt`, `flg_is_thoroughbred`, `flg_is_titan`
  - `flg_is_colt` — revenue $25M–$100M, excluding Verified Thoroughbreds
  - `flg_is_thoroughbred` — member of the "Verified Thoroughbreds" sector (sector_id 22843); curated as startups that reached $100M revenue (it's a sector-tag membership, not a live revenue threshold)
- `growth_stage`, `growth_stage_desc` — production literal values (filter with these exact strings):
  - `'Seed'` (growth_stage = 1)
  - `'Early Growth'` (growth_stage = 2) — total funding <$15M and/or <50 employees and/or valuation <$100M
  - `'Breakout Stage'` (growth_stage = 6) — total funding $15M–$100M and/or 50–500 employees and/or valuation $100M–$500M (note: "Stage", **not** "Growth")
  - `'Late Growth'` (growth_stage = 3) — total funding >$100M and/or >500 employees and/or valuation >$500M; includes unicorns and thoroughbreds
  - `'Mature'` (growth_stage = 4) — companies founded before 1990
  - `'Not meaningful'` (growth_stage = 5) — stage not applicable or indeterminate
  - (scalar `growth_stage` int also joins to `dim_tags_iu` where `tag_type = 'growth_stage'`)
- `company_status`, `company_status_desc` — values: `'Operational'`, `'Acquired'`, `'Closed'` (others may exist). Use `company_status_desc` for filtering. Do NOT use `= 'Operational'` to mean "still alive" — that excludes Acquired companies; use `!= 'Closed'` instead.
- `launch_year`, `launch_month`, `year_became_unicorn` — `launch_year` is the year the entity was founded/launched
- `total_funding_usd`, `total_vc_funding_usd` — entity-level aggregates
- `latest_valuation_usd`, `latest_valuation_eur`, `valuation_year`, `valuation_month` — most recent known company valuation (note: `latest_…`, not `last_…`). IPO/exit valuations live in `funding_iu.valuation_usd` with `flg_is_exit = TRUE`, not as a separate entity column.

### Nested Arrays (require UNNEST)
- `locations` — ARRAY<STRUCT<id, city, state, country, continent, city_id, state_id, country_id, continent_id, city_unique_id, state_unique_id, country_unique_id, continent_unique_id, city_region, country_region, city_region_ids, country_region_ids, city_region_unique_ids, country_region_unique_ids, lat, lon, flg_is_hq, flg_is_founding>>
  - `*_id` fields join `dim_locations_iu.id` (with matching `location_type`); `*_unique_id` fields join `dim_locations_iu.unique_id` directly (no type filter needed)
- `sectors` — ARRAY<STRUCT<id, name>>
- `technologies` — ARRAY<STRUCT<id, name>>
- `industries` — ARRAY<STRUCT<id, name>>
- `sub_industries` — ARRAY<STRUCT<id, name>>
- `techstack_categories`, `ownerships`, `business_model`, `income_stream`, `sdgs`, `client_focus` — ARRAY<STRUCT<id, name>> (client_focus values: b2b / b2c)
- `fundings` — ARRAY<STRUCT<id, round, year, month, amount_usd, flg_is_vc_round, flg_is_vc_backed_round, flg_is_pe_round, flg_is_exit, ...>> (denormalised copy of funding rounds); `flg_is_pe_round` = TRUE for BUYOUT or GROWTH EQUITY NON VC rounds
- `valuations` — ARRAY<STRUCT<...>>
- `revenues` — ARRAY<STRUCT<...>>

### Dealroom Signal (STRUCT — no UNNEST needed, use dot notation)
- `dealroom_signal.rating` — overall composite score (0–100)
- `dealroom_signal.completeness`
- `dealroom_signal.team_strength`
- `dealroom_signal.growth_rate`
- `dealroom_signal.timing`

All NUMERIC type. Access directly: `e.dealroom_signal.rating`

---

## Funding Table (`funding_iu`) — Key Fields

**CRITICAL DATE FIELDS:** This table uses integer `year` (INT64) and `month` (INT64) columns for dates. There is **NO** `announced_on` field. When filtering by time range, reconstruct from these integers.

**CRITICAL AMOUNT FIELD:** The amount field is `amount_usd`, **NOT** `raised_amount_usd_total`.

**CRITICAL TIMESTAMP WARNING:** `timecreate` is a database record creation timestamp, **NOT** the round date. Never use it for "last 12 months" or any time-range filtering.

- `id` (NUMERIC) — primary key
- `entity_id` → entities_iu.id
- `year` (INT64), `month` (INT64) — the round date
- `amount_usd` (NUMERIC) — round amount in USD
- `round` (STRING) — primary round classifier, always populated. Values include: SERIES A, SERIES B, SEED, PRE-SEED, EARLY VC, LATE VC, GROWTH EQUITY, ANGEL, DEBT FINANCING, GRANT, CONVERTIBLE NOTE, SPAC PRIVATE PLACEMENT, IPO, MERGER/ACQUISITION, SECONDARY MARKET, etc.
- `standardised_round_label` (STRING) — granular VC equity label. More precise (MICRO-SEED, PRE-SEED, SEED, SEED+, SEED EXTENSION, SERIES A, SERIES A EXTENSION, etc.) but NULL for ~790K of ~1M rows. Use only when you need precise stage breakdowns within VC rounds.
- `flg_is_vc_round` (BOOLEAN) — TRUE for VC rounds
- `flg_is_vc_backed_round` (BOOLEAN) — TRUE for VC-backed defining rounds
- `flg_is_pe_round` (BOOLEAN) — TRUE for private equity rounds (BUYOUT or GROWTH EQUITY NON VC)
- `flg_is_funding_round` (BOOLEAN) — TRUE for all funding rounds (including debt, grants)
- `flg_is_exit` (BOOLEAN) — TRUE for exits (IPO, M&A)
- `flg_is_verified` (BOOLEAN) — TRUE for verified rounds. Apply only when the user explicitly asks for verified rounds only.
- `funding_investors` — ARRAY<STRUCT<bobject_investor_id, flg_is_lead_investor>>

---

## VC Funding Table (`vc_funding_iu`)

Pre-filtered subset of `funding_iu` — contains only VC rounds and automatically excludes outside-tech and mature-stage companies at the table level. Same column structure as `funding_iu`. Use this when the query is purely about VC investment.

Same date field rules apply: `year` and `month` integers, `amount_usd` for the amount, no `announced_on`.

---

## Investors Table (`investors_iu`) — Key Fields

- `bobject_investor_id` → join target for funding_investors array
- `investment_stages` — ARRAY of investment stage labels (derived from Dealroom flags)
- `entities_invested_in` — ARRAY<INT64> of entity IDs the investor has backed
- `investor_types`, `deal_structure`, `industry_experience`, `sub_industry_experience`, `tags_experience`, `country_experience` — derived experience/portfolio classifications
- `min_deal_size`, `max_deal_size`, `total_funding_usd`, `total_funding_eur`
- `funds` — ARRAY<STRUCT<fund_id, fund_name, amount, currency, fund_type, flg_is_closed, fund_date, source_url>>; `fund_date` is a STRING, cast with `CAST(LEFT(fund_date, 10) AS DATE)`
- `known_limited_partners`, `lp_investments` — LP relationships

Note: An investor's "most-frequent round type" is NOT a pre-computed reliable field. To derive it, use a CTE that counts their `funding_iu` participations by `round` and picks the mode.

---

## People & People_Organizations Tables (`people_iu`, `people_organizations_iu`)

**people_iu:**
- `id` → entities_iu.id (person entity)
- `founded_entities_ids` — ARRAY of entity IDs the person founded
- `founder_score` (INT64)
- `gender`, `gender_desc`
- `universities` — ARRAY<STRUCT<education_id, bobject_university_id, degree, majors, year_start, year_end>>; `education_id` is the stable enrollment record id (join key for downstream education-linked tables)
- `flg_is_founder`, `flg_is_serial_founder`, `flg_is_promising_founder`, `flg_is_strong_founder`, `flg_is_super_founder`

**people_organizations_iu:**
- `person_id` → people_iu.id / entities_iu.id (person)
- `entity_id` → entities_iu.id (organisation)
- `raw_title` — raw unstructured title text as originally entered
- `titles` — ARRAY<STRUCT<id, name>> of structured/standardised job titles
- `flg_is_founder` (BOOL) — whether the person is a founder of this organisation
- `flg_is_past` (BOOL)
- `year_start`, `month_start`, `year_end`, `month_end` — tenure dates (integers, NOT `start_date`/`end_date`)

For people data, use standardised field values (e.g., `flg_is_founder = TRUE`) rather than LIKE/REGEX on title strings. For title matching, prefer the structured `titles` array; fall back to regex on `raw_title` only as a secondary check.

---

## Timeseries_Data Table (`timeseries_data_iu`)

**IMPORTANT:** The table name is `timeseries_data_iu`, **NOT** `entities_timeseries_data`. Join on `entity_id`, **NOT** `bobject_id`.

- `entity_id` → entities_iu.id
- `year` (INT64)
- `employees` — forward-filled
- `revenue_usd` — forward-filled
- `valuation_usd` — forward-filled
- `ebitda_usd` — forward-filled
- `vc_funding_usd` — annual sum (NOT forward-filled)

---

## Headcount_Breakdown Table (`headcount_breakdown_iu`)

Company headcount split by department and by country over time (LinkedIn-derived). One row per entity / breakdown_type / item / period. Companies only.

- `entity_id` → entities_iu.id
- `breakdown_type` (STRING) — `'department'` or `'country'`
- `item_id` — department id, or country location id (`dim_locations_iu.id` where `location_type = 'country'`)
- `item_name` — resolved department / country name
- `year`, `month`, `period_date` (DATE — first day of the month)
- `percentage` — 0–100 share of headcount for this item in the period (items within a period sum to ~100; shortfall is unattributed)

Latest period per (entity, breakdown_type) → the pie; earlier periods → the over-time view.

---

## Web_Traffic Table (`web_traffic_iu`)

Monthly estimated website traffic (visits) per company, from SimilarWeb. One row per entity per month. Companies only.

- `entity_id` → entities_iu.id
- `year`, `month`, `period_date` (DATE — first day of the month)
- `visits` — estimated total website visits in the month

---

## Dim_Lists Table (`dim_lists_iu`)

Lists / landscapes — curated entity collections. One row per list.

- `id`, `title`, `summary`, `description`, `type`
- `list_creator_id` — bobject ID of the creator
- `flg_is_public`, `flg_is_featured`, `flg_is_special`, `flg_is_visible`
- `entities_count` — number of distinct entities in the list
- `landscape_categories` — ARRAY<STRUCT<id, title, summary, description, order, …>>
- `entity_ids` — ARRAY<STRUCT<id, entity_id, timecreated, …>>; `entity_id` → entities_iu.id
- `users` — ARRAY<STRUCT<person_id, timecreated>>; `person_id` → entities_iu.id (where entity_type = 'person')

---

## Dim_Locations Table (`dim_locations_iu`)

Hierarchical location dimension supporting multiple granularity levels.

- `id`, `name`, `name_norm`, `searchable_text`
- `location_type` — values: **city, state, city_region, country, country_region, continent**
- `aliases` — ARRAY<STRING>
- `state_parent`, `country_parent`, `continent_parent` — STRING (single ancestor name)
- `state_parent_id`, `country_parent_id`, `continent_parent_id` — INT64 ids; join `dim_locations_iu.id` with matching `location_type`
- `state_parent_unique_id`, `country_parent_unique_id`, `continent_parent_unique_id` — INT64; join `dim_locations_iu.unique_id` directly
- `region_parent` — ARRAY<STRING>; `region_parent_ids` — ARRAY<INT64>; `region_parent_unique_ids` — ARRAY<INT64>
- `city_region_parent` — ARRAY<STRING>; `city_region_parent_ids` — ARRAY<INT64>; `city_region_parent_unique_ids` — ARRAY<INT64>
- `display_name`, `display_location_type`
- `lat`, `lon`, `population`, `gdp_millions_dollars`
- `flg_is_curated`, `flg_in_eco_index_2026`

**Key geography concepts:**
- `country_region` is the preferred regional grouping level (e.g., "Nordics", "DACH", "Southern Europe"). Use this over `continent` for regional analyses — it gives you meaningful sub-continental groupings.
- Turkey and Israel sit in `country_region` groups that differ from their `continent` classification — always use `country_region` for these edge cases.

---

## Dim_Tags Table (`dim_tags_iu`)

Unified tag taxonomy for all classification arrays on entities.

- `id`, `unique_id` (`id * 100 + tag_type_id`, collision-free), `name`, `name_norm`, `description`, `searchable_text`
- `is_muted` (BOOL) — for sector tags, TRUE if the sector is muted (hidden/deprioritised); NULL for other tag types
- `is_approved` (BOOL) — for sector and category tags, TRUE if the tag is approved in source; NULL for other tag types
- `tag_type` — values: **sector, technology, category, sub_category, sdg, techstack_category, ownership, business_model, income_stream, deal_structure, client_focus, growth_stage**
- `parent_id` — for sub_category rows, references parent category id
- `aliases` — ARRAY<STRING>

**`tag_type` → entity field mapping:** `sector`→`sectors`, `technology`→`technologies`, `category`→`industries`, `sub_category`→`sub_industries`, `sdg`→`sdgs`, `techstack_category`→`techstack_categories`, `ownership`→`ownerships`, `business_model`→`business_model`, `income_stream`→`income_stream`, `client_focus`→`client_focus`, `deal_structure`→`investors_iu.deal_structure`, `growth_stage`→`entities_iu.growth_stage` (scalar int).

**Key tag IDs and definitions:**
- Deep tech technology tag: `id = 6` in `technologies` array (~52,000 companies)
- "DT and LS" (deep tech + life sciences) in `sectors` array (~73,000 companies) — NOT interchangeable with the above; ~40% gap
- "Outside tech" appears in `sectors` — filter with `LOWER(s.name) = 'outside tech'`
- "Deep tech" does NOT exist as a sector tag — searching sectors for it returns 0 rows. Always use `technologies` with id = 6.
- "Verified Thoroughbreds" sector: `id = 22843` — drives `flg_is_thoroughbred`.

---

## News Table (`news_iu`)

One row per news item (AI-summarised feed articles + editorial notes). `id` (INT64) is the primary key.

- `id` (INT64) — news item id (primary key)
- `slug` (STRING) — unique URL-friendly identifier
- `title` (STRING)
- `content` (STRING) — text body; may contain HTML
- `source_urls` — ARRAY<STRING> — external source URL(s)
- `images` — ARRAY<STRUCT<id, name, flg_is_primary>>; prepend `https://sg-imgs.dealroom.co/<name>` to render
- `pub_datetime` (TIMESTAMP) — publication timestamp (UTC)
- `news_types` — ARRAY<STRUCT<id, name>> — values: Funding rounds, Mergers and acquisitions, Financial milestones, Product announcements, IPO, Key hires, Market expansion, Investor fundraising, Layoffs
- `importance_score` (INT64) — editorial/ranking importance of the item
- `flg_is_pinned` (BOOL) — the single most prominent pinned top story
- `mentioned_entities` — ARRAY<STRUCT<id, uuid, name, website, sector, hq_country>>; join `id` to `entities_iu.id`
- `fundings` — ARRAY<STRUCT<id, round, standardised_round_label, amount_eur, amount_usd, date>> — funding rounds the article reports on; empty when not a funding article
- `timecreate`, `timeupdate`

---

## Jobs Table (`jobs_iu`)

Active job openings per entity. Join `entity_id` to `entities_iu.id`. Coverage is uneven — `title`, `url`, `date_posted`, `city`, `country`, and `job_type` are well-populated; salary and department fields are sparse (mostly NULL from Predict Leads, ~99% of volume).

- `id` (INT64) — unique job id
- `entity_id` (INT64) → entities_iu.id (hiring company)
- `title` (STRING), `url` (STRING), `source` (STRING — e.g. 'Predict Leads', 'Welcome To The Jungle')
- `job_type` (STRING — e.g. engineering, sales); `city`, `country`, `formatted_location`
- `post_language`, `latitude`, `longitude`
- `date_posted` (TIMESTAMP), `expired_date` (TIMESTAMP)
- `salary_min`, `salary_max` (FLOAT64), `currency` (STRING) — sparse
- `department` (STRING), `contract_type` (STRING) — sparse

---

## Dim_Currency_Rates Table (`dim_currency_rates_iu`)

- `currency` (STRING — code), `currency_name` (STRING)
- `eur_rate`, `usd_rate` (FLOAT64)

---

## Power_Law Table

**Dataset:** `reporting_iu` — full path: `` `omega-dahlia-347111.reporting_iu.power_law` ``

Investor power-law ranking model for global markets. **GRAIN: one row per (investor × region × region_type × sector × sector_type).** Always filter on both region/region_type and sector/sector_type together to avoid double-counting.

**Common query patterns:**
- Global, all sectors (one row per investor): `region = 'Global' AND region_type = 'country_region' AND sector_type = 'global'`
- EMEA, all sectors: `region = 'EMEA' AND region_type = 'country_region' AND sector_type = 'global'`
- Country, all sectors: `region_type = 'country' AND sector_type = 'global'`
- Sector slice (e.g. Fintech × EMEA): `region = 'EMEA' AND region_type = 'country_region' AND sector = 'Fintech' AND sector_type = 'sector'`

**Exclusions:** BANKRUPTCY rounds excluded; `preferred_round = 'SUPPORT PROGRAM'` excluded; only `score_total > 0` rows included.

**Investor identity:**
- `bobject_investor_id`, `investor_name`, `investor_country`, `investor_type`, `sub_types`, `preferred_round`, `launch_year`, `age`, `link`

**Geography:**
- `region` — geographic label (e.g. 'Global', 'EMEA', 'Germany', 'Greater London')
- `region_type` — `'country_region'` (named groupings: Global, EMEA, Nordics…), `'country'`, `'city_region'`
- `sector`, `sector_type` — `'global'` (no filter), `'sector'`, `'technology'`, `'category'`, `'sub_category'`

**Portfolio counts** (by tier × entry stage):
- `unicorn_seed/early/late` — unicorns (valuation ≥ $1B)
- `tb_seed/early/late` — Thoroughbreds (sector_id = 22843)
- `colt_seed/early` — Colts (non-TB, founded ≥1990, revenue $25M–$100M)

**Portfolio names** — comma-separated strings: `unicorn_*_names`, `tb_*_names`, `colt_*_names`, `lead_unicorn_*_names`, `lead_tb_*_names`, `lead_colt_*_names`

**Scores:**
- `unicorn_seed/early/late_score` (×100/30/10), `tb_seed/early/late_score` (×100/30/10), `colt_seed/early_score` (×25/7.5)
- `score_total` — composite score; formula: (unicorn_seed×100)+(unicorn_early×30)+(unicorn_late×10)+(tb_seed×100)+(tb_early×30)+(tb_late×10)+(colt_seed×25)+(colt_early×7.5)
- `unicorn_rank`, `decacorn_rank` — raw portfolio counts for ranking

**Activity & fund:**
- `rounds_since_1990`, `rounds_2024`, `rounds_2025`, `activity` ('active'/'inactive')
- `last_fund_amount`, `last_fund_date`, `fund_status`, `funds_names`, `aum`

**Ranking:**
- `region_cume_dist` — PERCENT_RANK within slice (0.0 = best)
- `percentile` — `'Top 0.1%'`, `'Top 1%'`, `'Top 2.5%'`, `'Top 10%'`, `'Top 50%'`, `'Bottom 50%'`

---

## Power_Law_Rising_Star_USA Table

**Dataset:** `reporting_iu` — full path: `` `omega-dahlia-347111.reporting_iu.power_law_rising_star_usa` ``

Same structure as `power_law` but scoped to the **United States**, with Rising Stars replacing Colts as the third tier.

**GRAIN:** one row per (investor × region × region_type × sector × sector_type).

**Common query patterns:**
- US overall (one row per investor): `region = 'United States' AND region_type = 'country' AND sector_type = 'global'`
- State-level: `region_type = 'state' AND sector_type = 'global'`
- US macro-region: `region_type = 'us_region' AND sector_type = 'global'`

**Geography differs from power_law:**
- `region_type` values: `'country'` (United States), `'state'` (e.g. California), `'us_region'` (e.g. Northeastern United States)

**Third tier — Rising Stars** (replaces Colts):
- `rising_star_seed/early` — non-TB companies: founded ≥2020, signal ≥85, privately held, valuation <$1B, non-unicorn
- Only seed and early tiers (no late)
- `rising_star_*_names`, `lead_rising_star_*_names`
- `rising_star_seed/early_score` (×25/7.5)
- `score_total` formula: (unicorn_seed×100)+(unicorn_early×30)+(unicorn_late×10)+(tb_seed×100)+(tb_early×30)+(tb_late×10)+(rising_star_seed×25)+(rising_star_early×7.5)

All other columns (`unicorn_*`, `tb_*`, investor identity, activity, fund, ranking) are identical to `power_law`.

**Conversion logic:** `eur_rate` = units of local currency per 1 EUR. To convert to EUR: `amount_local / eur_rate`. Entity-level EUR fields are also available: `latest_valuation_eur`, valuations sub-array `value_eur`.
