# TraceNova — Project Specification

## 1. Project Overview

**TraceNova** is an event-driven pipeline reliability and root-cause analysis platform that detects production pipeline degradation, classifies incidents using deterministic RAG (Red/Amber/Green) rules, investigates the likely root cause, and produces an evidence-backed RCA report.

The system is designed as a realistic distributed-systems portfolio project rather than an LLM wrapper.

### Core idea

```text
Pipeline execution/events
        ↓
Event streaming
        ↓
Metrics + execution + logs processing
        ↓
Historical baselines
        ↓
Degradation detection
        ↓
GREEN / AMBER / RED
        ↓
Incident creation
        ↓
Heuristic RCA
        ↓
AI Agentic RCA
        ↓
Evidence-backed RCA report
        ↓
Dashboard + observability
```

The deterministic detection and heuristic RCA path must work even when the LLM is unavailable.

---

## 2. Problem Statement

Production data and application pipelines can become slow, fail intermittently, retry excessively, or degrade because of upstream dependencies, databases, APIs, infrastructure saturation, network problems, or recent deployments.

Today, investigating these incidents often requires engineers to manually inspect:

- Pipeline execution history
- Runtime and failure metrics
- Application logs
- Dependency health
- Database/API latency
- Infrastructure metrics
- Recent deployments
- Historical incidents
- Runbooks and operational documentation

This creates high mean time to detect (MTTD) and mean time to resolve (MTTR).

TraceNova automates the first stages of this workflow:

1. Detect abnormal pipeline behavior.
2. Quantify why it is abnormal.
3. Create an incident with explainable reason codes.
4. Correlate signals across dependencies and recent changes.
5. Rank likely root causes.
6. Use AI only for investigation/reasoning over collected evidence.
7. Produce a traceable RCA report.

---

## 3. Primary Research Question

> Can temporal correlation of pipeline executions, dependency health, infrastructure metrics, logs, retries, and deployments detect degradation early and identify the most likely root cause more accurately than inspecting individual signals independently?

---

## 4. Goals

### Functional goals

- Simulate realistic pipeline executions.
- Stream pipeline events asynchronously.
- Aggregate execution and operational metrics.
- Maintain historical baselines.
- Detect abnormal behavior.
- Classify pipeline health as GREEN, AMBER, or RED.
- Create and manage incidents.
- Perform deterministic heuristic RCA.
- Model pipeline/service dependencies.
- Search historical incidents.
- Support basic and hybrid RAG.
- Provide AI-assisted RCA.
- Support agentic investigation with tools.
- Produce evidence-backed RCA reports.
- Provide an operational dashboard.
- Add metrics, tracing, structured logs, and correlation IDs.
- Test failure modes and recovery behavior.
- Measure detection and RCA quality.

### Engineering goals

The project must demonstrate:

- Event-driven architecture
- Asynchronous processing
- Service boundaries
- Idempotency
- Retries and backoff
- Failure isolation
- Observability
- Explainability
- Database design
- API design
- AI integration with guardrails
- Evaluation methodology
- Security and least privilege
- Performance testing

---

## 5. Non-Goals

The first version will not attempt to:

- Automatically modify production infrastructure.
- Execute arbitrary remediation commands.
- Replace deterministic monitoring with an LLM.
- Depend on a proprietary observability platform.
- Build a full enterprise workflow-management system.
- Support every cloud provider.
- Use Kubernetes before local Docker-based deployment is stable.
- Introduce Kafka merely for resume keywords.
- Build graph RAG before the dependency model is functional.

Automated remediation can be considered as a future extension after detection, RCA, approval, and auditability are mature.

---

## 6. Design Principles

### 6.1 Deterministic before probabilistic

Critical detection decisions must be deterministic and reproducible.

LLMs may explain and investigate; they must not be the only mechanism deciding whether a pipeline is degraded.

### 6.2 Evidence first

Every RCA claim should point to evidence.

The AI must never invent:

- Metrics
- Logs
- Deployments
- Incident history
- Dependency relationships
- Timestamps

If evidence is missing, the system must explicitly say so.

### 6.3 Graceful degradation

If the LLM, vector database, Redis, or another optional subsystem is unavailable:

