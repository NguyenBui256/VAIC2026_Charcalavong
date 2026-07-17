# A8. Bootstrapping the Demo Tenant (referenced by FR-28)

A script (`scripts/bootstrap_demo_tenant.py` or equivalent) provisions:

- 1 Tenant ("SHB Demo Bank")
- 3 Departments (Credit, Legal/Compliance, Operations)
- 3 Users (one per role: builder, manager, operator)
- 3 Specialist Agents (Credit Analyst, Compliance Analyst, Operations Analyst), each with:
  - A KB seeded from sample policy PDFs
  - 1–2 Tools registered (per §A6)
  - A Model selected at config time
- 1 Workflow ("Business Loan Pre-Screen") with the description that triggers the §A6 decomposition
- 1 pre-provisioned Mini-App ("Business Loan Pre-Screen Case") for cold-start safety (R-5)

The script is idempotent and runs in < 60 s on demo hardware.

---

*Addendum v1. Mechanism and technical-how depth referenced from the PRD. Architecture work may move, refine, or replace any of these; the PRD's capability-level FRs are the contract.*
