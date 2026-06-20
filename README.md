# ConciergeOS

ConciergeOS is a hotel concierge and reservation management system built with Python, FastAPI, and SQLite. It provides a web dashboard for reservation management, an LLM-powered guest search, a performance testing suite, and tools for generating test data including rooms, guests with multilingual names, and reservations with realistic date/status distributions.

> **Last documented state:** Commit `d489d91` (20/06/2026) — "performance tests for multiple guests"
> All changes up to and including this commit are documented below.

## Project Structure

```
ConciergeOS/
├── create_hotel_db.py                  # SQLite schema initialization
├── pyproject.toml                      # Project metadata & dependencies
├── app/                                # FastAPI web application
│   ├── __init__.py
│   ├── db.py                           # SQLAlchemy engine, session, Base model
│   ├── enums.py                        # BookingChannel, BookingSource, ReservationStatus enums
│   ├── main.py                         # FastAPI app, routes, templates
│   ├── models.py                       # SQLAlchemy ORM models (Room, Guest, Reservation)
│   ├── schemas.py                      # Pydantic request/response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── core.py                     # Reservation queries & error detection
│   │   ├── debug.py                    # Debug endpoints router
│   │   └── llm.py                      # LLM integration (vLLM/OpenAI client)
│   └── templates/
│       ├── guest_search.html           # Guest search page
│       ├── header.html                 # Shared header component
│       ├── performance_testing.html    # Performance testing dashboard
│       └── reservations.html           # Reservations dashboard
├── Generator/                          # Data generation & utility scripts
│   ├── generate_names.py               # Multilingual name generator
│   ├── generate_rooms.py               # Room data generator
│   ├── populate_rooms.py               # Inserts rooms into database
│   ├── populate_reservations.py        # Generates guests & reservations
│   ├── shift_reservations.py           # Shifts all reservation dates by N days
│   ├── setup_errors.py                 # Injects controlled errors into reservations
│   ├── setup_performance_guests.py     # Creates 13 test guests with 4 reservations each
│   ├── utils.py                        # Shared constants & DB connection helper
│   ├── all_names.json                  # Master name list (8 alphabets)
│   ├── *_names.txt                     # Per-alphabet name files
│   ├── rooms.json                      # Structured room data
│   ├── rooms.txt                       # Human-readable room list
│   └── erroneous_reservations.json     # Persisted error IDs from setup_errors.py
└── PerformanceTesting/                 # LLM performance testing suite
    ├── __init__.py
    ├── db.py                           # Performance test result database (SQLite)
    ├── run_performance_tests.py        # Sequential & concurrent batch test runner
    └── manual_performance_analysis.sql # SQL queries for manual analysis
```

## What It Does

ConciergeOS models a single-tenant hotel with three core entities:

### Rooms
Rooms are categorized by booking channel:
- **ANY** — Bookable through any channel (OTA, website, phone)
- **ON_SITE_ONLY** — Only bookable as walk-in reservations
- **STAFF_ASSIGNMENT** — Internal staff assignments (no guest bookings)

Each room has configurable check-in/check-out times. STAFF_ASSIGNMENT rooms use `00:00` for both times.

### Guests
Guest records support multilingual names across 8 writing systems:
- Latin (European languages)
- Cyrillic (Russian, Ukrainian, etc.)
- Chinese (Simplified)
- Japanese (Kanji/Kana)
- Arabic
- Devanagari (Hindi, Marathi, etc.)
- Korean (Hangul)
- Nordic (Scandinavian with special characters)

Each guest has a first name, last name, date of birth, and optional special preferences.

### Reservations
Reservations link guests to rooms with the following statuses:
- `PENDING` → `CONFIRMED` → `CHECKED_IN` → `CHECKED_OUT` (or `CANCELLED`)

The system supports 1-6 guests per reservation and tracks booking source based on room type:
- ON_SITE_ONLY → `WALK_IN`
- ANY → random of `WEBSITE`, `PHONE`, `OTA`
- STAFF_ASSIGNMENT → `INTERNAL`

## Web Application

### FastAPI Dashboard