- Detection must continue where possible.
- Heuristic RCA must remain available.
- Incidents must not disappear.
- The system must record degraded functionality.

### 6.4 Idempotent processing

Duplicate events must not create duplicate metrics or incidents.

Consumers should use event IDs and/or deterministic idempotency keys.

### 6.5 Explainability

Every classification should include:

- Severity
- Reason codes
- Signal values
- Baseline values
- Contribution/weight
- Threshold crossed
- Detection timestamp

### 6.6 Small, explicit services

Each service should have one clear responsibility and a stable API/event contract.

---

## 7. Example Incident

Suppose pipeline `customer_orders_daily` normally completes in 8–12 minutes.

A deployment introduces a database query regression.

Observed sequence:

```text
10:00  Deployment completed
10:02  Pipeline starts
10:06  DB latency increases
10:08  Pipeline retries
10:15  Pipeline duration exceeds baseline
10:17  Pipeline fails
10:18  RED classification
10:18  Incident created
10:18  RCA begins
```

TraceNova should correlate:

- Duration degradation
- Retry increase
- Database latency
- Failure
- Recent deployment

The likely RCA should be:

> Recent deployment is strongly correlated with a database performance regression affecting the pipeline.

The system should show the evidence rather than simply outputting the sentence.

---

# 8. High-Level Architecture

```text
                         ┌─────────────────────┐
                         │ Pipeline Simulator  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Event Stream        │
                         │ Redis Streams       │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
      ┌───────────────┐    ┌────────────────┐    ┌────────────────┐
      │ Execution     │    │ Metrics        │    │ Log/Event      │
      │ Processor     │    │ Processor      │    │ Processor      │
      └───────┬───────┘    └───────┬────────┘    └───────┬────────┘
              │                    │                     │
              └────────────────────┼─────────────────────┘
                                   ▼
                         ┌─────────────────────┐
                         │ Metrics Aggregation  │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Baseline Engine      │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Degradation Engine  │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ RAG Classifier       │
                         │ GREEN/AMBER/RED      │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Incident Service     │
                         └──────────┬──────────┘
                                    ▼
                    ┌───────────────┴────────────────┐
                    ▼                                ▼
          ┌───────────────────┐            ┌────────────────────┐
          │ Heuristic RCA     │            │ AI RCA Agent       │
          └─────────┬─────────┘            └──────────┬─────────┘
                    │                                 │
                    └──────────────┬──────────────────┘
                                   ▼
                         ┌─────────────────────┐
                         │ Evidence Engine      │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ RCA Report           │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Dashboard            │
                         └─────────────────────┘
```

---

# 9. Service Responsibilities

## 9.1 Pipeline Simulator

Generates realistic synthetic pipeline executions.

Responsibilities:

- Start executions.
- Complete executions.
- Generate failures.
- Generate retries.
- Simulate dependency degradation.
- Emit resource metrics.
- Emit logs.
- Simulate deployments.

The simulator must support deterministic scenarios so evaluation tests can reproduce incidents.

---

## 9.2 Event Streaming

Initial implementation:

- Redis Streams

Potential future implementation:

- Kafka, only if scale/load requirements justify the additional complexity.

Event requirements:

- Unique event ID
- Event type
- Pipeline ID
- Timestamp
- Correlation ID
- Schema version
- Payload
- Producer metadata

Example:

```json
{
  "event_id": "evt_123",
  "event_type": "PIPELINE_COMPLETED",
  "schema_version": 1,
  "pipeline_id": "orders_daily",
  "correlation_id": "run_456",
  "timestamp": "2026-01-10T10:15:00Z",
  "payload": {
    "duration_ms": 720000,
    "status": "SUCCESS"
  }
}
```

---

# 10. Event Types

The initial event contract should support:

- `PIPELINE_STARTED`
- `PIPELINE_COMPLETED`
- `PIPELINE_FAILED`
- `PIPELINE_RETRIED`
- `DEPENDENCY_HEALTH_CHANGED`
- `RESOURCE_METRIC_RECORDED`
- `LOG_RECORDED`
- `DEPLOYMENT_STARTED`
- `DEPLOYMENT_COMPLETED`

---

# 11. Metrics

TraceNova should calculate:

### Execution metrics

