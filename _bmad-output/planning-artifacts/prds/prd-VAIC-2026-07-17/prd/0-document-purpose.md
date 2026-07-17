# 0. Document Purpose

This PRD specifies **VAIC**, a multi-tenant enterprise AI-agent platform that lets a bank configure specialist AI agents, coordinate them through a workflow orchestrator, generate working mini-apps with auto-provisioned backends, and trigger runs on schedule or event. It is written for: (a) the **product manager** (Nguyen) and **mentor** reviewing scope and rubric alignment; (b) the **build team** who need crisp feature-level requirements with stable IDs; (c) **downstream BMad workflows** — UX, Architecture, Epics & Stories — which consume FRs and UJs verbatim.

The PRD is **platform-capability-first**, not scenario-first: it specifies what the platform must be able to do. A demo at the close of the 2-day build is one configured instance of the platform, not its scope.

The document is structured as: Vision → Target User → Glossary → Features (the platform's six capability groups) → Non-Goals → MVP Scope (demo-scoped platform) → Success Metrics (mapped to the SHB rubric) → Constraints, Guardrails & NFRs → Integration & Dependencies → Risks → Stakeholders → Open Questions → Assumptions Index. Domain nouns are defined once in the Glossary and used verbatim everywhere else. Inferences are tagged inline `[ASSUMPTION: ...]` and indexed in §13. Deferred items are tagged `[NON-GOAL for MVP]` inline.

Source intake: the product brief v2 (`_bmad-output/planning-artifacts/briefs/brief-VAIC-2026-07-17/brief.md`) and the SHB Hack CX Together 2026 problem statement (verbatim, see §8.3). The brief's tech-stack choices (FastAPI, PostgreSQL with JSONB, ReactJS, MCP) are treated as **technical constraints** the team has decided, not feature-level requirements.