The `app/` package is a FastAPI application that serves a web dashboard and JSON API:

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Reservations dashboard — rooms grouped by name with error detection |
| `/api/reservations` | GET | JSON endpoint returning the same reservations + errors payload |
| `/guest-search` | GET | Guest search page |
| `/api/guest-search` | POST | LLM-powered guest lookup (natural language query) |
| `/performance-testing` | GET | Performance testing dashboard |
| `/api/performance-testing` | POST | Run performance tests with configurable settings |
| `/api/performance-testing/results` | GET | Latest 100 test results |
| `/api/performance-testing/all-results` | GET | All test results (no limit) |
| `/api/performance-testing/batches` | GET | All unique test batches |
| `/api/performance-testing/results-by-batch` | GET | Results filtered by batch UUID |
| `/api/performance-testing/result/{id}` | PATCH | Update `valid_response` flag for a result |
| `/api/performance-testing/setup-guests` | POST | Setup 13 performance test guests |
| `/api/performance-testing/test-guests` | GET | List performance test guests |

### Architecture

- **`app/db.py`** — SQLAlchemy engine and session factory connected to `hotel.db`. Provides `SessionLocal` and `get_db` FastAPI dependency.
- **`app/models.py`** — ORM models (`Room`, `Guest`, `Reservation`) mapped to the existing SQLite tables. Uses the enums from `app/enums.py`.
- **`app/schemas.py`** — Pydantic schemas for request/response validation (`GuestSearchRequest`, `GuestSearchResponse`, `ReservationResponse`, `ErrorResponse`, `ReservationsSummary`).
- **`app/enums.py`** — Python enums for `BookingChannel`, `BookingSource`, and `ReservationStatus`.
- **`app/services/core.py`** — Business logic: fetches reservations grouped by room, loads error IDs from `erroneous_reservations.json`, and detects status/date errors.
- **`app/services/llm.py`** — OpenAI-compatible client connecting to a local vLLM instance. Fetches all guest/reservation data from the database, builds a prompt, and returns the LLM response.

### LLM Integration

The guest search feature uses a local **vLLM** instance (default: `http://10.0.0.227:8000/v1`) running the model `Qwen/Qwen3.6-27B`. When a user searches for a guest by name, the service:

1. Queries the database for all guests, rooms, and reservations.
2. Serializes the data into a compact JSON string.
3. Sends the data as context to the LLM along with a system prompt and the customer name query.
4. Returns the LLM's natural-language response to the user.

## Performance Testing

The `PerformanceTesting/` package provides a suite for benchmarking LLM query performance:

### Features
- **Sequential batch mode** — Runs N requests one after another.
- **Concurrent batch mode** — Runs N requests in parallel using `ThreadPoolExecutor`.
- **Multi-guest mode** — Uses different guest names per request (from the 13 performance test guests) to avoid caching effects.
- **Single-guest mode** — Uses the same guest name for all requests in a batch.
- **Results persistence** — All results stored in `performance_tests.db` with full metadata (model name, vLLM version, thinking enabled, prompt, response, timestamps).
- **Batch tracking** — Each test run is assigned a UUID and optional friendly name for grouping and comparison.

### Test Settings (`TestSettings`)
| Parameter | Default | Description |
|-----------|---------|-------------|
| `customer_name` | "عائشة إبراهيم" | Default guest name (single mode) |
| `vllm_url` | `http://10.0.0.227:8000/v1` | vLLM endpoint |
| `models_endpoint` | `http://10.0.0.227:8000/v1/models` | Model info endpoint |
| `database_path` | `performance_tests.db` | Results database |
| `sequential_batch_size` | 5 | Number of sequential requests |
| `concurrent_batch_size` | 8 | Number of concurrent requests |
| `test_mode` | `"single"` | `"single"` or `"multi"` |
| `guest_names` | `[]` | Guest names for multi mode |
| `batch_uuid` | auto-generated | Unique batch identifier |
| `model_name` | from API | Model identifier |
| `thinking_enabled` | `False` | Whether vLLM thinking mode is on |
| `system_prompt` | default | Custom system prompt |
| `user_prompt` | auto-built | Custom user prompt |
| `expected_response_format` | `"auto"` | `"json"`, `"text"`, or `"auto"` |

### Performance Test Guest Setup

The script `Generator/setup_performance_guests.py` creates a controlled set of test data for performance testing:

