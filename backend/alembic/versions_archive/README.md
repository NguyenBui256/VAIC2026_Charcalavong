# Archived migrations (pre-baseline)

These 32 migrations were **squashed into a single baseline** on 2026-07-19:
`alembic/versions/baseline_0001_squashed_schema.py` (+ `baseline_0001_schema.sql`).

## Why squash

The pre-`rebuild` chain was broken for a clean deploy:

- **Duplicate revision id `c1d2e3f4a5b6`** — two different migrations
  (`add_kb_documents_content` and `widen_workflow_file_content_type`) shared the
  same id, so Alembic silently dropped one. A fresh `upgrade` skipped the
  `kb_documents.content` column.
- **Multiple heads** — `b8c9d0e1f2a3` (persistent chat) was never merged, so
  `alembic upgrade head` failed with "multiple heads" and chat tables were
  never created on a fresh DB.

## How the baseline was built (reproducible)

1. Renamed the duplicate id (`add_kb_documents_content` → `a11kbcontent01`) so
   the full chain applies cleanly.
2. Ran the **entire repaired chain** onto a throwaway DB (`alembic upgrade heads`)
   → the true, complete intended schema (tables + RLS policies + GRANTs +
   `users_set_updated_at` function/trigger + the previously-dropped changes).
3. `pg_dump --schema-only --no-owner` of that DB → `baseline_0001_schema.sql`
   (psql `\restrict`/`\unrestrict` meta-commands stripped).
4. Verified: a fresh DB built from `baseline_0001` alone is **object-for-object
   identical** to the chain-built DB (39 tables, 477 columns, 523 constraints,
   38 RLS policies, 105 indexes, 81 FKs, 131 grants).

The existing dev DB was brought up to the full schema, then
`alembic stamp baseline_0001 --purge`.

## Production deploy

```bash
cd backend
uv run alembic upgrade head          # builds the full schema from baseline_0001
# then seed data (NOT part of migrations):
uv run python -m scripts.bootstrap_auto_loan_demo   # or your prod seed
```

Notes:
- The `vaic_app` app role is created by the baseline (idempotent) because a
  single-database `pg_dump` does not emit `CREATE ROLE`.
- Migrations carry **schema only**. Demo/business data comes from the
  `scripts/bootstrap_*.py` seeders.

These archived files are kept for history/reference only. Alembic does **not**
scan this directory (it only reads `alembic/versions/`). Do not add new
migrations here; branch from `baseline_0001` in `versions/` instead.
