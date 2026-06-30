# Quick Start Guide

> Complete step-by-step instructions to get ConciergeOS running locally.

## Prerequisites

- Python 3.12+
- Node.js 18+
- SQLite 3 (included with Python)

## 1. Install Backend Dependencies

```bash
uv sync
```

## 2. Initialize the Database

```bash
cd backend
uv run alembic upgrade head
```

## 3. Populate the Database

```bash
# Generate multilingual name data
uv run python Generator/generate_names.py

# Create rooms
uv run python Generator/generate_rooms.py
uv run python Generator/populate_rooms.py

# Create guests and reservations
uv run python Generator/populate_reservations.py
```

## 4. Start the Application

Open two terminal windows:

```bash
# Terminal 1 — FastAPI Backend (port 8000)
cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Terminal 2 — React Frontend (port 5173)
cd frontend && npm run dev
```

Open **http://localhost:5173** in your browser.

## Optional: Performance Test Guests

```bash
cd backend
uv run python Generator/setup_performance_guests.py
```

## Optional: Inject Test Errors

```bash
cd backend
uv run python Generator/setup_errors.py