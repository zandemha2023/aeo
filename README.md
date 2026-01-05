# AEO Orchestrator

Autonomous Answer Engine Optimization Agency - a multi-agent system that thinks strategically, understands your business deeply, and takes action to improve your presence in AI answer engines.

## Current Implementation (Phase 1 + Phase 2)

### Agents

**Tier 0: Intelligence Bureau**
- **The Cartographer** - Client Intelligence Specialist (crawls websites, builds client profiles)
- **The Auditor** - AEO Performance Monitor (analyzes mentions, calculates health scores)
- **The Scout** - Competitive Intelligence Specialist (monitors competitors, finds vulnerabilities)
- **The Librarian** - Content & Authority Analyst (catalogs content, finds gaps)

**Tier 1: Strategic Command**
- **The Strategist** - Chief AEO Strategist (synthesizes intelligence, creates priorities)
- **The Architect** - Content & Campaign Architect (designs execution plans, content blueprints)

### Core Systems
- Calibration system with industry benchmarks
- AI engine query system (ChatGPT, Claude, Perplexity, Gemini)
- Client knowledge base
- LangGraph workflows for onboarding, monitoring, and strategy

### API Endpoints
- Client management and onboarding
- Monitoring execution
- Performance reports
- Strategy generation
- Execution plans
- Content calendar

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

### Generate Strategy

```bash
curl -X POST http://localhost:8000/api/strategy/{client_id}/generate
```

### Get Strategy Summary

```bash
curl http://localhost:8000/api/strategy/{client_id}
```

### Get Execution Plans

```bash
curl http://localhost:8000/api/strategy/{client_id}/execution-plans
```

### Get Content Calendar

```bash
curl http://localhost:8000/api/strategy/{client_id}/content-calendar
```

## Architecture

```
agents/
├── intelligence/          # Tier 0: Always-on intelligence
│   ├── cartographer.py    # Client intelligence
│   ├── auditor.py         # Performance monitoring
│   ├── scout.py           # Competitive intelligence
│   └── librarian.py       # Content analysis
├── strategic/             # Tier 1: Strategic command
│   ├── strategist.py      # Strategy synthesis
│   └── architect.py       # Execution planning
└── execution/             # Tier 2: Execution (Phase 3-4)

calibration/               # Benchmarks and scoring
engine/                    # AI engine queries
knowledge/                 # Client knowledge base
workflows/                 # LangGraph orchestration
db/                        # Database models and queries
api/                       # FastAPI endpoints
```

## Strategy Workflow

The strategy workflow runs all intelligence agents in parallel, then synthesizes:

```
┌─────────────────────────────────────────────────────────────┐
│  PARALLEL INTELLIGENCE GATHERING                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐│
│  │CARTOGRAPH.│  │  SCOUT    │  │ LIBRARIAN │  │  AUDITOR  ││
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘│
└────────┼──────────────┼──────────────┼──────────────┼───────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    THE STRATEGIST    │
                    │  (synthesizes all    │
                    │   intelligence)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    THE ARCHITECT     │
                    │  (creates execution  │
                    │   plans & blueprints)│
                    └─────────────────────┘
```

## Next Phases

- **Phase 3**: Content Execution (Writer, Optimizer, quality gates)
- **Phase 4**: Full Agency (Builder, Engineer, Analyst, Reporter)