- Average duration
- Median duration
- P95 duration
- P99 duration
- Success rate
- Failure rate
- Retry rate
- Throughput

### Dependency metrics

- Dependency latency
- Dependency error rate
- Availability
- Timeout rate

### Resource metrics

- CPU utilization
- Memory utilization
- Queue depth
- Network latency

### Windows

Support configurable windows such as:

- 5 minutes
- 15 minutes
- 1 hour
- 24 hours
- 7 days

---

# 12. Baseline Engine

The baseline engine represents normal pipeline behavior.

Baseline examples:

```text
pipeline: orders_daily

p95 duration: 10.2 min
failure rate: 0.8%
retry rate: 1.2%
throughput: 850 runs/hour
```

Current state:

```text
p95 duration: 18.7 min
failure rate: 9.6%
retry rate: 14.3%
throughput: 620 runs/hour
```

The system calculates deviation.

Example:

```text
duration deviation = current / baseline

18.7 / 10.2 = 1.83x
```

Baseline strategies can evolve from:

1. Simple rolling average
2. Rolling median
3. Percentile baseline
4. Time-of-day baseline
5. Day-of-week baseline

Do not over-engineer this in the first implementation.

---

# 13. Degradation Detection

Detection signals:

- Duration deviation
- Failure-rate increase
- Retry-rate increase
- Throughput decrease
- Dependency degradation
- Resource saturation
- Recent deployment correlation

Each signal should produce a structured result.

Example:

```json
{
  "signal": "DURATION_DEGRADATION",
  "current_value": 18.7,
  "baseline_value": 10.2,
  "deviation_ratio": 1.83,
  "severity": "HIGH"
}
```

---

# 14. RAG Classification

RAG means:

**Red / Amber / Green**

It does NOT mean Retrieval Augmented Generation.

### GREEN

Normal behavior.

### AMBER

Moderate degradation requiring investigation.

### RED

Severe degradation, repeated failures, or critical dependency failure.

Classification must be:

- Deterministic
- Configurable
- Explainable
- Testable

Example configuration:

```yaml
thresholds:
  duration:
    amber_ratio: 1.25
    red_ratio: 1.75

  failure_rate:
    amber: 0.05
    red: 0.10

  retry_rate:
    amber: 0.10
    red: 0.20
```

---

# 15. Reason Codes

Initial reason codes:

- `DURATION_DEGRADATION`
- `FAILURE_RATE_INCREASE`
- `RETRY_RATE_INCREASE`
- `DEPENDENCY_DEGRADATION`
- `THROUGHPUT_DROP`
- `RESOURCE_SATURATION`
- `RECENT_DEPLOYMENT`

Reason codes must be stored with the incident.

---

# 16. Incident Service

Incident lifecycle:

```text
OPEN
  ↓
INVESTIGATING
  ↓
RESOLVED
  ↓
CLOSED
```

Incident fields:

- Incident ID
- Pipeline ID
- Severity
- Status
- Created timestamp
- Updated timestamp
- Trigger signals
- Correlation ID
- Current hypothesis
- Root cause
- Confidence
- Evidence IDs

Incident creation should be idempotent.

---

# 17. Heuristic RCA

Heuristic RCA must be implemented before AI RCA.

Initial root-cause categories:

- `DATABASE_BOTTLENECK`
- `UPSTREAM_API_FAILURE`
- `COMPUTE_SATURATION`
- `NETWORK_LATENCY`
- `DEPENDENCY_FAILURE`
- `RESOURCE_EXHAUSTION`
- `RECENT_DEPLOYMENT`
- `RETRY_STORM`

Example:

```text
Signals:
- DB latency +240%
- Pipeline duration +83%
- Retry rate +310%
- Deployment 4 minutes before degradation

Ranking:
1. DATABASE_BOTTLENECK — 0.91
2. RECENT_DEPLOYMENT — 0.74
3. RETRY_STORM — 0.62
```

The score must be explainable.

---

# 18. Dependency Model

Represent relationships between:

- Pipeline
- Service
- Database
- API
- Storage
- Queue

Relationships:

- `depends_on`
- `used_by`
- `upstream_of`
- `downstream_of`

Example:

```text
orders_daily
      │
      ▼
orders_service
      │
      ▼
orders_db
```

