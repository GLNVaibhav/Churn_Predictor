# Universal Churn Intelligence Framework - Project Outline

## Project Identity

**Name:** Universal Churn Intelligence Framework (UCIF)

**Purpose:** Provide an explainable, sector-aware churn intelligence framework that turns heterogeneous customer datasets into auditable prediction, diagnostic, and decision-support outputs.

**Current architecture:** UCIF is now a layered product, not only a script-driven churn predictor. The product flow is `Frontend -> API -> Framework Mapper -> UCIF Framework`. The core framework remains in `universal_churn/`; it is consumed by the API through adapter and mapper boundaries instead of becoming the backend folder itself.

## Vision

UCIF exists to make churn prediction trustworthy enough for analytical use. Instead of stopping at "will this customer churn?", it asks whether the dataset is understandable, whether enough business evidence exists, whether prediction is reliable, which pipeline should run, why the result was produced, and what the analyst should inspect.

The framework follows the principle of diagnostics before decisions. It supports human decision-makers with transparent evidence; it does not make autonomous business decisions.

## Current System Shape

```text
User / analyst
    |
    v
Next.js frontend
    |
    v
FastAPI API layer
    |
    v
FrameworkAdapter and Framework Mapper
    |
    v
Core universal_churn framework
    |
    v
Mapped API contracts and persisted execution record
    |
    v
Dashboards, pipeline views, reports, predictions, and decision intelligence
```

This split gives UCIF two working interfaces:

- The CLI remains the reference implementation for direct framework execution.
- The FastAPI API is the web/runtime boundary.
- The Framework Adapter and Framework Mapper are the controlled bridge into `universal_churn/`.
- The Next.js platform turns the same framework output into an interactive enterprise workflow.

## Architectural Layers

### 1. Core Intelligence Framework

Location: `universal_churn/`

This layer owns UCIF's domain behavior. It contains dataset understanding, semantic inference, coverage assessment, data quality checks, routing, prediction, explanation, business reasoning, and enterprise reporting.

Key modules:

- `cli.py`: command-line reference implementation.
- `preprocessing.py`: sector detection and dataset preparation support.
- `semantic_intelligence/`: evidence extraction, profiling, inference, knowledge loading, validation, governance, and observability.
- `canonical_feature_builder.py`, `canonical_mapping.py`, `semantic_feature_resolver.py`: canonical field and concept resolution.
- `coverage.py`: coverage intelligence.
- `quality_gate.py`: quality and readiness checks.
- `routing.py`: adaptive prediction routing.
- `sector_pipeline.py`: sector model execution.
- `universal_pipeline.py`: universal model execution.
- `prediction_explanation_report.py`: prediction explanation output.
- `decision_intelligence.py` and `decision_report.py`: decision-readiness and analyst-facing interpretation.
- `business_reasoning.py`, `business_meaning.py`, `business_concept_graph.py`: business interpretation and reasoning.
- `adaptive_business/`: optional external business-context evidence.
- `prediction_intelligence/`: prediction confidence, assurance, stability, signal intelligence, and consistency engines.
- `enterprise_reporting.py`: report artifact generation.
- `udif.py` and `udif_rendering.py`: diagnostic information framework and rendering.

### 2. Backend API and Runtime

Location: `backend/`

The backend is an orchestration and transport layer. It should not duplicate framework business logic, and `universal_churn/` should not be treated as a replacement backend folder.

Key responsibilities:

- Accept and profile uploaded CSV files.
- Start managed analysis executions.
- Run framework analysis in background tasks.
- Persist upload metadata and execution records.
- Map raw framework output into stable API contracts through the framework mapper.
- Provide UI-ready platform enrichment and summaries.
- Expose execution, pipeline, prediction, report, event, diagnostics, semantic intelligence, framework mapper, and decision endpoints.

Key modules:

- `api/app.py`: FastAPI application factory, middleware, CORS, exception handlers, and router registration.
- `api/routers/upload.py`: CSV upload and initial profiling.
- `api/routers/analysis.py`: managed analysis start endpoint.
- `api/routers/executions.py`: execution-state and result endpoints.
- `adapters/framework_adapter.py`: anti-corruption layer into `universal_churn`.
- `services/analysis_service.py`: service orchestrator for one complete analysis.
- `services/upload_service.py`: upload profiling and metadata creation.
- `services/report_service.py`: report generation wrapper.
- `runtime/manager.py`: background execution lifecycle.
- `runtime/executor.py`: analysis task coroutine and execution-record assembly.
- `runtime/repository.py`: file-backed JSON repository for uploads and runs.
- `contracts/`: framework-facing and API-facing typed response objects.
- `mappers/`: framework-to-platform mapping and enrichment.
- `presentation/`: UI-facing prediction rollups.

### 3. Frontend Enterprise Console

Location: `frontend/`

The frontend is a Next.js App Router application that presents the framework as a usable platform.

Key responsibilities:

- Upload datasets.
- Start analyses.
- Show active and historical executions.
- Display pipeline state and stage details.
- Present predictions and customer-level detail.
- Surface reports and decision intelligence.
- Provide dashboards, monitoring, workspace, settings, and knowledge views.

Key modules:

- `src/app/`: pages and route structure.
- `src/app/api/backend/[...path]/route.ts`: same-origin proxy from frontend to FastAPI.
- `src/lib/api/`: API client, endpoint map, upload, analysis, executions, reports, and view-model utilities.
- `src/lib/hooks/`: execution and workspace hooks.
- `src/lib/context/`: execution and dev-mode contexts.
- `src/components/layout/`: application shell, sidebar, and topbar.
- `src/components/pipeline/`: pipeline graph and stage detail components.
- `src/components/predictions/`: prediction table and detail sheet.
- `src/components/reports/`: report explorer.
- `src/components/dashboard/`: dashboard tables and summaries.
- `src/components/charts/`: churn trend, contribution, and concept-confidence charts.

## Runtime Execution Flow

1. The user uploads a CSV from the frontend.
2. The frontend calls `POST /api/v1/upload` through the backend proxy.
3. The backend stores the file under `data/uploads/{upload_id}/`.
4. `UploadService` profiles the dataset, detects sector signals, computes initial metadata, and returns preview information.
5. The user starts analysis through `POST /api/v1/analyze`.
6. `ExecutionManager` creates an execution ID and persists a pending/running record.
7. `run_analysis_task` executes the analysis coroutine.
8. `AnalysisService` initializes, invokes `FrameworkAdapter`, passes the result through the framework mapper, adds presentation rollups, and optionally generates reports.
9. `FrameworkAdapter` mirrors CLI control flow and calls the core `universal_churn/` framework exactly once.
10. The core pipeline detects or uses the sector, builds canonical features, computes coverage, runs quality checks, routes prediction, executes the selected model path, attaches explanations, and attaches decision intelligence.
11. Backend mappers enrich the response for the platform.
12. `ExecutionRepository` persists the complete run under `data/runs/{execution_id}.json`.
13. The frontend reads execution-specific endpoints to render dashboards, reports, prediction tables, events, and decision views.

## Core Pipeline Flow

```text
Input CSV
    |
    v
Dataset profiling and sector detection
    |
    v
Business meaning and semantic evidence extraction
    |
    v
Canonical mapping and feature reconstruction
    |
    v
Coverage intelligence and concept confidence
    |
    v
Quality gate
    |
    v
Adaptive routing
    |
    +--> Sector pipeline
    |
    +--> Universal pipeline
    |
    +--> Refusal for unreliable prediction
    |
    v
Prediction explanation
    |
    v
Decision intelligence
    |
    v
Reports, persisted execution state, and UI-ready payloads
```

## Backend API Surface

The FastAPI service registers routers under `/api/v1`.

Primary endpoints:

