# Specific Corrections Needed

## Correction 1: TypeScript version is stale

**Spine text (line 225):**
```
| TypeScript | 5.6+ | Type safety |
```

**Should read:**
```
| TypeScript | 7.x | Type safety |
```

**Reason:** TypeScript 7.0.2 is the current stable on npm (published ~July 9, 2026). TS 5.6 was released September 2024 — nearly two years ago. The "5.6+" range misleadingly suggests anything in the 5.x line is current when the language has moved to 7.x.

## Correction 2: Vite version is one major behind

**Spine text (line 224):**
```
| Vite | 7 | Bundler/dev server |
```

**Should read:**
```
| Vite | 8 | Bundler/dev server |
```

**Reason:** Vite 8.0 was released March 2026; Vite 8.1.x is the current stable. Vite 7 shipped June 2025. Vitest 4.1 already targets Vite 8. New projects should start on Vite 8.

## Correction 3: Python version is in security-only support

**Spine text (line 210):**
```
| Python | 3.12 | Backend language |
```

**Should read:**
```
| Python | 3.13 | Backend language |
```

**Reason:** Python 3.12 entered security-only support (no bug fixes). Python 3.13 is in active bugfix support and has the best library compatibility for greenfield projects in 2026. Python 3.14 is also stable but some libraries may still be catching up. 3.13 is the conservative boring choice.

## Correction 4: PostgreSQL should target 18 for greenfield

**Spine text (line 215):**
```
| PostgreSQL | 16 | Primary DB, RLS |
```

**Should read:**
```
| PostgreSQL | 18 | Primary DB, RLS |
```

**Reason:** PostgreSQL 18.4 is the current stable. PG 16 is still supported but two major versions behind. For a greenfield build with no legacy constraints, PG 18 is the boring choice. RLS behavior is identical. All named dependencies (pgvector, SQLAlchemy, Alembic) support PG 18.

## Correction 5: arq minimum version should be 0.28+

**Spine text (line 218):**
```
| arq | 0.26+ | Async jobs + cron |
```

**Should read:**
```
| arq | 0.28+ | Async jobs + cron |
```

**Reason:** arq 0.28.0 (April 2026) is the current stable. While "0.26+" technically includes 0.28.0 via semver, a builder might pin 0.26.x and encounter bugs fixed in 0.28. The minimum should reflect the version the architecture was verified against.

## Correction 6: Redis version should be more specific

**Spine text (line 217):**
```
| Redis | 7 | arq broker only |
```

**Should read:**
```
| Redis | 7.4+ | arq broker only |
```

**Reason:** Redis 7.2 reached EOL on 2026-02-28. Bare "7" is ambiguous — a builder might use 7.0 or 7.2. The minimum supported version in the 7.x line is 7.4.x. Alternatively, Redis 8.8 is the current stable major.

## Correction 7: pgvector minimum version

**Spine text (line 216):**
```
| pgvector | 0.7+ | Only if FR-2 reconciliation yields VAIC-side retrieval; skip otherwise |
```

**Should read:**
```
| pgvector | 0.8+ | Only if FR-2 reconciliation yields VAIC-side retrieval; skip otherwise |
```

**Reason:** pgvector 0.8.1 is the current version. 0.7.x is outdated. If included at all, the minimum should be 0.8+.

---
