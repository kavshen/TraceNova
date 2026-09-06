# TraceNova — Implementation Plan

## How to Use This Document

This is the implementation roadmap for TraceNova.

### Critical development rule

**Implement one phase at a time.**

For every phase:

1. Read `docs/PROJECT_SPEC.md`.
2. Read the current phase in this file.
3. Implement only the current phase.
4. Add/update tests.
5. Run the test suite.
6. Run formatting/linting/type checks.
7. Update documentation.
8. Verify the system manually where applicable.
9. Do not introduce technologies belonging to later phases unless required by the current phase.

### Architecture rules

- Backend first.
- Deterministic detection before AI.
- Heuristic RCA before LLM RCA.
- Dependency model before graph RAG.
- Basic retrieval before hybrid retrieval.
- Reliability before performance optimization.
- Do not add Kafka only for resume value.
- Do not replace deterministic logic with an LLM.
- Keep all event contracts versioned.
- Prefer idempotent operations.
- Every important asynchronous workflow must have correlation IDs.

---

# Phase 0 — Repository Foundation

## Objective

Create the repository structure and development foundation.

## Tasks

- Initialize Git repository.
- Create monorepo structure.
- Add Python project configuration.
- Add shared configuration package.
- Add Pydantic settings.
- Add structured logging.
- Add common error model.
- Add `.env.example`.
- Add Docker Compose skeleton.
- Add PostgreSQL.
- Add Redis.
- Add health endpoints.
- Add CI workflow.
- Add formatting/linting/type checking.
- Add baseline unit-test setup.

## Suggested tools

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- pytest
- Ruff
- mypy
- Docker Compose

## Acceptance criteria

- Repository starts cleanly.
- PostgreSQL starts.
- Redis starts.
- Services expose `/health`.
- Tests execute in CI.
- No secrets committed.

---

# Phase 1 — Synthetic Pipeline Simulator

## Objective

Build a production-quality simulator that generates realistic pipeline execution events.

## Implement

Pipeline model:

```text
Pipeline
- id
- name
- owner
- schedule
- baseline configuration
- dependencies
```

Execution model:

```text
PipelineRun
- id
- pipeline_id
- started_at
- completed_at
- duration_ms
- status
- attempt
```

## Events

Implement:

- `PIPELINE_STARTED`
- `PIPELINE_COMPLETED`
- `PIPELINE_FAILED`
- `PIPELINE_RETRIED`

## Scenarios

Implement deterministic scenario controls:

- normal
- slow
- failure
- retry storm

## API

Example:

```text
POST /pipelines
GET /pipelines
POST /pipelines/{id}/run
GET /pipelines/{id}/runs
```

## Tests

- Event schema validation
- Pipeline creation
- Run creation
- Successful execution
- Failed execution
- Retry execution
- Deterministic scenario behavior

## Acceptance criteria

A developer can start the system and generate realistic pipeline execution data locally.

---

# Phase 2 — Event Streaming

## Objective

Introduce asynchronous event processing.

## Technology

Use Redis Streams initially.

## Implement

- Event publisher
- Event consumer
- Consumer group
- Retry handling
- Event acknowledgement
- Dead-letter mechanism
- Correlation ID propagation

## Event envelope

```json
{
  "event_id": "...",
  "event_type": "...",
  "schema_version": 1,
  "pipeline_id": "...",
  "correlation_id": "...",
  "timestamp": "...",
  "payload": {}
}
```

## Reliability requirements

- Duplicate event handling
- Consumer restart handling
- Malformed-event handling
- Retry with exponential backoff
- DLQ

## Acceptance criteria

Pipeline simulator publishes events and independent consumers process them asynchronously.

---

# Phase 3 — Metrics Aggregation

## Objective

Convert raw execution events into operational metrics.

## Implement

Calculate:

- Count
- Success rate
- Failure rate
- Retry rate
- Average duration
- Median duration
- P95 duration
- Throughput

## Storage

Create metric tables with appropriate indexes.

## APIs

```text
GET /metrics/pipelines/{pipeline_id}
GET /metrics/pipelines/{pipeline_id}/timeseries
```

## Tests

Use deterministic event fixtures.

Validate metric calculations mathematically.

## Acceptance criteria

Given a known event set, the system returns exactly the expected metrics.

---

# Phase 4 — Historical Baselines

## Objective

