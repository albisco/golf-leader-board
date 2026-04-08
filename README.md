# Golf Leader Board

A real-time golf scoring application with live leaderboard updates.

## Tech Stack

- FastAPI
- WebSocket for real-time updates
- pytest + httpx for testing

## API Endpoints

- `POST /events` — Create event (holes auto-generated)
- `POST /events/{id}/start` — Start event (draft → active)
- `POST /events/{id}/close` — Close event (active → closed)
- `POST /scores` — Submit/upset score on a hole
- `GET /leaderboard/{event_id}` — Live leaderboard data
- `POST /chat` — Send chat message
- `POST /auth/magic-link` — Send magic link email
- `GET /auth/verify` — Verify magic link, set session
- `GET /score/{scorer_token}` — Scorer interface
- `WS /ws/{event_id}` — WebSocket for leaderboard + chat updates

## Key Features

- Score upsert (re-submitting updates existing score, increments edit_count)
- Mid-round leaderboard sorting (more holes completed = higher rank)
- Final leaderboard sorting (net total, then gross total as tiebreaker)
- Real-time WebSocket broadcast on score submission
- Closed events reject score submission (403)
- Magic links expire after 24 hours

## Testing

```bash
pytest
```

## Test Files

- `tests/test_events.py` — Event CRUD and lifecycle
- `tests/test_scores.py` — Score submission and validation
- `tests/test_leaderboard.py` — Sort logic
- `tests/test_auth.py` — Authentication
- `tests/test_ws.py` — WebSocket
- `tests/test_e2e.py` — End-to-end flows