# ConciergeOS

> A modern hotel concierge and reservation management system powered by AI.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.137+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org/)

## 📺 Watch & Learn

Get started by watching our project tutorial series:

[![ConciergeOS Tutorial Playlist](https://img.shields.io/badge/YouTube-Playlist-red?style=for-the-badge&logo=youtube)](https://www.youtube.com/playlist?list=PL3QNSFtuykvkuKuNExP1lQ6jGdDnJCKRc)

[Watch the full tutorial playlist →](https://www.youtube.com/playlist?list=PL3QNSFtuykvkuKuNExP1lQ6jGdDnJCKRc)

## 🏨 What is ConciergeOS?

ConciergeOS is a complete hotel management solution that combines:

- **Reservation Dashboard** — Visualize all reservations grouped by room with automatic error detection for status mismatches and date inconsistencies.
- **AI-Powered Guest Search** — Search for guests using natural language. Supports 8 writing systems including Latin, Cyrillic, Arabic, Chinese, Japanese, Devanagari, Korean, and Nordic scripts.
- **Performance Testing Suite** — Benchmark LLM query performance with sequential and concurrent testing modes.
- **Data Export** — Export guest and reservation data in CSV, JSON, or XML formats.

## ✨ Key Features

### Reservation Management
- Automatic detection of erroneous reservation statuses
- Date synchronization validation (future check-ins, past check-outs)
- Rooms categorized by booking channel (public, staff-only, on-site)

### Guest Search
- **Tool Calling Mode** — LLM invokes read-only database query tools on demand
- **Data Prompting Mode** — All data embedded in prompt (CSV/JSON/XML) for benchmarking
- Multilingual name support across 8 writing systems

### Performance Testing
- Sequential and concurrent batch testing
- Single-guest and multi-guest modes
- Configurable data formats (tool calling, CSV, JSON, XML)
- Results persistence and batch comparison

## 🚀 Quick Start

For detailed step-by-step instructions, see the [Quick Start Guide](QUICKSTART.md).

**TL;DR:**
```bash
uv sync && cd backend && uv run alembic upgrade head
uv run python Generator/generate_names.py && uv run python Generator/populate_rooms.py
uv run python Generator/populate_reservations.py
```

Then start the backend (`uv run uvicorn app.main:app --reload`) and frontend (`cd ../frontend && npm run dev`).

## 📁 Project Structure

```
ConciergeOS/
├── backend/                    # FastAPI backend application
│   ├── app/                    # Core application (routes, services, models)
│   ├── Generator/              # Data generation & utility scripts
│   ├── PerformanceTesting/     # LLM performance benchmarking suite
│   ├── alembic/                # Database migrations
│   ├── alembic.ini             # Migration configuration
│   ├── data/                   # Exported data files
│   └── database.db             # SQLite database (auto-created)
├── frontend/                   # React + TypeScript + Vite SPA
│   └── src/                    # Source code
└── docs/                       # Technical documentation
```

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Guest Search Multimodal](docs/IMPLEMENTATION_GUEST_SEARCH_MULTIMODAL.md) | Guest search implementation details |
| [Performance Dashboard](docs/IMPLEMENTATION_PERFORMANCE_DASHBOARD.md) | Performance testing dashboard |
| [Prompting System](docs/IMPLEMENTATION_PROMPTING_SYSTEM.md) | Prompt versioning and chain execution |
| [Database Population](backend/Generator/DATABASE_POPULATION.md) | Complete database setup & wrapper scripts guide |

## 🛠️ Development

For detailed development instructions, see the component-specific guides:

| Guide | Description |
|-------|-------------|
| [Backend Development](backend/DEVELOPMENT.md) | Server setup, migrations, data generation scripts |
| [Frontend Development](frontend/DEVELOPMENT.md) | React app, components, build process |

## 🔌 API Documentation

ConciergeOS uses FastAPI's built-in OpenAPI 3.1 support for auto-generated API documentation.

### Interactive Docs

When the backend is running, access:

| Format | URL | Description |
|--------|-----|-------------|
| Swagger UI | `http://localhost:8000/docs` | Interactive OpenAPI docs with try-it-out |
| ReDoc | `http://localhost:8000/redoc` | Alternate OpenAPI documentation |
| OpenAPI JSON | `http://localhost:8000/openapi.json` | Raw OpenAPI 3.1.0 specification |

### Export OpenAPI Spec

Generate the OpenAPI specification file using UV:

```bash
# Export to default location (backend/openapi.json)
uv run python backend/export_openapi.py

# Export to custom location
uv run python backend/export_openapi.py docs/openapi.json
```

### Available Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/reservations` | Reservations grouped by room with error detection |
| POST | `/api/reservations/shift` | Shift all reservation dates forward/backward |
| POST | `/api/guest-search` | AI-powered natural language guest search |
| POST | `/api/guest-search/extract-name` | Extract guest name from image/audio |
| GET | `/api/settings` | Get current application configuration |
| POST | `/api/settings` | Update application configuration |
| GET | `/api/models` | Get available LLM models |
| POST | `/api/performance-testing` | Run performance benchmarks |
| GET | `/api/performance-testing/results` | Get latest test results |
| GET | `/api/performance-testing/stats` | Get aggregated performance stats |
| POST | `/api/prompts/ai-improve` | LLM-assisted prompt improvement |
| GET | `/api/prompts` | List all prompts |

See the interactive Swagger UI for the complete endpoint reference with request/response schemas.

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.