- `GET /api/v1/health`
- `POST /api/v1/upload`
- `POST /api/v1/analyze`
- `GET /api/v1/executions`
- `GET /api/v1/analysis/{execution_id}`
- `GET /api/v1/analysis/{execution_id}/pipeline`
- `GET /api/v1/analysis/{execution_id}/predictions`
- `GET /api/v1/analysis/{execution_id}/reports`
- `GET /api/v1/analysis/{execution_id}/reports/text`
- `GET /api/v1/analysis/{execution_id}/decision`
- `GET /api/v1/analysis/{execution_id}/context`
- `GET /api/v1/analysis/{execution_id}/events`
- `GET /api/v1/analysis/{execution_id}/diagnostics`
- `GET /api/v1/analysis/{execution_id}/feature-engineering`
- `GET /api/v1/analysis/{execution_id}/semantic-intelligence`
- `GET /api/v1/analysis/{execution_id}/framework-mapper`

Framework and model-discovery routes are provided by `backend/api/routers/framework.py`.

## Data and Persistence

Current persistence is intentionally simple and replaceable:

- Uploaded CSV files are stored under `data/uploads/`.
- Upload metadata and execution payloads are stored as JSON through `ExecutionRepository`.
- Execution records are stored under `data/runs/`.
- The repository implements a protocol-style boundary so a database or queue-backed runtime can replace file storage later.

## Supported Sectors

Current sector coverage:

- Telecom
- Banking
- E-commerce
- Healthcare

Each sector can provide:

- Canonical feature definitions
- Business concepts
- Entities
- Relationships
- Synonyms
- Sector-specific datasets
- Sector-specific model and routing behavior

The knowledge architecture is extensible to additional sectors without changing the API/runtime boundary.

## Project Objectives

### Universal Dataset Understanding

Accept customer datasets with varying schemas and map them into a shared churn-intelligence vocabulary.

### Prediction Readiness

Measure whether the dataset has enough quality, coverage, and concept confidence for prediction.

### Adaptive Routing

Choose the appropriate path among sector prediction, universal prediction, and refusal.

### Explainability

Attach prediction explanations, business evidence, confidence signals, and warnings.

### Decision Support

Turn technical output into readable, auditable decision-intelligence summaries for analysts.

### Platform Readiness

Expose framework outputs through stable API contracts, persisted execution state, and an interactive frontend.

## Development Commands

Run the CLI:

```powershell
python main.py --input data/telecom/new_telecom_customers.csv --mode auto --explain
```

Run the backend:

```powershell
uvicorn backend.api.app:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Run tests:

```powershell
pytest
pytest backend/tests
cd frontend
npm run lint
npm run build
```

Some backend integration tests require trained model artifacts under `outputs/`. Missing-artifact tests are skipped where the test suite marks them as optional.

## Engineering Boundaries

The current architecture depends on several important boundaries:

- `universal_churn/` owns intelligence and business behavior.
- `backend/adapters/framework_adapter.py` is the backend's only direct execution bridge into the framework.
- `backend/services/analysis_service.py` orchestrates execution but does not make routing or scoring decisions.
- `backend/mappers/` translates and enriches framework output without changing domain meaning.
- `backend/runtime/` owns execution lifecycle and persistence.
- `frontend/` consumes API contracts and should not reproduce framework logic.

These boundaries keep the system testable and make future deployment changes easier.

## Current Deliverables

- CLI reference implementation
- Core UCIF framework modules
- Sector knowledge packs and sample datasets
- FastAPI backend with upload, analysis, execution, and framework routes
- Background execution manager
- File-backed run persistence
- Typed contracts and response mappers
- Next.js enterprise console
- Backend and core framework tests
- Publication and report artifacts

## Future Extension Points

Likely extension areas:

- Database-backed execution repository
- Queue-backed execution runtime
- Authentication and tenant-aware storage
- More sector knowledge packs
- More trained sector models
- Richer report export from the web platform
- More detailed observability and replay tooling
- Deployment-specific environment configuration

The framework has already been structured so these additions can happen around the current boundaries rather than by rewriting the core pipeline.
