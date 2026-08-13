# Task 2 report — FastAPI endpoint and configuration safety

## Evidence

- Focused: `python3 -m pytest -q services/recommendation-api/tests/test_live_http_api.py` — 5 passed.
- Full Python suite: `python3 -m pytest -q services/recommendation-api/tests` — 41 passed.
- Whitespace: `git diff --check` — clean.
- The focused tests inject stub services and use no real API key or network calls.

## Changed files

- `services/recommendation-api/app/main.py`
- `services/recommendation-api/app/kakao_client.py`
- `services/recommendation-api/tests/test_live_http_api.py`

## Endpoint contract

`POST /v1/live-recommendations` accepts `LiveRecommendationRequest` fields:
`origin_name`, `origin_latitude`, `origin_longitude`, `purpose`, and
`max_travel_time_minutes`. It returns `LiveRecommendationResponse` from the
Kakao-backed service. Invalid non-Korean origins receive FastAPI validation
status 422. A missing or blank `KAKAO_REST_API_KEY` produces only the safe
503 detail `Live recommendations are not configured.` Provider 429 maps to
429; provider 5xx maps to 503; provider-facing details are never returned.
The existing `/v1/recommendations` fixture endpoint is unchanged.

## Deferred smoke test

No `.env` exists in this worktree, so no smoke request was made here. Run the
single configured-key smoke request from the parent workspace, reporting only
status, provider, and result count; do not print the key.
