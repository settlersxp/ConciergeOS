# Backend Development Guide

> Development commands and scripts for the ConciergeOS backend.

## Running the Server

```bash
# Development mode with auto-reload
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Production mode
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Database Migrations

```bash
# Create a new migration after model changes
uv run alembic revision --autogenerate -m "description"

# Apply all pending migrations
uv run alembic upgrade head

# Revert last migration
uv run alembic downgrade -1

# Show current migration version
uv run alembic current

# Show migration history
uv run alembic history
```

### Migration Workflow

1. Modify models in `app/models.py`
2. Generate migration: `uv run alembic revision --autogenerate -m "description"`
3. Review the generated migration file in `alembic/versions/`
4. Apply: `uv run alembic upgrade head`

## Data Generation Scripts

### Wrapper Scripts

| Category | Wrapper | Command | Description |
|----------|---------|---------|-------------|
| Generation | `run_generation.py` | `python Generator/run_generation.py` | Generates raw data files (names, rooms) |
| Population | `run_population.py` | `python Generator/run_population.py` | Inserts rooms, guests, reservations into DB |
| Error Setup | `run_errors.py` | `python Generator/run_errors.py` | Injects controlled errors for testing |

**Full setup sequence:**
```bash
# 1. Generate data files
python Generator/run_generation.py

# 2. Populate database
python Generator/run_population.py

# 3. (Optional) Inject test errors
python Generator/run_errors.py
```

### Standalone Scripts

| Script | Command | Description |
|--------|---------|-------------|
| Generate names | `python Generator/generate_names.py` | ~400 multilingual names across 8 scripts |
| Generate rooms | `python Generator/generate_rooms.py` | ~205 room definitions |
| Populate rooms | `python Generator/populate_rooms.py` | Insert rooms into database |
| Populate reservations | `python Generator/populate_reservations.py` | Create guests & reservations |
| Setup performance guests | `python Generator/setup_performance_guests.py` | Create 13 test guests |
| Setup errors | `python Generator/setup_errors.py` | Inject controlled errors |
| Seed prompts | `python Generator/seed_prompts.py` | Create PromptVersions table |
| Shift reservations | `python Generator/shift_reservations.py --days N` | Shift all dates by N days |

## Testing

```bash
# Run backend tests (when test suite is configured)
uv run pytest

# Run performance tests
python PerformanceTesting/run_performance_tests.py
```

## API Development

```bash
# API documentation (auto-generated)
# Open http://localhost:8000/docs for Swagger UI
# Open http://localhost:8000/redoc for ReDoc
```

## Project Structure

```
backend/
├── app/                        # FastAPI application
│   ├── main.py                 # Application entry point
│   ├── models.py               # SQLAlchemy ORM models
│   ├── schemas.py              # Pydantic schemas
│   ├── db.py                   # Database session setup
│   ├── config.py               # Configuration management
│   ├── enums.py                # Shared enumerations
│   ├── config.json             # Persistent config (auto-generated)
│   ├── routes/                 # API route modules
│   │   ├── reservations.py
│   │   ├── guest_search.py
│   │   ├── performance_testing.py
│   │   ├── settings.py
│   │   ├── prompts.py
│   │   └── prompt_groups.py
│   └── services/               # Business logic
│       ├── core.py
│       ├── llm.py
│       ├── tool_calling.py
│       └── ...
├── Generator/                  # Data generation scripts
├── PerformanceTesting/         # LLM benchmarking suite
├── alembic/                    # Database migrations
├── data/                       # Exported data files
└── database.db                 # SQLite database