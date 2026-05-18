---
name: next-gen-api-hackathon
description: Use this skill whenever the user is building against the Dealroom next-gen API — querying companies, startups, investors, founders, funding rounds, or any Dealroom data. Triggers on phrases like "Dealroom hackathon", "I have a Dealroom API key", "fetch startups", "query the Dealroom API", "build a dashboard with VC data", or any project that calls `api-next.beta.dealroom.co`. Walks the user through key generation, configures local credentials, handles the OAuth2 client-credentials flow + 24h token refresh, and routes the agent to the right docs (OpenAPI for endpoint shape, Mintlify for prose). If the user mentions any of: investors, fundings, startup ecosystems, scouting, VC data, unicorns, valuations, or the Dealroom platform, check whether this skill applies before doing anything else.
---

# Dealroom next-gen API — hackathon companion

Goal: get a hackathon participant from "I have nothing" to "I'm making authenticated API calls" in a few minutes, then keep the agent on rails so they don't waste hours guessing endpoint shapes.

## Read this before building anything

**Do not guess endpoint paths, filter keys, or operator syntax.** Hallucinated filter names that "look right" are the #1 reason hackathon participants get stuck — empty results, 400s, and no idea why. The docs are short and live; read them before constructing a request you haven't already made in this session.

Default workflow for any new query:

