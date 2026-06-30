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
- Multilingual name support

### Performance Testing
- Sequential and concurrent batch testing
- Single-guest and multi-guest modes
- Configurable data formats (tool calling, CSV, JSON, XML)
- Results persistence and batch comparison

## 🚀 Quick Start

For detailed step-by-step instructions, see the [Quick Start Guide](QUICKSTART.md).

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

For a complete list of documentation, see [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md).

## 🛠️ Development

| Component | Guide | Description |
|-----------|-------|-------------|
| Backend | [backend/README.md](backend/README.md) | Overview, quick start, project structure |
| Backend | [backend/DEVELOPMENT.md](backend/DEVELOPMENT.md) | Server setup, migrations, data generation scripts |
| Frontend | [frontend/DEVELOPMENT.md](frontend/DEVELOPMENT.md) | React app, components, build process |

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.