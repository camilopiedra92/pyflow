# PyFlow v2 — Headless Platform Design

## Overview

Evolution from single-process workflow engine to production-grade headless platform.

## Gap Analysis (v1 → v2)

1. No execution persistence (in-memory only)
2. Synchronous trigger-to-execution coupling
3. No auth/multi-tenancy framework
4. No secret management
5. No plugin discovery (manual register)
6. No observability stack (metrics/tracing)
7. No Python SDK for programmatic access
8. No workflow CRUD API
9. Incomplete trigger system
10. Missing SSRF on AlertNode, path traversal on StorageNode

## Platform Architecture (10 Areas)

### 1. Headless API-First
- REST `/api/v1/` with full CRUD, async execution, versioned paths
- WebSocket + SSE for real-time execution streaming
- JSON/YAML content negotiation
- RFC 7807 error responses

### 2. Execution Engine
- ExecutionJob decouples submission from execution
- Redis Streams job queue, worker pool, horizontal scaling
- Progress callbacks with NodeEvent streaming
- In-process mode preserved for dev (no Redis required)

### 3. State Management
- Protocol-based WorkflowStore/RunStore abstractions
- SQLite (dev) → PostgreSQL (prod) via SQLAlchemy
- Full run history with per-node execution records
- Alembic migrations

### 4. Event System
- EventBus protocol: in-process + Redis pub/sub
- 15 event types (workflow, run, node, trigger lifecycle)
- Webhook delivery with HMAC-SHA256 signing + retry

### 5. Plugin Architecture
- BaseNodeV2 with metadata (display_name, category, config_schema)
- Pydantic config schemas → auto JSON Schema
- Python entry_points for discovery
- Separate pyflow-sdk package

### 6. Multi-Tenancy
- Row-level isolation with tenant_id
- Scoped API keys with bcrypt hashing
- Redis sliding window rate limiting
- Plan-based quotas (free/pro/enterprise)

### 7. Observability
- OpenTelemetry span-per-node tracing
- Prometheus metrics (runs_total, duration, queue_depth)
- Structured audit log in database
- run_id as correlation ID

### 8. Workflow Versioning
- Draft → Published → Archived lifecycle
- Immutable version snapshots, rollback
- Diff API, triggers execute latest published

### 9. Scheduler
- Leader-elected single scheduler (PG advisory locks)
- Persistent job store with deduplication
- Timezone-aware cron

### 10. Security
- Scoped API keys, bcrypt-hashed
- RBAC: viewer/editor/admin/owner
- Encrypted secrets store with {{ secrets.KEY }}
- OAuth2/JWT optional overlay (v2.1)

## Developer Experience

### Package Ecosystem
- `pyflow` — core engine + CLI + server (enhanced)
- `pyflow-client` — standalone SDK for API consumers
- `pyflow-sdk` — lightweight SDK for plugin authors

### Python DSL (Workflow-as-Code)
- Decorator-based: @workflow, @node
- Fluent builder: Workflow("name").node(Node(...))
- Round-trip: Python ↔ YAML conversion

### Enhanced CLI
- `pyflow run --dry-run --mock --stop-at --format json`
- `pyflow nodes` / `pyflow inspect` / `pyflow diff`
- `pyflow dev` (auto-reload) / `pyflow remote` (API client)
- `pyflow secrets` / `pyflow init` / `pyflow new`

### Testing Framework
- WorkflowTestRunner with MockNode and fixtures
- MockContext for unit testing nodes
- dry_run() for execution plan analysis
- pytest plugin with auto-injected fixtures

### Integration Patterns
- Library mode (no server, direct engine)
- Sidecar mode (embedded FastAPI sub-app)
- Remote client mode (SDK to standalone server)
- Saga pattern for microservice orchestration

## Phased Roadmap

### Phase 1 (v1.1) — Non-Breaking Enhancements
- --format json, --dry-run, pyflow nodes, pyflow inspect
- pyflow.toml + .env config, --verbose logging

### Phase 2 (v1.2) — API v1 Alongside Legacy
- /api/v1/ routes + RFC 7807 errors + pagination
- Workflow CRUD API, async execution endpoint

### Phase 3 (v2.0-alpha) — DSL + SDK
- pyflow-client, pyflow-sdk packages
- pyflow.dsl module, pyflow.testing module

### Phase 4 (v2.0) — Full Platform
- Database storage, Redis queue, webhook management
- Secrets, BaseNodeV2, plugin discovery

### Phase 5 (v2.1) — Enterprise
- OAuth2/JWT, RBAC, audit compliance, Vault, K8s operator

## Backward Compatibility
All existing YAML workflows, CLI commands, BaseNode implementations, and single-process mode continue unchanged. Every v2 feature is opt-in.
