# HCP Web Crawler — AI Agent

> AI-powered Healthcare Provider contact discovery from the open internet.

## Architecture

- **Backend**: FastAPI + LangGraph (agentic orchestration) + PyDoll (browser automation)
- **Frontend**: Streamlit with glassmorphism UI
- **LLM**: Azure OpenAI / OpenAI (configurable)
- **Infra**: Docker + Helm + Jenkins + OpenShift

## Quick Start

### 1. Install dependencies (UV)

```bash
pip install uv
uv sync --all-extras
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your LLM API keys
```

### 3. Generate sample data

```bash
uv run python sample_data/create_sample.py
```

### 4. Start the backend

```bash
uv run uvicorn hcp_crawler.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Start the frontend

```bash
uv run streamlit run frontend/app.py --server.port 8501
```

### 6. Run tests

```bash
uv run pytest tests/ -v
```

## Project Structure

```
├── src/hcp_crawler/        # FastAPI backend
│   ├── services/agent/     # LangGraph pipeline (state, nodes, graph)
│   ├── services/           # Excel, Search, Scraper, LLM, Stats
│   ├── api/                # REST endpoints
│   └── models/             # Pydantic schemas + SQLAlchemy ORM
├── frontend/               # Streamlit dashboard
├── helm/                   # Helm chart for OpenShift
├── tests/                  # Pytest test suite
└── Jenkinsfile             # CI/CD pipeline
```

## Agent Pipeline

```
Excel Row → QueryBuilder → GoogleSearch (PyDoll) → PageScraper (PyDoll)
  → LLM Extractor → LLM Verifier → Save Results + Source URLs
```

Each step is a LangGraph node with conditional retry logic across query tiers
(doximity/npiprofile → .gov/.edu → general search).

## Dashboard KPIs

- Records Processed / HCPs Found / Not Found
- Success Rate / Hours Saved / Dollars Saved

## License

Internal use only.
