---
name: dealroom-early-access-api
description: >-
  Use this skill whenever the user is building against the Dealroom API OR asking
  you to look up Dealroom data conversationally (the next-gen REST API at
  api-next.beta.dealroom.co) - querying companies, startups, investors, funds,
  founders, people, funding rounds, valuations, news, jobs, or any Dealroom data.
  Triggers on "I have a Dealroom API key", "query the Dealroom API", "fetch
  startups", "build a server-side VC/scouting dashboard", "funding analytics", and on
  one-off conversational lookups like "show me X from Dealroom", "top startups in
  <sector/region>", "who invested in <company>", "how much has <company> raised", or
  any project that calls api-next.dealroom.co / api-next.beta.dealroom.co. Walks the
  user through Programmatic (M2M) API-key generation, sets up the OAuth2 client-credentials flow with
  automatic token refresh, picks the right endpoint for the question (transactional
  vs aggregate), and routes to the live OpenAPI spec and Mintlify docs. If the user
  mentions investors, fundings, startup ecosystems, scouting, VC data, unicorns,
  valuations, or the Dealroom platform, check whether this skill applies first.
---

# Dealroom API consumer guide

How to build against the Dealroom next-gen REST API: authenticate, pick the right
endpoint, and discover filters from the live API instead of guessing.

This skill covers **Programmatic (M2M) API usage**. Application (PKCE) keys for browser
SPAs also exist (read-only, created from the same settings page), but this skill does not
cover that flow.

This skill holds only the durable parts (auth, endpoint judgment, discovery mechanism,
pointers). Endpoint shapes, the full filter catalog, and field lists live in the API
itself and the docs, which are the single source of truth. Always read those for
specifics rather than relying on memory.

## Read this before building anything

Two failure modes cause almost every stuck integration. Avoid both:

1. **Don't guess endpoint paths, filter keys, or operator syntax.** Hallucinated names
   that "look right" return empty results or `400`s. Discover filters at runtime with
   `GET /api/reference/filters?scope=<scope>` and confirm shapes against the OpenAPI spec.
2. **Don't default to aggregate endpoints.** This is the most common mistake. Most
   questions want *records*, not a computed statistic. See below.

