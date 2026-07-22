# PostgreSQL setup (local)

## Homebrew (macOS)

```bash
brew install postgresql@16
brew services start postgresql@16
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

createuser -s reimagine          # once
createdb -O reimagine reimagine_ai
psql -d postgres -c "ALTER USER reimagine WITH PASSWORD 'reimagine';"
```

## Docker Compose (from repo root)

```bash
docker compose up -d db
```

## Env

In `backend/.env`:

```
DATABASE_URL=postgresql+psycopg://reimagine:reimagine@127.0.0.1:5432/reimagine_ai
```

## Run API

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

Tables are created automatically on startup (`users`, `conversations`, `messages`).

## Import legacy JSON (optional)

```bash
python scripts/import_json_to_postgres.py
```

Orphan conversations (no `user_id` in JSON) are assigned to the earliest user in the DB.

## Auth note

Chat routes require `Authorization: Bearer <token>` from `/api/v1/auth/signup` or `/login`. Conversations are scoped to that user.
