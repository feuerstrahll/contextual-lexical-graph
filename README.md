# Contextual Lexical Graph

First vertical slice of the project from `Engineering_Backlog.xlsx`: `API-101`.

## Local Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest -q
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/health` returns `{"status":"ok"}`.

Sense search: `GET http://localhost:8000/api/search?q=improve` returns a list of
`{senseId, lemma, pos, gloss}` sorted by `frequency_rank`. PostgreSQL uses full-text search
and `pg_trgm` for typo tolerance.

Sense graph: `GET http://localhost:8000/api/senses/{senseId}/graph?depth=1` returns
`center`, `nodes`, `edges`, and `depth`. Supports `depth=0..2`, repeatable `relation_types`,
and `linguistic`/`personal` modes; results contain only published edges. Directed edges are
traversed forward; undirected edges in both directions.

## Suitability Endpoint
Suitability: `GET http://localhost:8000/api/edges/{edgeId}/suitability?context_sentence=...`
returns `score`, measurable `dimensions`, `matchedRule`, `confidence`, and `reason`.
Non-applicable dimensions remain `null`; if the contextual rule is not found, score is also
equal to `null`, without substituting guesses.

## PostgreSQL and Migrations

```powershell
docker compose up -d postgres
alembic upgrade head
```

To run the full API and database:

```powershell
docker compose up --build
```

Domain model reflects the architecture document: senses/concepts/edges, context rules,
exercises, attempts, and mastery. Published content will be filtered by
`curator_status='published'` in subsequent API slices.