This is an early-access API and can change without notice. If the live behavior conflicts
with this skill, trust the API and flag it: see
[When the API disagrees with this skill](#when-the-api-disagrees-with-this-skill).

## Choosing the right endpoint

The most important decision. Pick by what the answer *is*, not by how analytical the
question sounds.

> **Rule of thumb:** If the user wants to *see things* (a list of companies, the rounds
> of one startup, who invested in X), use a **transactional / list** endpoint. If they
> want a *number or a chart of numbers* computed across many rows (count, sum, average,
> median, distribution, trend, cross-tab), use an **aggregate** endpoint. When in doubt,
> start transactional.

List endpoints already return rich nested objects (funding summary, latest valuation,
tags, founders) and a `page.total` count, so you rarely need a separate aggregate just to
enrich or count a result set.

| The user wants                                                   | Use                                                                | Not                          |
| ---------------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------- |
| A list of companies / investors / people matching criteria       | `GET /api/data/entities` (or `/data/investors`, `/data/founders`, `/data/people`) | aggregate     |
| The "top N by funding / valuation / signal"                      | list + `sort=-<field>` + `limit=N`                                 | aggregate group_by           |
| Everything about one entity                                      | `GET /api/data/entities/{id}`                                      | aggregate                    |
| One entity's rounds / valuations / investors / portfolio / team  | typed collections (see below): `GET /api/data/companies/{id}/{funding-rounds,valuations,investors,team}`, `/api/data/investors/{id}/{portfolio,funds}` | aggregate |
| All funding rounds matching criteria                             | `GET /api/data/transactions`                                       | aggregate                    |
| All valuations matching criteria (cross-entity)                  | `GET /api/data/valuations`                                         | aggregate                    |
| Fund vehicles investor firms have raised (cross-manager)         | `GET /api/data/funds`                                              | `/api/data/investors`        |
| Points to plot on a map                                          | `GET /api/data/{companies,investors,universities}/geo` (slim dots; see below) | a full list call you then thin client-side |
| How many entities match (just the count)                         | the list call's `page.total` (`include_total=true`)                | an aggregate for a bare count |
| A count / sum / avg / median grouped by a dimension              | `GET /api/analytics/aggregate/{source}`                            | paging the list and reducing client-side |
| Several metrics at once (KPIs, leaderboards)                     | `GET /api/analytics/aggregate/{source}/multi-metric`               | many separate calls          |
| A 2D matrix, stage transitions, or a per-year trend              | `GET /api/analytics/funding-analytics/{heatmap,round-transitions,funnel}`, `/api/analytics/timeseries` |        |
| Fuzzy name lookup ("find Stripe")                                | `GET /api/data/search` (all five collections; narrow with `types=`) | an `/api/data/entities` name filter |
| Ranked investor recommendations for a target company             | `GET /api/analytics/matching/investors`                            | hand-rolled portfolio-overlap queries |
| Companies / investors similar to a given one                     | `GET /api/data/companies/{id}/similar`, `/api/data/investors/{id}/similar` | building your own tag-overlap ranking |

**Anti-patterns:**

- **Ranking entities via aggregate.** `group_by` groups by a *dimension* (country, year,
  sector), not by entity. To rank companies, use the list endpoint with `sort`.
- **Aggregating to count.** A list response already returns `page.total`.
- **Aggregating one entity.** Profile data lives on the typed-collection sub-resources
  (see below).
- **The reverse mistake:** paging thousands of list rows to sum/average client-side. That
  is exactly what `GET /api/analytics/aggregate/{source}` is for.

**Relationship sub-resources are facet-scoped by entity type.** They are *not* on
`/api/data/entities/{id}` (that path carries only the detail record plus `lp-funds`).
Read the entity's `type` / `organization_subtype` / `is_investor` / `is_founder` flags
from the detail payload, then call the matching typed collection. The paths are static
and knowable:

- **Companies** (`/api/data/companies/{id}/`): `funding-rounds`, `valuations`,
  `financials`, `investors`, `team`, `headcount-breakdown`, `web-traffic`, `similar`
- **Investors** (`/api/data/investors/{id}/`): `portfolio`, `funds`,
  `lp-funds`, `team`, `similar`
- **People / founders / universities**: `/api/data/people/{id}/career`,
  `/api/data/founders/{id}/founded-companies`, `/api/data/universities/{id}/alumni`,
  and `team` on universities / gov-ngo

The `similar` collections rank by weighted tag overlap (force-sorted by score), accept
the full company/investor filter DSL to narrow the pool, and use offset pagination
capped at `offset + limit <= 1000`.

**Map points have their own slim lens.** `GET /api/data/{companies,investors,universities}/geo`
returns one point per entity (id, name, coordinates) instead of the full list payload, takes
the same `filter` as its list endpoint, and accepts `size_by=<numeric dimension>` (e.g.
`total_funding`, `employee_count`, `latest_valuation`, `total_invested`,
`total_investments_count`, `alumni_count`, `alumni_founder_count`) to return each point's
`value` for proportional sizing. `size_by` also sorts descending, so a capped response keeps
the highest-value points; entities without usable coordinates are omitted. For per-area
counts (a choropleth rather than dots) use
`GET /api/analytics/aggregate/companies?metric=count&group_by=map_area` instead. The older
generic `GET /api/data/entities/geo` still exists (no `size_by`, higher limits) but prefer
the per-collection endpoints.

## Setup

Steps 1-2 apply to both modes; run them on the first turn and skip what is already done.
Step 3 is only for app builds (see [Two ways to call the API](#two-ways-to-call-the-api)).

1. **Generate an API key (the user must do this).** Auth0 needs a logged-in browser, so
   you cannot do it for them. Tell them: open
   <https://app-next.beta.dealroom.co/settings/api>, click **+ Create key**, choose
   **Programmatic (M2M)**, and copy both `client_id` and `client_secret` (the secret is
   shown only once).
2. **Store the credentials in `.env`.** Copy `assets/.env.example` and fill in
   `DEALROOM_CLIENT_ID` and `DEALROOM_CLIENT_SECRET`. Optionally set
   `DEALROOM_USER_AGENT` for server-side observability. Confirm `.env` is in `.gitignore`.
3. **App builds only - copy a client snippet.** Python: `cp <skill-path>/assets/snippets/dealroom.py ./`
   then `pip install authlib requests python-dotenv`. Node/TS: copy `dealroom.ts` plus
   `assets/package.json` and `assets/tsconfig.json` (the ESM config the snippet needs), then
   `npm install` and verify with `npm run sanity`. Both read `.env`, send the headers, and
   mint and refresh tokens automatically. For one-off conversational queries, skip this and
   use curl (next section).

## Two ways to call the API

Match the tool to the job. Do not scaffold a project or write a script just to answer a
question; do not hand-mint tokens in a loop inside a real program.

**Conversational / ad-hoc - you answering a question now: run curl directly.** This is the
default when the user asks you to look something up, explore, or sanity-check data. Mint one
token per session, reuse it across calls, and pass each filter with `curl -G
--data-urlencode` so the `[`, `]`, and `|` metacharacters survive the shell. No files, no
project, no snippet.

```bash
# Load credentials and mint a token ONCE per session (24h lifetime); reuse $TOKEN after.
set -a && . ./.env && set +a
TOKEN=$(curl -s https://accounts.beta.dealroom.co/oauth/token \
  -H 'Content-Type: application/json' \
  -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"$DEALROOM_CLIENT_ID\",\"client_secret\":\"$DEALROOM_CLIENT_SECRET\",\"audience\":\"https://api-next.beta.dealroom.co\"}" \
  | jq -r .access_token)

curl -s -G 'https://api-next.beta.dealroom.co/api/data/entities' \
  --data-urlencode 'filter=and(organization_subtype[eq]:company,tag_id[in_any]:42|99)' \
  --data-urlencode 'sort=-total_funding' --data-urlencode 'limit=5' \
  -H "Authorization: Bearer $TOKEN" -H "X-Client-Id: $DEALROOM_CLIENT_ID" | jq
```

**Building an app or anything repeated - code that outlives the session: use the snippet.**
Copy `dealroom.py` / `dealroom.ts` into the project. It reads `.env`, sends the headers, and
re-mints the token on a `401` automatically - which raw curl will not do when the 24h token
expires mid-run. This is the right path inside any program, loop, or multi-query tool.

**Pitfall either way: never put raw `[ ] |` in a curl URL string.** Use `-G
--data-urlencode` per parameter (or the snippet's structured params). Bare brackets in the
URL are the single biggest cause of agents writing throwaway escape scripts.

## Authentication

- **Flow:** OAuth2 client-credentials (machine-to-machine). Exchange `client_id` /
  `client_secret` for a Bearer token, then send it on every call. The snippets do this
  for you.
- **Two mandatory headers on every request:** `Authorization: Bearer <token>` and
  `X-Client-Id: <client_id>` (missing it is a `400`). A custom `User-Agent` is optional
  and useful for server-side observability, but it is not part of authentication.
- **Token lifetime:** 24h. Cache and reuse; do not mint per call. Snippets refresh on
  `401`. A key deactivated in the UI is rejected on its next request even while its token is
  still inside that 24h window, so a `401` that survives one refresh means the key is dead,
  not expired: stop and tell the user rather than re-minting in a loop.
- **Mutations** (POST / PATCH / PUT / DELETE) additionally need the relevant write/delete
  permission on the key.

### A missing token does not fail loudly - check that your auth applied

Read endpoints also serve **anonymous** callers (that is how public ecosystem pages work), so
a request with no or a dropped `Authorization` header returns `200` with a thinner row rather
than `401`. Two markers tell you which principal the API actually saw:

- `page.tier` - `anonymous` / `free` / `premium`, alongside `page.capped` and
  `page.ecosystem`. Present only for non-M2M callers on capped resources.
- `locked[]` - a top-level array of `{ field, reason, unlock }` for fields redacted (nulled,
  not omitted) at that tier, e.g. `{ "field": "website", "reason": "ACCOUNT_REQUIRED",
  "unlock": "signup" }`. Added only when something was actually redacted.

**A `page.tier` of `anonymous` or a `locked[]` on a call you made with a key means your
credentials did not apply.** Fix the headers; do not report the nulls as missing data. M2M
callers are exempt from field redaction and from the per-tier page-size and pagination-depth
caps below, so a correctly authenticated response has neither marker.

The default environment is **beta**. For other environments, swap the base URL and Auth0
host (the OAuth2 `audience` equals the API base URL):

| Environment | API base URL                            | Auth0 host                      |
| ----------- | --------------------------------------- | ------------------------------- |
| Beta        | `https://api-next.beta.dealroom.co`     | `accounts.beta.dealroom.co`     |
| Production  | `https://api-next.dealroom.co`          | `accounts.dealroom.co`          |
| Staging     | `https://api-next.staging.dealroom.dev` | `accounts.staging.dealroom.dev` |

## API versioning

The API is **date-versioned** (Stripe-style). Send an optional `API-Version: YYYY-MM-DD`
header to pin behavior; **omit it to get the latest version** (what new integrations
should do). Clients pinned to an older date keep their old request/response shapes via
server-side transforms until that version's sunset date, so existing code does not break
when the API moves.

Every breaking change, deprecation, and addition is listed in the
**[changelog](https://developers.beta.dealroom.co/changelog)** with the version
date and affected endpoints. **If you are returning to a project built against an earlier
version of this skill, or anything here looks stale, read the changelog first** - it is
the fastest way to see what moved. This skill deliberately keeps no per-version change
list: the live changelog is the single source of truth for what changed when.

## Constructing queries

### Filter grammar

All list and aggregate endpoints take a `filter` query parameter:

```text
filter=key[op]:value                                          # single
filter=and(key1[op]:val1,key2[op]:val2)                       # AND (comma-separated args)
filter=or(key1[op]:val1,key2[op]:val2)                        # OR
filter=and(tag_id[eq]:42,or(location[eq]:1234,location[eq]:5678))   # nested
```

Operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, and the multi-value `in_any` / `in_all`
/ `nin_any` / `nin_all` (pipe-separated, e.g. `tag_id[in_any]:1|2|3`). `in_all` / `nin_all`
apply only to junction filters (tags, growth stages). Booleans are strings (`true` /
`false`). Relationship-path filters reach related entities with `.` (one hop) and `__`
(two hops), e.g. `founder.gender[eq]:female`, `funding_round__investor.total_invested[gt]:1000000`.

Entity classification (the legacy `is_company` flags were removed): `type` is
`organization` or `person`; `organization_subtype` is `company`, `investor`, `university`,
or `gov_ngo`; role flags `is_investor` / `is_founder` / `is_executive` / `is_partner` stack
on top. So "companies" is `organization_subtype[eq]:company`, "investment firms" is
`organization_subtype[eq]:investor`, "people" is `type[eq]:person`. (The investor-firm
subtype was renamed from `fund` to `investor`; `fund` now refers only to the investment
vehicle and is no longer a valid `organization_subtype` value.)

The exact key list, operators, and value types per scope are not memorized here. Discover
them live (next section) or read the
[Filters & Sorting reference](https://developers.beta.dealroom.co/references/filters-and-sorting).

### Discover filters and resolve IDs (do not guess)

There are two ID families - never mix them up:

- **Taxonomy IDs are numeric** (locations, industries, tags, degrees, backgrounds), not
  strings: `location[eq]:United+States` returns nothing; `location[eq]:233` works.
- **Entity IDs are UUIDs** - every path `{id}` param and every entity-reference filter
  (`entity_id`, `investor_id`, `company_investor_id`, `portfolio_company_id`, and
  relationship `.id` paths like `founder__university.id`). An integer where a UUID is
  expected fails validation or matches nothing.

Discover and resolve at runtime:

```bash
GET /api/reference/filters?scope=companies              # valid filter keys, operators, types, data status
GET /api/reference/filters/location/values?q=netherlands   # resolve a location to its ID
GET /api/reference/filters/tag_id/values?q=climate         # resolve a tag across ALL taxonomy types
GET /api/reference/filters/search?q=climate&scope=companies  # one-shot value search across every filter key
```

Valid scopes: `companies`, `investors`, `transactions`, `people`, `universities`, `news`,
`jobs`. Cache resolved IDs in your app; taxonomy changes rarely.

**Build filters from `filter_key`, not the displayed `key`.** `/api/reference/filters` returns tag
entries whose `key` is category-qualified (`tag_id:sector`, `tag_id:industry`,
`tag_id:technology`, ...) but whose `filter_key` is the bare `tag_id`. The filter grammar
only accepts the bare form: `tag_id[eq]:2181301` works; `tag_id:sector[eq]:2181301` throws
`FILTER_PARSE_ERROR` ("Expected LBRACKET but got COLON"). Always construct filter
expressions from each entry's `filter_key`.

**Resolve tags without forcing a `type`.** A tag's category is not always what you expect -
"Climate Tech" is a `sector`, not an `industry`, so `…/values?q=climate&type=industry`
returns `[]`. Omit `type` to search every taxonomy at once; each result is labelled with its
own `type`. Only pass `type` to disambiguate. Note: do not trust `entity_count` from these
value lookups (it can read `0` even for tags that match hundreds of entities on beta) -
confirm real counts with the list call's `page.total`.

### Pagination, sorting, currency

- **Pagination:** offset-based (`limit` / `offset`). Some list responses also return
  `page.next_cursor` for keyset pagination; round-trip it opaquely. `include_total=false`
  skips the count for faster lists.
- **Pagination depth is capped for non-M2M callers.** `offset + limit` above the caller's tier
  ceiling (anonymous 750 / free 5,000 / premium 50,000, raisable per ecosystem) is a `400`
  `PAGINATION_DEPTH_EXCEEDED` on both the offset and cursor paths - an error, not a silent
  clamp. M2M keys are exempt. Page size, by contrast, clamps silently for non-M2M callers and
  reports it via `page.capped`.
- **Sorting:** `sort=-total_funding,name` (prefix `-` for descending, comma-separated).
- **Currency:** `?currency=<ISO 4217>` converts thresholds and amounts (default USD). Field
  names stay base names (no `_usd` suffix); every response has a top-level `currency`.

Limit maximums, sort columns, and response field lists vary by endpoint and are documented
in the OpenAPI spec, not here.

## Live references

These are the single source of truth. Fetch the slice you need (`WebFetch` or `curl`); do
not paste whole pages or the full spec into context.

| Need                                          | Where                                                                  |
| --------------------------------------------- | ---------------------------------------------------------------------- |
| Enumerate namespaces / resources at runtime   | `GET /api` lists the five namespaces; each namespace index (`GET /api/data`, `GET /api/analytics`, ...) lists its resources |
| Exact request/response shape for any endpoint | `https://api-next.beta.dealroom.co/openapi` (then `jq '.paths | keys'`, then `jq '.paths["/api/<path>"]'`) |
| Swagger UI                                    | `https://api-next.beta.dealroom.co/docs`                               |
| Guides + concepts (filtering, aggregates, pagination, rate limits) | `https://developers.beta.dealroom.co` |
| Full filter + sorting catalog                 | `https://developers.beta.dealroom.co/references/filters-and-sorting` |
| Known limitations (stub / no-data endpoints + filters) | `https://developers.beta.dealroom.co/concepts/known-limitations` |
| Changelog (breaking changes, deprecations, new features per version) | `https://developers.beta.dealroom.co/changelog` |

Some advertised endpoints and filters are stubbed or not fully data-loaded yet, and the
set changes over time. Check the known-limitations page, the `x-data-status` extension in
the OpenAPI spec, or the `data_status` field from
`GET /api/reference/filters?scope=<scope>` before relying on a surface in production.

## Common errors

| Symptom                                       | Cause and fix                                                              |
| --------------------------------------------- | -------------------------------------------------------------------------- |
| `401 Unauthorized`                            | Token expired (24h). The snippet auto-refreshes.                           |
| `401` that persists after one refresh         | The key was deactivated or deleted. Re-minting will not help; ask the user to check <https://app-next.beta.dealroom.co/settings/api>. |
| `400` mentioning `X-Client-Id`                | The required client-id header is missing or does not match the token.        |
| `400` / `UNKNOWN_FILTER`                      | Filter key wrong for this scope. Call `GET /api/reference/filters?scope=<scope>`. |
| `400` / `PAGINATION_DEPTH_EXCEEDED`           | `offset + limit` past the tier depth cap (non-M2M only). Narrow the filter and partition the query instead of paging deeper. |
| `200` with nulled fields and a `locked[]`     | The call was treated as anonymous or free. Your credentials did not apply - fix the headers. |
| Empty `data: []` from a sane-looking filter   | The value did not resolve to a real ID. Look it up via `/api/reference/filters/{key}/values`. |
| `429 Too Many Requests`                       | Rate limit. Back off, honor `Retry-After`, cache taxonomy lookups.         |
| `504`                                         | 15s query timeout. Narrow the filter or set `include_total=false`.         |

## Early access: data caveat

This skill targets `api-next.beta.dealroom.co`, where data may be refreshed or partially
loaded. If a single result looks off, say so honestly rather than inventing an explanation,
and sanity-check the same query in the production Dealroom UI before debugging further.

## When the API disagrees with this skill

This is an early-access API: endpoints, filter keys, fields, response shapes, and auth
details can change without notice. **The live API and its docs are authoritative; this
skill is not.** When reality and this skill conflict, trust the API and surface the gap.

Treat these as drift signals (not normal data issues):

- A path documented here returns `404` / `405`, or a method that worked is rejected.
- A filter key this skill names returns `UNKNOWN_FILTER` on a scope where it should work.
- The response envelope differs from what is described (e.g. `page` renamed, fields
  missing or restructured, `data` shape changed).
- Valid credentials no longer authenticate (header names, audience, or token flow changed).
- `GET /api/reference/filters?scope=<scope>` or `/openapi` advertise endpoints/filters this skill
  does not mention, or omit ones it does.

When you hit one:

1. **Do not paper over it** with hardcoded values, guessed keys, or silent workarounds.
2. **Confirm against the source of truth:** `GET /api/reference/filters?scope=<scope>` for filters,
   `/openapi` for paths and shapes. A one-off `400`/`5xx` or empty result is usually data,
   not drift; a structural mismatch is reproducible.
3. **If the live state genuinely diverges from this skill, stop and tell the user
   plainly**, for example: "The Dealroom API now behaves differently from what the
   `dealroom-early-access-api` skill describes (`<what changed>`). I verified this against
   `/api/reference/filters` and `/openapi`. The skill looks out of date." Then proceed using the live
   behavior, and recommend the user update the skill (or open a PR to
   `dealroom-ai/agent-skills`) so it stays accurate.
