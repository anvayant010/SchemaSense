<div align="center">

# ⬡ SchemaSense

**Intelligent database schema analyzer - find the right database for your schema in seconds**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-schemasense--tool.vercel.app-7c6aff?style=for-the-badge&logo=vercel)](https://schemasense-tool.vercel.app)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61dafb?style=for-the-badge&logo=react)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker)](https://docker.com)



</div>

---

## What is SchemaSense?

SchemaSense is a full-stack SaaS tool that analyzes database schemas and scores them against **12 major databases** - giving developers instant compatibility reports, AI-powered recommendations, migration risk assessments, and live ER diagrams.

Upload a `.sql`, `.csv`, or `.json` schema file and get:

- **Compatibility scores** across PostgreSQL, MySQL, MongoDB, SQLite, Oracle, CockroachDB, Cassandra, DynamoDB, BigQuery, Redshift, MariaDB, SQL Server
- **AI-powered explanation** of which database fits best and why (Gemini AI)
- **Column-level migration warnings** - specific fields that will break and why
- **ER diagram** rendered live in the browser + copyable Mermaid code
- **Migration plan** with table creation order and constraint steps
- **Schema quality score** - missing PKs, FK indexes, weak tables
- **Saved analysis history** - sign in to save, reopen, and delete past analyses

---

## Live Demo

**→ [schemasense-tool.vercel.app](https://schemasense-tool.vercel.app)**

Try it instantly with the built-in **E-Commerce sample schema** - no file upload needed.

---

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | REST API framework |
| **Python 3.11** | Core language |
| **sqlglot** | SQL schema parsing |
| **NetworkX** | Schema graph analysis |
| **Pydantic v2** | Data validation |
| **Gemini AI** | AI-powered explanations |
| **Celery + Redis** | Async task processing |
| **Supabase (PostgreSQL)** | Analysis persistence |
| **Clerk** | Authentication (Google + GitHub) |
| **PyJWT** | JWT token verification |
| **Docker** | Containerization |
| **Render** | Backend deployment |

### Frontend
| Technology | Purpose |
|---|---|
| **React 18** | UI framework |
| **Vite** | Build tool |
| **React Router v6** | Client-side routing |
| **Clerk React** | Auth UI components |
| **Mermaid.js** | ER diagram rendering |
| **Space Grotesk** | Display typography |
| **DM Mono** | Monospace typography |
| **Vercel** | Frontend deployment |

---

## Features

### Core Analysis Engine
- Custom rule-based scoring engine across 12 databases
- Type compatibility checking with column-level granularity
- Foreign key relationship analysis and graph-based dependency ordering
- Schema quality analysis - missing PKs, unindexed FKs, weak tables
- Migration risk scoring (Low / Medium / High)
- ER diagram generation in Mermaid.js syntax

### Web Application
- Drag-and-drop schema upload (`.sql` / `.csv` / `.json`)
- One-click sample schema analysis (E-Commerce, 5 tables)
- Live ER diagram with Diagram and Mermaid code tabs
- Dark-themed UI with dot grid background
- Fully responsive design

### Auth & Persistence (Phase 3)
- Sign in with Google or GitHub via Clerk
- Save analyses to Supabase with one click
- Dashboard with full analysis history
- Reopen any saved analysis with preserved results
- Delete saved analyses

---

## Project Structure

```
SchemaSense/
├── api/                    # FastAPI backend
│   ├── main.py             # App setup, CORS, startup
│   ├── routes.py           # All API endpoints
│   ├── worker.py           # Analysis pipeline + Celery
│   ├── auth.py             # Clerk JWT verification
│   ├── database.py         # Supabase operations
│   ├── ai_explainer.py     # Gemini AI integration
│   └── config.py           # Settings from .env
├── core/                   # Analysis engine
│   ├── scorer.py           # 12-database scoring engine
│   ├── schema_parser.py    # SQL/CSV/JSON parser
│   ├── schema_quality.py   # Quality analysis
│   ├── schema_complexity.py
│   ├── migration_risk.py
│   ├── migration_planner.py
│   ├── schema_graph.py     # NetworkX graph analysis
│   ├── er_generator.py     # Mermaid ER diagram generator
│   └── models.py           # Pydantic data models
├── data/
│   └── db_features.json    # Database feature definitions
├── frontend/               # React + Vite frontend
│   ├── src/
│   │   ├── pages/          # Upload, Results, Dashboard, SignIn, SignUp
│   │   ├── components/     # DBScoreCard, ERDiagram, SchemaOverview...
│   │   ├── styles/         # Global CSS + design tokens
│   │   └── api.js          # Centralized API config
│   └── package.json
├── tests/                  # pytest test suite
├── Dockerfile
├── docker-compose.yml
├── render.yaml
└── requirements.txt
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/analyze` | Analyze a schema file |
| `GET` | `/api/v1/databases` | List supported databases |
| `POST` | `/api/v1/analyses/save` | Save analysis (auth required) |
| `GET` | `/api/v1/analyses/history` | Get user history (auth required) |
| `GET` | `/api/v1/analyses/{id}` | Get single analysis (auth required) |
| `DELETE` | `/api/v1/analyses/{id}` | Delete analysis (auth required) |

Full interactive docs at: `https://schemasense-api.onrender.com/docs`

---

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker Desktop (optional)

### With Docker (recommended)

```bash
# Clone the repo
git clone https://github.com/yourusername/SchemaSense.git
cd SchemaSense

# Set up environment
cp .env.example .env
# Edit .env with your keys (Gemini, Clerk, Supabase)

# Start everything
docker compose up --build
```

API runs at `http://localhost:8000`

### Manual Setup

```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Gemini AI (google.com/aistudio)
GEMINI_API_KEY=your_key_here

# Clerk Auth (clerk.com)
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...

# Supabase (supabase.com)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# App
SECRET_KEY=random_secret_string
ENVIRONMENT=development
REDIS_URL=redis://localhost:6379/0
```

### Supabase Table Setup

Run this SQL in your Supabase SQL Editor:

```sql
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_format TEXT NOT NULL,
    top_db TEXT,
    top_score DECIMAL(5,2),
    table_count INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    result JSONB NOT NULL
);

CREATE INDEX idx_analyses_user ON analyses(user_id, created_at DESC);
```

---

## Supported Databases

| Database | Type | Notes |
|---|---|---|
| PostgreSQL | Relational | Best overall for complex schemas |
| MySQL | Relational | Great for web applications |
| MariaDB | Relational | MySQL-compatible, open source |
| SQL Server | Relational | Enterprise Windows environments |
| Oracle | Relational | Enterprise, advanced types |
| CockroachDB | Distributed SQL | PostgreSQL-compatible, scalable |
| SQLite | Embedded | Simple apps, no server needed |
| MongoDB | Document | Flexible schemas, no FKs |
| Cassandra | Wide Column | High write throughput |
| DynamoDB | Key-Value | AWS native, serverless |
| BigQuery | OLAP | Analytics and data warehousing |
| Redshift | OLAP | AWS analytics |

---