Determine normal pipeline behavior.

## Initial strategy

Use rolling historical windows.

For each pipeline calculate:

- Median duration
- P95 duration
- Failure rate
- Retry rate
- Throughput

## Later improvements

Only after the basic version works:

- Time-of-day baselines
- Day-of-week baselines
- Seasonal behavior

## Acceptance criteria

The system can compare current metrics with a historical baseline.

---

# Phase 5 — Degradation Detection

## Objective

Detect abnormal pipeline behavior.

## Signals

Implement:

- Duration deviation
- Failure-rate increase
- Retry-rate increase
- Throughput decrease

## Signal output

Each signal must contain:

```text
signal_type
current_value
baseline_value
deviation
threshold
severity
timestamp
```

## Acceptance criteria

Known synthetic degradation scenarios produce the expected detection signals.

---

# Phase 6 — GREEN / AMBER / RED Classification

## Objective

Convert detection signals into an explainable health classification.

## Classification

GREEN:

Normal.

AMBER:

Moderate degradation.

RED:

Severe degradation.

## Configuration

Use YAML or typed configuration rather than hard-coded thresholds.

Example:

```yaml
duration:
  amber_ratio: 1.25
  red_ratio: 1.75
```

## Output

```json
{
  "status": "RED",
  "reasons": [
    "DURATION_DEGRADATION",
    "FAILURE_RATE_INCREASE"
  ]
}
```

## Acceptance criteria

Classification is deterministic, configurable, and covered by boundary tests.

---

# Phase 7 — Incident Management

## Objective

Create incidents when significant degradation occurs.

## Incident model

```text
Incident
- id
- pipeline_id
- severity
- status
- created_at
- updated_at
- correlation_id
- reason_codes
```

## Lifecycle

```text
OPEN
→ INVESTIGATING
→ RESOLVED
→ CLOSED
```

## Requirements

- Idempotent incident creation
- Deduplication
- Incident APIs
- Incident timeline
- Incident status transitions

## APIs

```text
GET /incidents
GET /incidents/{id}
POST /incidents/{id}/resolve
```

## Acceptance criteria

Repeated detection events do not create duplicate incidents for the same active degradation.

---

# Phase 8 — Heuristic RCA

## Objective

Build deterministic root-cause analysis.

## Causes

Implement:

- DATABASE_BOTTLENECK
- UPSTREAM_API_FAILURE
- COMPUTE_SATURATION
- NETWORK_LATENCY
- DEPENDENCY_FAILURE
- RESOURCE_EXHAUSTION
- RECENT_DEPLOYMENT
- RETRY_STORM

## Approach

Build a scoring/rule engine.

Example:

```text
DB latency high           +0.40
Pipeline duration high    +0.20
Retry rate high           +0.15
Recent deployment         +0.15
-------------------------------
Database bottleneck       0.90
```

## Explainability

Store:

- Cause
- Score
- Contributing signals
- Missing evidence
- Rule IDs

## Acceptance criteria

RCA works with no LLM and returns ranked causes with explanations.

---

# Phase 9 — Dependency Analysis

## Objective

Add upstream/downstream reasoning.

## Implement

Dependency entities:

- Pipeline
- Service
- Database
- API
- Storage
- Queue

Relationships:

- depends_on
- upstream_of
- downstream_of

## Example

```text
Pipeline A
    ↓
Service B
    ↓
Database C
```

If C degrades, the RCA should identify C as a potential upstream cause.

## Tests

- Dependency creation
- Graph traversal
- Upstream lookup
- Cascading failure scenario

## Acceptance criteria

The system can trace a degraded pipeline to degraded upstream dependencies.

---

# Phase 10 — Historical Incident Knowledge Base

## Objective

Store past incidents for future investigation.

## Implement

Historical incident documents containing:

- Summary
- Root cause
- Timeline
- Evidence
- Resolution
- Tags

## Retrieval metadata

Add:

- Pipeline
- Service
- Root cause
- Date
- Severity
- Tags

## Acceptance criteria

Past incidents can be searched by structured filters.

---

# Phase 11 — Basic RAG

## Objective

Introduce retrieval-augmented investigation.

## Initial implementation

Use a simple vector retrieval path.

Possible storage:

- PostgreSQL + pgvector

## Documents

Index:

- Historical incidents
- Runbooks
- Pipeline documentation
- Operational guides

