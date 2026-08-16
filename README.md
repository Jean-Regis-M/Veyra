# VEYRA — Genomic Intelligence

> An end-to-end, interpretable CRISPR/Cas9 guide RNA design, off-target risk assessment, and empirical calibration pipeline.

---

## System Architecture

The VEYRA system runs across three strictly layered tiers:

| Tier | Component | Technology | Default Port | Description |
|---|---|---|---|---|
| **Frontend** | Web UI / Console | Next.js 16 (React 19, Tailwind CSS) | `http://localhost:3000` | Interactive guide RNA visualizer, sequence analyzer, and AI orchestration console. |
| **Midend** | Orchestration & AI | FastAPI (Python 3.12) | `http://localhost:8080` | Boundary validation, SSE execution streaming, skill orchestration, and AI reasoning. |
| **Backend** | Deterministic Core | FastAPI, BWA, Cas-OFFinder, ViennaRNA | `http://localhost:8000` | PAM discovery, cut-site geometry, sequence thermodynamics, CFD scoring, and off-target search. |

---

## Quick Start — Turning On All Services

Open separate terminal tabs or windows for each service.

### 1. Start the Backend (Port 8000)

```bash
cd /home/hrirake/Desktop/hck15
PYTHONPATH=veyra/backend ./veyra/backend/venv/bin/uvicorn veyra.backend.http_api.app:app --host 0.0.0.0 --port 8000 --reload
```

*Or from the backend directory:*
```bash
cd /home/hrirake/Desktop/hck15/veyra/backend
./venv/bin/uvicorn http_api.app:app --host 0.0.0.0 --port 8000 --reload
```

- **Health Check:** `curl http://localhost:8000/health`
- **Swagger Docs:** `http://localhost:8000/docs`

---

### 2. Start the Midend (Port 8080)

```bash
cd /home/hrirake/Desktop/hck15
PYTHONPATH=. ./veyra/backend/venv/bin/uvicorn veyra.midend.http_api.app:app --host 0.0.0.0 --port 8080 --reload
```

- **Health Check:** `curl http://localhost:8080/health`
- **Skills Discovery:** `curl http://localhost:8080/skills`
- **Swagger Docs:** `http://localhost:8080/docs`

---

### 3. Start the Frontend (Port 3000)

```bash
cd /home/hrirake/Desktop/hck15
npm run dev
```

- **Web App:** Open [http://localhost:3000](http://localhost:3000) in your browser.
- **Analysis Console:** [http://localhost:3000/analyze](http://localhost:3000/analyze)
- **Midend Live Session:** [http://localhost:3000/midend](http://localhost:3000/midend)
- **Raw API Explorer:** [http://localhost:3000/raw](http://localhost:3000/raw)

---

## Running Automated Verification & Tests

### Backend Full Regression Suite (425 Tests)
```bash
cd /home/hrirake/Desktop/hck15/veyra/backend
./venv/bin/pytest tests/ -v
```

### Midend Full Test Suite (35 Tests)
```bash
cd /home/hrirake/Desktop/hck15
PYTHONPATH=. ./veyra/backend/venv/bin/pytest veyra/midend/tests/ -v
```

### Frontend Type-Checking & Linting
```bash
cd /home/hrirake/Desktop/hck15
npm run lint
npm run build
```

---

## Input Classes & Calibration

- **`analysis_input`**: FASTA, FASTQ, GenBank, or raw DNA strings for standard CRISPR analysis workflows.
- **`calibration_input`**: Optional CSV/TSV labeled experimental datasets for empirical model fitting.
- **Critical Rule**: Calibration is strictly **optional**. Normal gene-cutting and PAM workflows never require calibration datasets.