- **13 guests** with Arabic names from the existing name list.
- **4 reservations per guest** (52 total), distributed across four date buckets:
  1. CHECKED_IN (checking out today)
  2. CHECKED_IN (future checkout)
  3. CHECKED_OUT
  4. CONFIRMED
- Guests are tagged with `special_preferences = "performance_test"` for easy filtering.
- Ensures each guest has the same reservation count for consistent LLM output.

## Quick Start

### Prerequisites
- Python 3.12+
- SQLite 3 (built into Python standard library)
- Dependencies (installed via `pip` or `uv`):
  - `fastapi` — Web framework
  - `jinja2` — Template engine
  - `openai` — OpenAI-compatible client (for vLLM)
  - `pydantic` — Data validation
  - `requests` — HTTP client
  - `sqlalchemy` — ORM
  - `uvicorn` — ASGI server

Install with:
```bash
pip install -e .
# or
uv pip install -e .
```

### Setup

Follow these steps in order to initialize the database and generate test data:

#### 1. Initialize the Database
```bash
python create_hotel_db.py [--recreate]
```
Creates `hotel.db` with the `Rooms`, `Guests`, and `Reservations` tables, including indexes for efficient date-range and guest lookups. Use `--recreate` to delete the existing database and start fresh.

#### 2. Generate Name Data
```bash
python Generator/generate_names.py
```
Generates ~50 names per alphabet (400 total) and saves them to individual `.txt` files and a consolidated `all_names.json`.

#### 3. Generate and Populate Rooms
```bash
python Generator/generate_rooms.py    # Creates rooms.json and rooms.txt
python Generator/populate_rooms.py    # Inserts rooms into the database
```
Generates ~205 rooms across three building wings (East, North, West), each mapped to a booking channel.

#### 4. Populate Guests and Reservations
```bash
python Generator/populate_reservations.py
```
Creates realistic reservation data with:
- **Weighted status distribution**: More CHECKED_IN than CHECKED_OUT or CONFIRMED
- **Name collisions**: Intentional duplicate guest names across multiple rooms (for testing deduplication logic)
- **STAFF_ASSIGNMENT handling**: All staff rooms are always CHECKED_IN with past check-in and future check-out dates
- **Booking source enforcement**: Sources are determined by room booking channel

#### 5. (Optional) Setup Performance Test Guests
```bash
python Generator/setup_performance_guests.py
```
Creates 13 dedicated test guests with 4 reservations each for the performance testing suite.

### Running the Web Application

Start the FastAPI development server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Then open `http://localhost:8000` in your browser.

### Utility Scripts

#### Shift Reservation Dates
```bash
python Generator/shift_reservations.py              # Shift by 1 day (default)
python Generator/shift_reservations.py --days 3     # Shift forward by 3 days
python Generator/shift_reservations.py --days -2    # Shift backward by 2 days
```
Shifts all `check_in_date` and `check_out_date` values in the `Reservations` table by the specified number of days. Positive values shift forward, negative values shift backward. A sample of dates before and after the shift is printed to stdout.

#### Inject Controlled Errors (for testing)
```bash
python Generator/setup_errors.py
```
Finds reservations with name collisions (same guest name on 2+ different rooms) and introduces two types of controlled errors:

- **Error Type A — Erroneous Status** (2 reservations):
  1. A `CHECKED_IN` reservation → status changed to `CANCELLED`
  2. A `CONFIRMED` reservation → status changed to `CHECKED_OUT`

- **Error Type B — Unsynchronized Dates** (2 reservations):
  3. A `CHECKED_IN` reservation → `check_out_date` moved to the past
  4. A `CHECKED_OUT` reservation → `check_in_date` moved to the future

The affected reservation IDs are persisted to `Generator/erroneous_reservations.json` for repeatable testing. Excluded IDs can be configured in the `EXCLUDED_RESERVATION_IDS` list at the top of the script.

### Shared Utilities (`Generator/utils.py`)

All Generator scripts share a common utility module that provides:
- **`BASE_DIR`** — Path to the `Generator/` directory
- **`PROJECT_ROOT`** — Path to the project root (`ConciergeOS/`)
- **`DB_NAME`** — Database filename (`hotel.db`)
- **`DB_PATH`** — Full path to the database file
- **`init_connection()`** — Creates a SQLite connection with foreign keys enforced and WAL journal mode enabled

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.