## Retrieval output

Every result should contain:

```text
document_id
chunk_id
text
score
source
metadata
```

## Guardrail

The LLM must only use retrieved content as knowledge-base evidence.

## Acceptance criteria

Given an incident, the system retrieves relevant historical incidents/runbooks.

---

# Phase 12 — Hybrid Retrieval

## Objective

Combine multiple retrieval strategies.

## Retrieval modes

### Vector

Semantic similarity.

### BM25 / keyword

Exact terminology and error messages.

### SQL

Structured metrics and historical facts.

### Graph

Dependency relationships.

## Query router

The system should choose retrieval based on query type.

Examples:

```text
"What happened to orders_daily?"
→ SQL + metrics

"Have we seen this error before?"
→ BM25 + vector

"What upstream dependency is affected?"
→ graph + health metrics

"Which runbook applies?"
→ vector + BM25
```

## Acceptance criteria

Hybrid retrieval improves retrieval evaluation compared with the basic vector-only baseline.

---

# Phase 13 — AI RCA Service

## Objective

Add LLM-assisted investigation.

## Input

- Incident
- Detection signals
- Heuristic RCA
- Retrieved evidence
- Dependency information

## Output

Structured RCA:

```text
summary
root_cause
confidence
supporting_evidence
alternative_causes
impact
timeline
recommendations
missing_evidence
evidence_conflicts
```

## Guardrails

- Structured output
- Evidence IDs required for claims
- No fabricated metrics
- Explicit uncertainty
- Timeout handling
- Retry handling
- Fallback to heuristic RCA

## Acceptance criteria

If the LLM is unavailable, the incident still receives a heuristic RCA.

---

# Phase 14 — Agentic RCA

## Objective

Turn AI RCA into controlled multi-step investigation.

## Agent workflow

```text
Incident
   ↓
Planner
   ↓
Hypotheses
   ↓
Tool selection
   ↓
Evidence retrieval
   ↓
Evidence grading
   ↓
Additional investigation
   ↓
Root cause ranking
   ↓
Final RCA
```

## Tools

Implement:

```text
get_pipeline_metrics
get_execution_history
get_dependency_health
search_logs
get_recent_deployments
search_similar_incidents
get_pipeline_dependencies
```

## Tool rules

- Read-only
- Typed inputs
- Typed outputs
- Timeouts
- Authorization
- Audit logs

## Acceptance criteria

The agent can investigate at least the database, upstream API, deployment, compute, and cascading-failure scenarios.

---

# Phase 15 — Evidence & Explainability

## Objective

Make every RCA auditable.

## Evidence model

```text
Evidence
- id
- type
- source
- timestamp
- claim
- confidence
- reference
```

## Evidence graph

Represent:

```text
Incident
  ↓
Hypothesis
  ↓
Evidence
  ↓
Conclusion
```

## Add

- Evidence IDs in final RCA
- Evidence confidence
- Conflicting evidence
- Missing evidence
- Evidence timeline

## Acceptance criteria

A reviewer can trace the final root-cause conclusion back to concrete evidence.

---

# Phase 16 — Dashboard

## Objective

Build an operational UI.

## Screens

### Overview

Show:

- Pipeline health
- GREEN/AMBER/RED counts
- Active incidents
- Recent degradations
- Event throughput

### Pipeline detail

Show:

- Current status
- Runtime trend
- Failure trend
- Retry trend
- Dependency health

### Incident detail

Show:

- Timeline
- Detection signals
- Reason codes
- Heuristic RCA
- AI RCA
- Evidence
- Root-cause confidence
- Recommendations

## Stack

- Next.js
- React
- TypeScript
- Tailwind
- shadcn/ui

## Acceptance criteria

A user can understand an incident without reading backend logs.

---

# Phase 17 — Observability

## Objective

Instrument the distributed system.

## Implement

OpenTelemetry tracing across:

```text
Simulator
 → Redis
 → Consumer
 → Detection
 → Incident
 → RCA
 → AI Agent
 → Tools
```

## Metrics

Track:

- API latency
- Event processing latency
- Queue depth
- Consumer lag
- Incident creation latency
- RCA latency
- LLM latency
- LLM errors
- DB latency
- Retry count
- DLQ count

## Dashboards

Create Grafana dashboards for:

1. System health
2. Event processing
3. Detection
4. Incidents
5. RCA/AI

