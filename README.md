# AEO Orchestrator

Autonomous Answer Engine Optimization Agency - a multi-agent system that thinks strategically, understands your business deeply, and takes action to improve your presence in AI answer engines.

## Phase 1 Implementation

This is the Phase 1 implementation which includes:

### Agents (Tier 0: Intelligence Bureau)
- **The Cartographer** - Client Intelligence Specialist
- **The Auditor** - AEO Performance Monitor

### Core Systems
- Calibration system with industry benchmarks
- AI engine query system (ChatGPT, Claude, Perplexity, Gemini)
- Client knowledge base
- LangGraph workflows for onboarding and monitoring

### API Endpoints
- Client management and onboarding
- Monitoring execution
- Performance reports
- Alerts

## Setup

1. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Setup PostgreSQL database and run migrations:
   ```bash
   python -m db.migrations create_tables
   ```

4. Run the API server:
   ```bash
   python main.py
   ```

## Usage

### Onboard a New Client

```bash
curl -X POST http://localhost:8000/api/clients/onboard \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "domain": "acme.com"}'
```

### Run Monitoring

```bash
curl -X POST http://localhost:8000/api/monitoring/{client_id}/run
```

### Get Performance Report

```bash
curl http://localhost:8000/api/monitoring/{client_id}/report
```

## Architecture

```
agents/
├── intelligence/          # Tier 0: Always-on intelligence
│   ├── cartographer.py    # Client intelligence
│   └── auditor.py         # Performance monitoring
├── strategic/             # Tier 1: Strategy (Phase 2)
└── execution/             # Tier 2: Execution (Phase 3-4)

calibration/               # Benchmarks and scoring
engine/                    # AI engine queries
knowledge/                 # Client knowledge base
workflows/                 # LangGraph orchestration
db/                        # Database models and queries
api/                       # FastAPI endpoints
```

## Next Phases

- **Phase 2**: Strategic Layer (Scout, Librarian, Strategist, Architect)
- **Phase 3**: Content Execution (Writer, Optimizer)
- **Phase 4**: Full Agency (Builder, Engineer, Analyst, Reporter)