If `orders_db` degrades, the system should be able to identify it as an upstream candidate instead of blaming only the pipeline.

---

# 19. Historical Incident Knowledge Base

Store historical incidents containing:

- Incident summary
- Timeline
- Root cause
- Evidence
- Resolution
- Impact
- Affected pipeline
- Tags

Example:

```json
{
  "incident_id": "INC-1002",
  "root_cause": "DATABASE_BOTTLENECK",
  "summary": "Orders pipeline slowed due to database connection saturation.",
  "tags": ["database", "latency", "orders"]
}
```

This becomes the knowledge base for later RAG.

---

# 20. RAG Architecture

TraceNova should eventually support hybrid retrieval:

```text
                 User/Agent query
                       │
                 Query Router
             ┌─────────┼─────────┐
             ▼         ▼         ▼
          Vector      BM25      SQL
             │         │         │
             └─────────┼─────────┘
                       ▼
                   Reranker
                       │
                       ▼
                Evidence Set
```

Later, dependency-aware queries can use graph retrieval.

Do not implement graph RAG before the dependency model is working.

---

# 21. AI RCA Service

The AI service receives:

- Incident
- Detection signals
- Heuristic RCA candidates
- Structured evidence
- Relevant historical incidents
- Pipeline dependencies

The LLM should reason over evidence rather than directly querying arbitrary infrastructure.

Expected output:

```json
{
  "summary": "...",
  "root_cause": "...",
  "confidence": 0.91,
  "supporting_evidence": [],
  "alternative_causes": [],
  "impact": "...",
  "timeline": [],
  "recommendations": [],
  "missing_evidence": [],
  "evidence_conflicts": []
}
```

---

# 22. Agentic RCA

The agentic workflow:

```text
Incident
   ↓
Planner
   ↓
Hypotheses
   ↓
Evidence retrieval
   ↓
Evidence evaluation
   ↓
Additional retrieval if needed
   ↓
Root cause ranking
   ↓
RCA report
```

Available tools:

- `get_pipeline_metrics()`
- `get_execution_history()`
- `get_dependency_health()`
- `search_logs()`
- `get_recent_deployments()`
- `search_similar_incidents()`
- `get_pipeline_dependencies()`
- `calculate_behavioral_risk()` is NOT part of TraceNova and should not be introduced from the FraudShield project.

The agent should stop when evidence is sufficient rather than repeatedly calling tools.

---

# 23. Evidence Model

Every evidence item should contain:

```text
evidence_id
type
source
timestamp
claim
confidence
reference
```

Evidence types:

- Metric
- Log
- Event
- Deployment
- Dependency
- Historical incident
- Document

Example:

```json
{
  "evidence_id": "ev_100",
  "type": "METRIC",
  "source": "metrics-service",
  "timestamp": "2026-01-10T10:06:00Z",
  "claim": "Database latency increased from 120ms to 420ms.",
  "confidence": 0.99
}
```

---

# 24. Evidence Rules

The system should distinguish:

### Direct evidence

Observed metric/event/log.

### Correlated evidence

Strong temporal relationship between independent signals.

### Historical evidence

A similar previous incident.

### Inferred evidence

A reasoned conclusion that is not directly observed.

The RCA must not present inferred evidence as direct evidence.

---

# 25. Observability

Use:

- OpenTelemetry
- Prometheus
- Grafana

Track:

- API latency
- Event processing latency
- Queue depth
- Consumer lag
- Incident creation latency
- RCA latency
- LLM latency
- LLM error rate
- Database latency
- Retry count
- Dead-letter events

---

# 26. Correlation IDs

A correlation ID should follow an incident through:

```text
Pipeline run
 → Event
 → Consumer
 → Detection
 → Incident
 → RCA
 → Agent
 → Tool calls
 → Final report
```

This is important for debugging distributed workflows.

---

# 27. Reliability

The system should implement:

- Retries
- Exponential backoff
- Timeouts
- Dead-letter queue
- Idempotency
- Circuit breaker where appropriate
- Graceful fallback

Failure scenarios to test:

- Redis unavailable
- Database unavailable
- Duplicate event
- Malformed event
- Consumer crash
- LLM timeout
- LLM rate limit
- Vector store unavailable
- Partial dependency failure

