# Task 2 report — FastAPI endpoint and configuration safety

## Evidence

- Focused: `python3 -m pytest -q services/recommendation-api/tests/test_live_http_api.py` — 6 passed.
- Full Python suite: `python3 -m pytest -q services/recommendation-api/tests` — 42 passed.
- Whitespace: `git diff --check` — clean.
- Focused tests inject stub services for successful and provider-failure paths;
  the foreign-origin regression runs the real configuration path with only a
  missing or whitespace environment value. No test uses a real key or network.

## Changed files

- `services/recommendation-api/app/main.py`
- `services/recommendation-api/app/kakao_client.py`
- `services/recommendation-api/tests/test_live_http_api.py`

## Endpoint contract

`POST /v1/live-recommendations` accepts `LiveRecommendationRequest` fields:
`origin_name`, `origin_latitude`, `origin_longitude`, `purpose`, and
`max_travel_time_minutes`. It returns `LiveRecommendationResponse` from the
Kakao-backed service. Request validation, including non-Korean origin
rejection, runs before the configured service is opened, so invalid origins
receive FastAPI status 422 even when `KAKAO_REST_API_KEY` is missing or blank.
A missing or blank key for an otherwise valid request produces only the safe
503 detail `Live recommendations are not configured.` Provider 429 maps to
429; provider 5xx maps to 503; provider-facing details are never returned.
The existing `/v1/recommendations` fixture endpoint is unchanged.

## Deferred smoke test

No `.env` exists in this worktree, so no smoke request was made here. Run the
single configured-key smoke request from the parent workspace, reporting only
status, provider, and result count; do not print the key.
