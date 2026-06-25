# ConciergeOS

ConciergeOS is a hotel concierge and reservation management system built with Python, FastAPI, SQLite (backend) and React with TypeScript (frontend). It provides a web dashboard for reservation management, an LLM-powered guest search with tool calling support, a performance testing suite, and tools for generating and exporting test data.

## Architecture

The project consists of two independent applications:

| Component | Technology | Port | Description |
|-----------|------------|------|-------------|
| **Frontend** | React + TypeScript + Vite | 5173 | Single-page application with client-side routing |
| **Backend** | FastAPI + SQLite | 8000 | REST API only (no server-rendered pages) |

Both applications run independently and communicate via HTTP JSON API calls. The frontend is configured to proxy API requests to the backend.

## Core Features

### Reservation Management
A web dashboard displaying all reservations grouped by room, with automatic error detection for:
- **Erroneous statuses** — Reservations with incorrect status (e.g., `CANCELLED` instead of `CHECKED_IN`)
- **Unsynchronized dates** — Check-in dates in the future for checked-out guests, or check-out dates in the past for checked-in guests

Rooms are categorized by booking channel (`ANY`, `ON_SITE_ONLY`, `STAFF_ASSIGNMENT`), which determines allowed booking sources.

### Guest Search
LLM-powered natural language search for guest information. Type a guest name (in any supported language) and receive a structured response with personal details, rooms, and all reservations.

The system supports two LLM interaction modes:
- **Tool Calling** — The LLM invokes read-only database query tools (`query_guests`, `query_rooms`, `query_reservations`, `get_hotel_summary`) to fetch data on demand. This is the default mode and scales better with large datasets.
- **Data Prompting** — All guest and reservation data is embedded in the prompt in CSV, JSON, or XML format. Useful for benchmarking and comparison.

Guest records support multilingual names across 8 writing systems: Latin, Cyrillic, Chinese, Japanese, Arabic, Devanagari, Korean, and Nordic.

### Performance Testing
A built-in suite for benchmarking LLM query performance with the following capabilities:
- **Sequential and concurrent batch testing** — Run N requests one-after-another or in parallel
- **Single-guest and multi-guest modes** — Test with one repeated query or rotate across different guests
- **Configurable data format** — Choose between tool calling, CSV, JSON, or XML data embedding
- **Results persistence** — All results stored in SQLite with full metadata (model, version, timestamps, responses)
- **Batch tracking** — Each test run is grouped by a unique batch ID with an optional friendly name
- **Manual validation** — Flag individual results as valid/invalid for accuracy analysis
- **Batch comparison** — Compare results across different test configurations

### Configuration Management
Persistent application settings managed through a dedicated web page:
- LLM model endpoint and model selection
- Thinking mode toggle
- Expected response format
- Settings are saved to disk and survive server restarts

### Data Export
Export all guest and reservation data in multiple formats:
- **CSV** — Flat file with one row per reservation, including guest and room details
- **JSON** — Nested structure with rooms and guests (with embedded reservations)
- **XML** — Hierarchical markup format

Exported files are saved to the `data/` directory and can be regenerated on demand from the web UI.

## Project Structure

```
ConciergeOS/
├── create_hotel_db.py                  # SQLite database initialization
├── pyproject.toml                      # Project metadata & dependencies
├── app/                                # FastAPI backend (REST API only)
│   ├── config.json                     # Persistent configuration (auto-generated)
│   ├── config.py                       # Configuration management
│   ├── main.py                         # FastAPI app & route registration
│   ├── db.py                           # Database session setup
│   ├── enums.py                        # Shared enumerations
│   ├── models.py                       # SQLAlchemy ORM models
│   ├── schemas.py                      # Pydantic request/response schemas
│   ├── routes/                         # API route modules
│   │   ├── __init__.py                 # Router exports
│   │   ├── guest_search.py             # Guest search API endpoints
│   │   ├── performance_testing.py      # Performance testing API endpoints
│   │   ├── reservations.py             # Reservations API endpoints
│   │   └── settings.py                 # Settings API endpoints
│   └── services/                       # Business logic
│       ├── core.py                     # Reservation queries & error detection
│       ├── debug.py                    # Debug endpoints
│       ├── llm.py                      # LLM client, prompts, data exporters
│       └── tool_calling.py             # LLM tool-calling service
├── frontend/                           # React SPA (Vite + TypeScript)
│   ├── vite.config.ts                  # Vite build configuration
│   ├── tsconfig.json                   # TypeScript configuration
│   ├── index.html                      # HTML entry point
│   └── src/                            # React source code
│       ├── main.tsx                    # React entry point
│       ├── App.tsx                     # Router configuration
│       ├── components/                 # Shared UI components
│       │   ├── Header.tsx              # Navigation header
│       │   └── ui/                     # Reusable UI primitives
│       ├── pages/                      # Page components
│       │   ├── Reservations.tsx        # Reservations dashboard
│       │   ├── GuestSearch.tsx         # Guest search page
│       │   ├── PerformanceTesting.tsx  # Performance testing dashboard
│       │   ├── Settings.tsx            # Configuration settings page
│       │   └── components/             # Page-specific components
│       ├── services/                   # API client
│       │   └── api.ts                  # Fetch wrapper for backend API
│       ├── types/                      # TypeScript type definitions
│       └── utils/                      # Utility functions
├── data/                               # Exported data files (auto-generated)
│   ├── guests_data.csv
│   ├── guests_data.json
│   └── guests_data.xml
├── Generator/                          # Data generation & utility scripts
│   ├── generate_names.py               # Multilingual name generator
│   ├── generate_rooms.py               # Room data generator
│   ├── populate_rooms.py               # Insert rooms into database
│   ├── populate_reservations.py        # Generate guests & reservations
│   ├── shift_reservations.py           # Shift all reservation dates by N days
│   ├── setup_errors.py                 # Inject controlled errors for testing
│   ├── setup_performance_guests.py     # Create dedicated performance test guests
│   └── utils.py                        # Shared utilities
├── PerformanceTesting/                 # LLM performance testing suite
│   ├── db.py                           # Results database (SQLite)
│   ├── run_performance_tests.py        # Test runner (sequential & concurrent)
│   └── manual_performance_analysis.sql # SQL queries for manual analysis
└── performance_tests.db                # Performance test results (auto-created)
```

