# AskDB

Ask a database a question in plain language. AskDB turns it into one read-only SQL statement with Gemini, runs it, and shows the rows, summary stats, and a chart.

The stack is a React studio, a FastAPI API, and Postgres. Sign-in uses hashed passwords and JWT access and refresh tokens. Question traffic is rate limited so a shared free-tier Gemini key is harder to burn through.

A Harbor & Co. retail database is created on first startup: stores, employees, customers, products, and orders. You can also add your own Postgres connection or upload a SQLite file.

## Run it

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), then from this folder:

```bash
copy .env.example .env
```

Open `.env` and set `GEMINI_API_KEY`. A free key (no credit card) comes from [Google AI Studio](https://aistudio.google.com/apikey). The default model is `gemini-3.5-flash-lite`, which is on the Gemini API free tier. `gemini-3.8-flash` and `gemini-3.1-flash-lite` are other free-tier options if you want to change `GEMINI_MODEL`.

```bash
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080), create an account, and ask something like “What are the top 5 products by paid revenue?”

The API is also on [http://localhost:8000/api/docs](http://localhost:8000/api/docs).

`docker compose up` still starts if `.env` is missing. Auth, the demo database, and hand-written SQL work. Generated questions need the key. After you add it, run `docker compose up --build` again.

To wipe the demo data and local accounts:

```bash
docker compose down -v
```

## What you can do

- Register and sign in. Passwords are hashed with bcrypt. Sessions are a short-lived JWT plus a rotating refresh token.
- Ask a question. Gemini returns SQL, a short reason, a confidence score, and a chart suggestion.
- Generate AI Executive Insights on-demand (or automatically via toggle): headline takeaway, key findings, anomaly callouts, and clickable follow-up questions.
- The API keeps only a single `SELECT` or `WITH` statement, strips comments, blocks writes and file-read functions, and caps the result at 500 rows.
- Postgres connections run with a statement timeout and `default_transaction_read_only`. The demo login can only `SELECT`. SQLite uploads run with `PRAGMA query_only`.
- If the first query fails validation or the database, AskDB asks Gemini to repair it once.
- Browse the schema, including keys and a few sample rows. Click a column to drop it into the question.
- Switch the chart (bar, line, area, scatter, histogram, pie), sort the table, and export CSV or JSON.
- Re-open a past question from history, or run your own read-only SQL.
- Upload a SQLite file (20 MB max) or save a Postgres connection. Saved passwords are encrypted with a key derived from `JWT_SECRET`.

Login is limited to 8 attempts a minute per IP. Registration is 5 a minute. Generated questions are 8 a minute and 40 a day per account. Those values are `QUERY_RATE_LIMIT` and `QUERY_DAILY_LIMIT` in `.env`.

## Project layout

```
docker-compose.yml      web on :8080, api on :8000, Postgres
backend/                FastAPI app
backend/sql/init.sql    Harbor & Co. demo database and demo_reader role
frontend/               React + Vite studio, served by nginx
```

Nginx sends `/api` to the API container, so the browser only talks to port 8080.

## Demo questions

- What are the top 5 products by paid revenue?
- Show monthly paid revenue for 2026
- Which employees have the highest average order value?
- How many customers joined in each region?
- Which products have fewer than 20 units in stock?

Revenue is `order_items.quantity * order_items.unit_price`. Paid revenue filters `orders.status = 'paid'`.

## Connect your own Postgres

In the studio, choose **Add database**. From a container, a database on your computer is usually host `host.docker.internal`. The API checks the connection before saving it.

Avoid `@`, `:`, and `/` in `POSTGRES_PASSWORD`. Those characters break the URL that Compose builds.

The demo database password (`demo_reader` / `demo_reader_pass`) only exists on the Docker network. It is not an account on the AskDB app.

## Local checks

Backend unit tests cover the SQL guard, password hashing, rate limit, and Gemini JSON parsing. They do not need Postgres:

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pytest
.venv\Scripts\pytest
```

Frontend production build:

```bash
cd frontend
npm install
npm run build
```