---

# 28. Security

Minimum requirements:

- Read-only database access for analytical queries
- Parameterized SQL
- Input validation
- Authentication for internal APIs where appropriate
- Least-privilege service credentials
- Secret management through environment variables
- No secrets in logs
- Redaction of sensitive values
- LLM prompt/input sanitization
- Audit trail for AI-generated conclusions

The AI must never be allowed to execute arbitrary destructive SQL or infrastructure commands.

---

# 29. Technology Stack

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy

### Storage

- PostgreSQL
- Redis

### Messaging

- Redis Streams initially
- Kafka only if justified later

### AI

- LLM provider
- Embeddings
- LangGraph or equivalent agent orchestration

### Retrieval

- PostgreSQL / pgvector or vector store
- BM25
- Optional reranker
- Neo4j later for graph retrieval

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui

### Observability

- OpenTelemetry
- Prometheus
- Grafana

### Deployment

- Docker
- Docker Compose

---

# 30. Suggested Repository Structure

```text
tracenova/
├── apps/
│   ├── simulator/
│   ├── incident-service/
│   ├── detection-service/
│   ├── rca-service/
│   ├── ai-rca-service/
│   └── dashboard/
│
├── services/
│   ├── event_processor/
│   ├── metrics/
│   ├── baseline/
│   ├── dependency/
│   ├── retrieval/
│   └── evidence/
│
├── packages/
│   ├── event-contracts/
│   ├── config/
│   ├── logging/
│   └── common/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── reliability/
│   └── evaluation/
│
├── docs/
│   ├── PROJECT_SPEC.md
│   └── IMPLEMENTATION_PLAN.md
│
├── docker-compose.yml
├── .env.example
├── README.md
└── Makefile
```

The exact structure may evolve, but boundaries must remain explicit.

---

# 31. Evaluation

TraceNova should measure:

## Detection

- Precision
- Recall
- F1
- False-positive rate
- Detection delay

## RCA

- Top-1 root-cause accuracy
- Top-3 root-cause accuracy
- Evidence coverage
- Confidence calibration
- Hallucination rate

## RAG

- Retrieval recall
- Context precision
- Answer relevance
- Faithfulness
- Citation/evidence accuracy

## Agent

- Tool-selection accuracy
- Task completion rate
- Evidence coverage
- Number of unnecessary tool calls

## System

- Throughput
- P95 event processing latency
- P95 RCA latency
- Recovery time
- Queue backlog
- Error rate

---

# 32. Synthetic Scenarios

The simulator must eventually support:

### Scenario A — Database degradation

Database latency rises and pipeline duration increases.

Expected RCA:

`DATABASE_BOTTLENECK`

### Scenario B — Upstream API degradation

API error rate and latency increase.

Expected RCA:

`UPSTREAM_API_FAILURE`

### Scenario C — Compute saturation

CPU/memory saturation causes duration increase and failures.

Expected RCA:

`COMPUTE_SATURATION` or `RESOURCE_EXHAUSTION`

### Scenario D — Bad deployment

Deployment occurs shortly before a degradation.

Expected RCA:

`RECENT_DEPLOYMENT`, potentially combined with another direct cause.

### Scenario E — Cascading failure

An upstream service fails and downstream pipelines degrade.

Expected behavior:

Identify upstream service as the likely root cause.

---

# 33. Definition of Done

TraceNova is considered portfolio-ready when:

- Events are generated and consumed asynchronously.
- Duplicate events are handled safely.
- Metrics and baselines are persisted.
- Degradation is detected deterministically.
- GREEN/AMBER/RED classification is explainable.
- Incidents are created idempotently.
- Heuristic RCA works without an LLM.
- Dependencies are modeled.
- Historical incidents are searchable.
- Hybrid retrieval works.
- AI RCA produces evidence-backed reports.
- Agentic investigation uses controlled tools.
- LLM failures do not break detection.
- OpenTelemetry traces cross service boundaries.
- Prometheus/Grafana expose system health.
- Reliability tests cover key failures.
- Evaluation datasets and metrics exist.
- Security controls are implemented.
- Load testing has measurable results.
- Documentation explains architecture and trade-offs.
- Docker Compose can start the complete local system.