## API Endpoints

### Reservations
| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/reservations` | Reservations grouped by room with detected errors |

### Guest Search
| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/guest-search` | Query the LLM for guest information (body: `{ "customer_name": "..." }`) |

### Settings
| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/settings` | Current global configuration |
| `POST` | `/api/settings` | Update configuration (body: `{ "test_settings": { ... } }`) |
| `GET` | `/api/models` | List available models from the configured LLM endpoint |

### Performance Testing
| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/performance-testing` | Run performance tests with configurable settings |
| `GET` | `/api/performance-testing/results` | Latest 100 test results |
| `GET` | `/api/performance-testing/all-results` | All test results (no limit) |
| `GET` | `/api/performance-testing/batches` | All unique test batches |
| `GET` | `/api/performance-testing/results-by-batch?batch_uuid=...` | Results for a specific batch |
| `PATCH` | `/api/performance-testing/result/{id}` | Update `valid_response` flag for a result |
| `DELETE` | `/api/performance-testing/batch/{batch_uuid}` | Delete all results for a batch |
| `POST` | `/api/performance-testing/setup-guests` | Create 13 dedicated test guests with 4 reservations each |
| `GET` | `/api/performance-testing/test-guests` | List current performance test guests |
| `POST` | `/api/performance-testing/generate-xml` | Regenerate CSV data file |
| `POST` | `/api/performance-testing/generate-all` | Regenerate all data files (CSV, JSON, XML) |

### Debug
| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/debug/tool-calling-info` | Info about available tools and LLM configuration |
| `POST` | `/api/debug/test-tool-call` | Test a specific tool call directly |
| `POST` | `/api/debug/test-llm-completion` | Test LLM completion with tool calling |
| `POST` | `/api/debug/shift-reservations` | Shift reservation dates by N days |

## Data Model

### Rooms
Each room has a name, booking channel (`ANY`, `ON_SITE_ONLY`, `STAFF_ASSIGNMENT`), and configurable check-in/check-out times. STAFF_ASSIGNMENT rooms use `00:00` for both times.

### Guests
Guest records include first name, last name, date of birth, special guest flag, and optional special preferences. Names support 8 writing systems (Latin, Cyrillic, Chinese, Japanese, Arabic, Devanagari, Korean, Nordic).

### Reservations
Reservations link guests to rooms with the following status lifecycle:
`PENDING` → `CONFIRMED` → `CHECKED_IN` → `CHECKED_OUT` (or `CANCELLED`)

Booking source is determined by room channel: `WALK_IN` for ON_SITE_ONLY, random of `WEBSITE`/`PHONE`/`OTA` for ANY, and `INTERNAL` for STAFF_ASSIGNMENT.

## Data Generation

### Generator Scripts

| Script | Purpose |
|--------|---------|
| `generate_names.py` | Generate ~50 names per alphabet (400 total) across 8 writing systems |
| `generate_rooms.py` | Create room definitions (~205 rooms across 3 wings) as `rooms.json` |
| `populate_rooms.py` | Insert generated rooms into the database |
| `populate_reservations.py` | Create realistic guest and reservation data with weighted status distribution and intentional name collisions |
| `shift_reservations.py` | Shift all reservation dates by N days forward or backward |
| `setup_errors.py` | Inject controlled status/date errors into existing reservations |
| `setup_performance_guests.py` | Create 13 dedicated test guests with 4 reservations each for benchmarking |

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- SQLite 3 (built into Python standard library)
- Python dependencies: `fastapi`, `openai`, `pydantic`, `requests`, `sqlalchemy`, `uvicorn`, `httpx`

Install with:
```bash
pip install -e .
# or
uv pip install -e .
```

### Setup

#### 1. Initialize the Database
```bash
python create_hotel_db.py [--recreate]
```
Creates `hotel.db` with tables for Rooms, Guests, and Reservations. Use `--recreate` to start fresh.

#### 2. Generate Name Data
```bash
python Generator/generate_names.py
```

#### 3. Generate and Populate Rooms
```bash
python Generator/generate_rooms.py
python Generator/populate_rooms.py
```

#### 4. Populate Guests and Reservations
```bash
python Generator/populate_reservations.py
```

#### 5. (Optional) Setup Performance Test Guests
```bash
python Generator/setup_performance_guests.py
```

### Running the Application

Start both the frontend and backend as independent servers:

```bash
# Terminal 1 — React frontend (port 5173)
cd frontend && npm run dev

# Terminal 2 — FastAPI backend (port 8000)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:5173` in your browser. The frontend will automatically proxy API requests to `http://localhost:8000`.

### Utility Scripts

#### Shift Reservation Dates
```bash
python Generator/shift_reservations.py              # Shift by 1 day (default)
python Generator/shift_reservations.py --days 3     # Shift forward by 3 days
python Generator/shift_reservations.py --days -2    # Shift backward by 2 days
```

#### Inject Controlled Errors (for testing)
```bash
python Generator/setup_errors.py
```
Finds reservations with name collisions and introduces controlled errors (erroneous statuses and unsynchronized dates). Affected IDs are persisted to `Generator/erroneous_reservations.json`.

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.