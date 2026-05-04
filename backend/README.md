# FinSight AI Backend

FastAPI backend for FinSight AI. Handles user authentication using JWT and stores data in Supabase PostgreSQL.

---

## Project Structure

```
backend/
  app/
    main.py
    config.py
    database.py
    models/
      user.py
    schemas/
      auth.py
      user.py
    routes/
      auth.py
    services/
      auth_service.py
    core/
      security.py
      rate_limit.py
  sql/
    create_tables.sql
  .env
  .env.example
  requirements.txt
```

---

## Setup

### 1. Activate virtual environment

**Mac / Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Full Supabase PostgreSQL connection string |
| `JWT_SECRET_KEY` | Random secret string (at least 32 chars) |
| `JWT_ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime in minutes (e.g. `60`) |
| `APP_ENV` | `development` or `production` |

---

## Database Setup (Supabase)

1. Open your Supabase project dashboard.
2. Go to **SQL Editor**.
3. Open `sql/create_tables.sql`.
4. Paste the full contents and click **Run**.

This creates the `users` table and an `updated_at` trigger.

---

## Run the backend

```bash
uvicorn app.main:app --reload
```

The server starts at `http://127.0.0.1:8000`.

---

## Swagger Docs

Open in your browser:

```
http://127.0.0.1:8000/docs
```

---

## API Endpoints

### Health

```
GET /          → {"message": "FinSight AI backend is running"}
GET /health    → {"status": "healthy"}
```

### Auth

```
POST /auth/signup
POST /auth/login
GET  /auth/me
```

---

## Testing

### Sign up

```bash
curl -X POST http://127.0.0.1:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Rahul","last_name":"Patel","email":"rahul@example.com","password":"secret123"}'
```

### Log in

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"rahul@example.com","password":"secret123"}'
```

### Get current user (requires token)

```bash
curl http://127.0.0.1:8000/auth/me \
  -H "Authorization: Bearer <your_access_token>"
```

---

## Rate Limits

| Endpoint | Limit |
|---|---|
| `POST /auth/signup` | 3 requests / minute |
| `POST /auth/login` | 5 requests / minute |
| `GET /auth/me` | 30 requests / minute |

Exceeding a limit returns HTTP `429 Too Many Requests`.

---

## Android Integration

The Android app connects to this backend using Retrofit. The default base URL for the Android emulator is `http://10.0.2.2:8000/`, which maps to `localhost` on the host machine.