1. Check the **filter syntax** and **common queries** sections below — they cover ~80% of hackathon use cases.
2. If you need something else, **fetch the relevant Mintlify page** (links in [Reference URLs](#reference-urls)) — these pages are written for both humans and agents, ~50–150 lines each.
3. For exact request/response shapes, **fetch the OpenAPI spec**: `https://api-next.beta.dealroom.co/openapi`. Pipe through `jq '.paths | keys'` to find the endpoint, then `jq '.paths["/api/<path>"]'` for the schema.

Send the human to `https://developers.beta.dealroom.co/mintlify` if they ask "where are the docs". Don't paste OpenAPI JSON at them.

## Setup checklist

Run through these on the first turn. Skip steps already done.

### 1. Have the participant generate an API key

You can't do this for them — Auth0 needs a logged-in browser. Tell them:

> Open <https://app-next.beta.dealroom.co/settings/api>, click **+ Create key**, choose **Programmatic (M2M)**, name it `hackathon-key-{your_name}-2026`, copy both `client_id` and `client_secret`. The secret is shown only once. Make sure they save it (a `.env` in their project folder is fine).

Each participant gets their own `client_id` and `client_secret` — `client_id` is visible to others, secret is hidden.

### 2. Run the setup script

```bash
bash <skill-path>/scripts/setup.sh
```

It prompts for `client_id`, `client_secret`, and an email, derives the `User-Agent` from the current directory name + email, writes everything to `.env`, fetches an access token, and makes a test call to confirm everything works.

If they prefer manual setup, copy `assets/.env.example` to `.env` and fill in the three values.

### 3. Add `.env` to `.gitignore`

Check it's there. If not, add it. Secrets in git is the #1 way hackathon projects leak credentials.

### 4. Copy a starter snippet into the project

This is **the default path for everything after the first sanity-check curl** — do it now, not later. See [Use the snippet, not curl](#use-the-snippet-not-curl) for why.

```bash
cp <skill-path>/assets/snippets/dealroom.py ./   # Python projects
cp <skill-path>/assets/snippets/dealroom.ts ./   # Node/TS projects
```

Both read credentials from `.env`, handle 401-driven token refresh transparently, and don't have the bash-quoting problems of curl.

Quick smoke test:

```bash
# Python
python -c "from dealroom import client; print(client.get('/entities', params={'limit': 1}).json())"

# Node/TS
deno run --allow-env --allow-net --allow-read dealroom.ts   # or tsx, ts-node, etc.
```

## Use the snippet, not curl

curl is fine for the **first one or two calls** to confirm auth works. After that, switch to the snippet. Why this matters:

- **Bash quoting around filter expressions is fragile.** `[`, `]`, and `|` are shell metacharacters. Agents that try to keep curl-ing end up writing throwaway `tmp.sh` scripts to escape them — debris that pollutes the participant's project.
- **The snippet handles 401 automatically.** No "did the token expire?" guessing — it retries with a fresh token.
- **It reads `.env` once.** No re-sourcing between commands.

If you catch yourself about to write a temp wrapper script for curl, stop and use the snippet instead.

### Bash quoting cheat-sheet (for when you do use curl)

Always **single-quote or double-quote the whole URL** when filters are involved:

```bash
# BROKEN — bash interprets [, ], | as metacharacters
curl $DEALROOM_API_BASE/api/entities?filter=tag_id[in_any]:42|99   # NO

# WORKS — quote the URL
curl "$DEALROOM_API_BASE/api/entities?filter=tag_id[in_any]:42|99" \
  -H "Authorization: Bearer $DEALROOM_ACCESS_TOKEN" \
  -H "User-Agent: $DEALROOM_USER_AGENT" \
  -H "X-Client-Id: $DEALROOM_CLIENT_ID"
```

Don't URL-encode `[`/`]`/`|` manually — the API expects them literal. Quoting in bash is enough.

### Token refresh

Tokens last 24h (`expires_in: 86400`). The snippets refresh automatically on 401. If working in bash, run `scripts/refresh-token.sh` on a 401, re-source `.env`, retry once. Don't refresh pre-emptively on every call.

## Filter syntax

Filters use a single `filter` query parameter. The expression is its own little language.

### Operators

| Operator  | Meaning                                              |
| --------- | ---------------------------------------------------- |
| `eq`      | Exact match                                          |
| `neq`     | Not equal                                            |
| `gt`      | Greater than                                         |
| `gte`     | Greater than or equal                                |
| `lt`      | Less than                                            |
| `lte`     | Less than or equal                                   |
| `in_any`  | Matches any value in the pipe-separated list         |
| `nin_any` | Matches none of the values                           |
| `in_all`  | Matches all values (relation filters only)           |
| `nin_all` | Excludes all values (relation filters only)          |

### Composition

| Form        | Syntax                          | Example                                                                        |
| ----------- | ------------------------------- | ------------------------------------------------------------------------------ |
| Single      | `field[op]:value`               | `total_funding[gte]:1000000`                                                   |
| AND         | `and(expr,expr,...)`            | `and(total_funding[gte]:1000000,location[eq]:233)`                             |
| OR          | `or(expr,expr,...)`             | `or(location[eq]:118871,location[eq]:1297711)`                                 |
| Multi-value | `field[in_any]:v1\|v2\|v3`      | `tag_id[in_any]:42\|99\|202`                                                   |
| Cross-ref   | `relation__field[op]:value`     | `investor__total_invested[gte]:100000000`                                      |

Pipe `|` separates multi-values; **comma** separates AND/OR arguments. Don't mix them up.

### Taxonomy IDs — the most common trap

Locations, industries, and tags are **numeric IDs**, not strings. `location[eq]:United+States` returns nothing; `location[eq]:233` works. Look up the ID once, then filter:

```python
# Resolve: "what's the ID for Netherlands?"
client.get("/filters/location/values", params={"q": "netherlands"}).json()
# → { "data": [{ "id": 165, "name": "Netherlands", ... }] }

# Then filter
client.get("/entities", params={"filter": "location[eq]:165", "limit": 10})
```

Industries live under `tag_id` with `type=industry`:

```python
client.get("/filters/tag_id/values", params={"q": "fintech", "type": "industry"}).json()
```

**Cache the result in the participant's app.** Taxonomy changes rarely; re-resolving "United States" on every page load wastes rate-limit headroom.

### Discovering valid filters per resource

```bash
GET /api/filters?scope=companies
```

Valid scopes: `companies`, `investors`, `founders`, `transactions`, `valuations`. The response lists every accepted filter key, its supported operators, and value type. **Use this when you're not sure if a filter exists** — beats guessing.

## Common queries

Adapt these by swapping filter values and sorts.

```bash
# Top 20 startups by funding in the US (233 = US location ID)
GET /api/entities?sort=-total_funding&limit=20&filter=location[eq]:233

# Recently funded AI startups (tag_id 202 = Artificial Intelligence)
GET /api/entities?sort=-last_funding_date&limit=10&filter=tag_id[in_any]:202

# US AI startups with >$10M funding (AND composition)
GET /api/entities?filter=and(location[eq]:233,tag_id[in_any]:202,total_funding[gte]:10000000)&sort=-total_funding&limit=20

# Deal counts by country in 2024 (aggregate)
GET /api/aggregate/funding-rounds?metric=count&group_by=hq_country&filter=year[eq]:2024&sort=-count&limit=10

# All funding rounds for a specific company (entity_id from /api/entities)
GET /api/transactions?filter=entity_id[eq]:3009626&sort=-announced_date
```

## Reference URLs

Fetch these (with `WebFetch` or `curl`) when the inline cheat-sheet doesn't cover what you need.

| Need                                                | Fetch                                                                  |
| --------------------------------------------------- | ---------------------------------------------------------------------- |
| Filter operators, AND/OR, cross-ref syntax          | `https://developers.beta.dealroom.co/mintlify/concepts/filtering`      |
| Aggregate endpoints (counts, sums, percentiles)     | `https://developers.beta.dealroom.co/mintlify/concepts/aggregates`     |
| Pagination, sorting, currency                       | `https://developers.beta.dealroom.co/mintlify/concepts/pagination`     |
| Rate limits and 429 handling                        | `https://developers.beta.dealroom.co/mintlify/concepts/rate-limits`    |
| Full request/response shapes for any endpoint       | `https://api-next.beta.dealroom.co/openapi`                            |

For the OpenAPI spec: `jq '.paths | keys'` to list endpoints, `jq '.paths["/api/<path>"]'` for one. Don't paste the whole spec into context — fetch the slice you need.

## Common errors

| Symptom                                          | Likely cause + fix                                                                                |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `401 Unauthorized`                               | Token expired (24h TTL). Snippet auto-refreshes; in bash run `scripts/refresh-token.sh`, retry.   |
| `400` with `User-Agent` or `X-Client-Id`         | Header missing — all three auth headers are mandatory on every request.                           |
| `400` with `Unknown filter` or similar           | Filter key wrong for this scope. Hit `GET /api/filters?scope=<scope>` to see what's valid.        |
| Empty `data: []` from a filter that looks right  | Filter value didn't resolve to a real taxonomy ID. Look it up via `/api/filters/<field>/values`.  |
| `429 Too Many Requests`                          | Cloudflare rate limit. Exponential backoff, honor `Retry-After`. Cache taxonomy lookups.          |
| Weird shell parsing errors                       | Forgot to quote the URL. See [Bash quoting cheat-sheet](#bash-quoting-cheat-sheet-for-when-you-do-use-curl). |

## Beta environment caveat

The hackathon runs against `api-next.beta.dealroom.co`. Data may be refreshed or partially loaded. If something looks off, say so honestly rather than fabricating an explanation. Check the same query in the production Dealroom UI as a sanity check before going down a debugging rabbit hole.
