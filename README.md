# TraceNova

TraceNova is an event-driven platform for detecting pipeline degradation and producing
evidence-backed root-cause analysis.

## Current status

Phase 0, Phase 1, Phase 2, and Phase 3 (Metrics Aggregation) are completed.
Phase 4 — Historical Baselines is currently active.

## Local setup

Prerequisites:

- Python 3.12
- Docker Desktop, running with the Linux engine available

Create a local environment and install development dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run quality checks:

```powershell
python -m ruff check .
python -m mypy
python -m pytest
```

Start the local infrastructure and API after Docker Desktop is running:

```powershell
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/health
docker compose down
```

## Delivery rule

Each phase is implemented independently, tested locally, committed, and pushed only after
its acceptance criteria pass.

