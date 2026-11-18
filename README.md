# NYC 311 Analytics & AI Chatbot System

An automated end-to-end analytics engineering pipeline, cloud data warehouse, Power BI reporting suite, and guardrailed natural language AI chatbot built on NYC 311 service request data from NYC Open Data.

## Architecture

```
       [NYC Open Data Socrata API]
                    │
                    ▼
       [Local / CI Ingestion Script]
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
 [raw_complaints.json.gz] [DuckDB In-Memory ETL]
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       [clean_complaints]            [quarantine_complaints]
       (Valid records)               (Broken dates/ZIPs/missing keys)
               │                               │
               └───────────────┬───────────────┘
                               ▼
               [Supabase Cloud Data Warehouse]
                (Public Schema / PostgreSQL)
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 [Power BI Desktop Dashboard]          [Streamlit Chatbot UI]
 - Ticket Ops & SLA Delays              - Natural language questions
 - Pipeline Health & Quarantine         - Gemini 2.5 Flash Text-to-SQL
                                        - AST/Regex Read-Only Guardrail
                                        - Read-Only Postgres Execution
```

## Directory Structure

```
nyc-311-ai-analysis/
├── .github/
│   └── workflows/              # GitHub Actions CI/CD workflows
├── data/
│   ├── raw/                    # Immutable raw API extractions (*.json.gz)
│   ├── clean/                  # Valid clean datasets (*.parquet)
│   └── quarantine/             # Rejected / quarantined datasets (*.parquet)
├── powerbi/                    # Power BI templates, DAX specifications & assets
├── src/
│   ├── etl/                    # Extraction & DuckDB transformation logic
│   ├── db/                     # Supabase schema DDL & loader scripts
│   └── chatbot/                # Streamlit UI, Gemini agent & AST guardrails
├── tests/                      # Unit & guardrail test suites
├── .env.example                # Template for environment variables
├── .gitignore                  # Git ignore rules
├── GEMINI.md                   # Project architecture & HITL guidelines
├── README.md                   # Project overview & documentation
└── requirements.txt            # Python dependencies
```

## Mandatory 4-Gate HITL Analytics Workflow
1. **Gate 1**: Read-Only Profiling & Anomaly Audit (`duckdb`)
2. **Gate 2**: Transformation, Quarantine & Mathematical Reconciliation (`duckdb` + `excel`)
3. **Gate 3**: Star Schema Design & Verified Warehouse Load (`supabase`)
4. **Gate 4**: Semantic Layer & DAX Engineering (`powerbi` + `github`)