## Acceptance criteria

A single incident can be traced end-to-end using its correlation ID.

---

# Phase 18 — Reliability & Failure Testing

## Objective

Prove the system behaves correctly under failures.

## Failure tests

### Redis failure

Expected:

- Producers retry.
- Consumers recover.
- No silent event loss.

### Database failure

Expected:

- Requests fail cleanly.
- Retry policy applies.
- System reports dependency health.

### Duplicate event

Expected:

- Idempotent handling.
- No duplicate metrics/incident.

### Malformed event

Expected:

- Validation failure.
- Event sent to DLQ.

### Consumer crash

Expected:

- Consumer restarts.
- Unacknowledged work is retried.

### LLM timeout

Expected:

- Heuristic RCA remains available.

### Vector store unavailable

Expected:

- Deterministic/heuristic investigation remains available.

## Acceptance criteria

Failure behavior is tested and documented.

---

# Phase 19 — Evaluation Framework

## Objective

Measure system quality instead of relying on demos.

## Build ground-truth dataset

Each scenario should define:

```text
scenario
expected_detection
expected_severity
expected_root_cause
expected_evidence
```

## Detection metrics

- Precision
- Recall
- F1
- False-positive rate
- Detection delay

## RCA metrics

- Top-1 accuracy
- Top-3 accuracy
- Evidence coverage
- Confidence calibration

## RAG metrics

- Retrieval recall
- Context precision
- Relevance
- Faithfulness

## Agent metrics

- Tool-selection accuracy
- Task completion
- Unnecessary calls
- Evidence coverage

## Acceptance criteria

The repository contains reproducible evaluation commands and reports.

---

# Phase 20 — Security Hardening

## Objective

Harden service boundaries and AI interactions.

## Implement

- API authentication where appropriate
- Role-based authorization for sensitive operations
- Read-only analytical database credentials
- Parameterized queries
- Input validation
- Secret handling
- Log redaction
- Prompt/input sanitization
- Tool authorization
- Audit logging

## AI restrictions

The AI agent must not:

- Execute arbitrary SQL
- Execute shell commands
- Modify infrastructure
- Change pipeline configuration
- Delete records

Unless a future explicitly approved remediation workflow adds those capabilities with strong authorization.

## Acceptance criteria

Security tests cover unauthorized access and unsafe inputs.

---

# Phase 21 — Performance & Load Testing

## Objective

Measure how the system behaves under load.

## Test dimensions

- Events per second
- Number of concurrent pipelines
- Consumer count
- Incident rate
- RCA requests
- Agent tool calls

## Measure

- P50 latency
- P95 latency
- P99 latency
- Throughput
- Error rate
- Queue depth
- DB load
- CPU/memory
- Recovery time

## Bottleneck analysis

Identify:

- Database bottleneck
- Redis bottleneck
- Consumer bottleneck
- Detection bottleneck
- LLM latency
- Retrieval latency

## Acceptance criteria

A documented load-test report explains system limits and bottlenecks.

---

# Phase 22 — Final Production Polish

## Objective

Turn the project into a strong portfolio artifact.

## README

Include:

- Problem
- Why it matters
- Architecture
- Event-driven flow
- Detection methodology
- RCA methodology
- AI/agent design
- Reliability
- Observability
- Evaluation results
- Screenshots
- Example incident
- Local setup
- API examples

## Documentation

Include:

- Architecture decision records
- API documentation
- Event contracts
- Failure-mode documentation
- Evaluation methodology
- Trade-offs

## Demo

Prepare a deterministic demo:

```text
1. Start system
2. Run normal pipeline
3. Trigger DB degradation
4. Show metrics moving
5. Show AMBER/RED transition
6. Show incident creation
7. Show heuristic RCA
8. Run AI RCA
9. Show evidence
10. Show dashboard
11. Show trace in Grafana/observability
```

## Resume-ready metrics

Do not invent metrics.

Use measured values from the actual implementation, such as:

- Events processed/sec
- P95 processing latency
- Detection precision/recall
- RCA top-1/top-3 accuracy
- Reduction in investigation steps
- Test coverage
- Recovery time

## Final acceptance criteria

The project should be:

- Reproducible
- Testable
- Observable
- Explainable
- Documented
- Dockerized
- Demonstrable locally
- Strong enough to discuss deeply in an SDE/backend interview
