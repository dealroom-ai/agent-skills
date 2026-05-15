---
name: next-gen-api-hackathon
description: Use this skill whenever the user is building against the Dealroom next-gen API — querying companies, startups, investors, founders, funding rounds, or any Dealroom data. Triggers on phrases like "Dealroom hackathon", "I have a Dealroom API key", "fetch startups", "query the Dealroom API", "build a dashboard with VC data", or any project that calls `api-next.beta.dealroom.co`. Walks the user through key generation, configures local credentials, handles the OAuth2 client-credentials flow + 24h token refresh, and routes the agent to the right docs (OpenAPI for endpoint shape, Mintlify for prose). If the user mentions any of: investors, fundings, startup ecosystems, scouting, VC data, unicorns, valuations, or the Dealroom platform, check whether this skill applies before doing anything else.
---

# Dealroom next-gen API — hackathon companion

Goal: get a hackathon participant from "I have nothing" to "I'm making authenticated API calls" in a few minutes, then point the agent at the right docs for whatever comes next.

## Two audiences, two doc sources

Send the human to <https://developers.beta.dealroom.co/mintlify> for prose. For your own endpoint lookups, fetch <https://api-next.beta.dealroom.co/openapi>. Don't dump OpenAPI at the human.

## Setup checklist

Run through these on the first turn. Skip steps that are already done.

### 1. Have the participant generate an API key

You can't do this for them — Auth0 needs a logged-in browser. Tell them:

> Open <https://app-next.beta.dealroom.co/settings/api>, click **+ Create key**, choose **Programmatic (M2M)**, name it `hackathon-key-{your_name}-2026`, copy both `client_id` and `client_secret`. The secret is shown only once. Make sure to stress to the user to save this. Possibly in a .env in their project folder.

Each participant gets their own `client_id` and `client_secret` — client_id is visible to others, secret is hidden.

### 2. Run the setup script

```bash
bash <skill-path>/scripts/setup.sh
```

It prompts for `client_id`, `client_secret`, and an email, derives the `User-Agent` from the current directory name + email, writes everything to `.env`, fetches an access token, and makes a test call to confirm everything works.

If they prefer to do it themselves, copy `assets/.env.example` to `.env` and fill in the three values.

### 3. Add `.env` to `.gitignore`

Check it's there. If not, add it. Secrets in git is the #1 way hackathon projects leak credentials.

## Making requests

Once `.env` is set up, every call follows this shape:

```bash
source .env
curl "$DEALROOM_API_BASE/api/entities?limit=10&sort=-launch_date" \
  -H "Authorization: Bearer $DEALROOM_ACCESS_TOKEN" \
  -H "User-Agent: $DEALROOM_USER_AGENT" \
  -H "X-Client-Id: $DEALROOM_CLIENT_ID"
```

All three headers are mandatory. The API rejects requests missing `User-Agent` or `X-Client-Id` with a 400.

### Token refresh

Tokens last 24h (`expires_in: 86400`). On a 401, run `scripts/refresh-token.sh` — it requests a new token, rewrites `DEALROOM_ACCESS_TOKEN` in `.env`, and you re-source. Don't refresh pre-emptively on every call.

### Python or Node

For real apps (not one-off curls), copy a starter from `assets/snippets/`:

- `assets/snippets/dealroom.py` — `requests` + `authlib`, auto-refresh
- `assets/snippets/dealroom.ts` — `axios` + `simple-oauth2`, auto-refresh

Both read credentials from environment and handle refresh transparently.

## Common queries

Three patterns that cover most hackathon use cases. Adapt them with different filters/sorts.

```bash
# Top 20 startups by total funding in the US (233 = United States location ID)
curl "$DEALROOM_API_BASE/api/entities?sort=-total_funding&limit=20&filter=location[eq]:233" \
  -H "Authorization: Bearer $DEALROOM_ACCESS_TOKEN" \
  -H "User-Agent: $DEALROOM_USER_AGENT" \
  -H "X-Client-Id: $DEALROOM_CLIENT_ID"

# Recently funded AI startups (tag_id 202 = Artificial Intelligence)
curl "$DEALROOM_API_BASE/api/entities?sort=-last_funding_date&limit=10&filter=tag_id[in_any]:202" \
  -H "Authorization: Bearer $DEALROOM_ACCESS_TOKEN" \
  -H "User-Agent: $DEALROOM_USER_AGENT" \
  -H "X-Client-Id: $DEALROOM_CLIENT_ID"

# Deal counts by country in 2024
curl "$DEALROOM_API_BASE/api/aggregate/funding-rounds?metric=count&group_by=hq_country&filter=year[eq]:2024&sort=-count&limit=10" \
  -H "Authorization: Bearer $DEALROOM_ACCESS_TOKEN" \
  -H "User-Agent: $DEALROOM_USER_AGENT" \
  -H "X-Client-Id: $DEALROOM_CLIENT_ID"
```

Numeric IDs (locations, industries) need to be looked up via `/api/filters/<field>/values?q=<query>`. Cache the result in the participant's app — taxonomy changes rarely.

## Where to look up more

| Need                                                | Fetch                                                          |
| --------------------------------------------------- | -------------------------------------------------------------- |
| Filter operators, AND/OR, cross-ref syntax          | `https://developers.beta.dealroom.co/mintlify/concepts/filtering`   |
| Aggregate endpoints (counts, sums, percentiles)     | `https://developers.beta.dealroom.co/mintlify/concepts/aggregates`  |
| Pagination, sorting, currency                       | `https://developers.beta.dealroom.co/mintlify/concepts/pagination`  |
| Rate limits and 429 handling                        | `https://developers.beta.dealroom.co/mintlify/concepts/rate-limits` |
| Full request/response shapes for any endpoint       | `https://api-next.beta.dealroom.co/openapi`                    |

The OpenAPI spec is large — `jq '.paths | keys'` to list endpoints, `jq '.paths["/api/<path>"]'` for one.

## Common errors

| Symptom                                      | Fix                                                          |
| -------------------------------------------- | ------------------------------------------------------------ |
| `401 Unauthorized`                           | Token expired (24h TTL) — run `scripts/refresh-token.sh`, re-source `.env`, retry once |
| `400` with `User-Agent` or `X-Client-Id`     | Header missing — all three auth headers are mandatory        |
| `429 Too Many Requests`                      | Cloudflare rate limit — exponential backoff, honor `Retry-After` |
| Empty `data: []` from a filter that looks right | Filter value didn't resolve to a real taxonomy ID — look it up via `/api/filters/<field>/values` |

Always quote the URL in bash — `[`, `]`, and `|` are shell metacharacters.

## Beta environment caveat

The hackathon runs against `api-next.beta.dealroom.co`. Data may be refreshed or partially loaded. If something looks off, say so honestly rather than fabricating an explanation.
