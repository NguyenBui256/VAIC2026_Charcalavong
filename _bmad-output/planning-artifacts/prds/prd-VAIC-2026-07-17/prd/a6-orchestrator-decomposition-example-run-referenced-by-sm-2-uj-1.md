# A6. Orchestrator Decomposition — Example Run (referenced by SM-2, UJ-1)

Request: *"Pre-screen business loan application #LOAN-2026-0143 for Acme Trading JSC."*

Orchestrator decomposition (illustrative — actual decomposition is dynamic per request, per FR-8):

1. Task → Credit Analyst Agent
   - `task`: "Compute financial ratios and verdict against lending policy for Acme Trading."
   - `expected`: ["retrieve policy clauses", "compute ratios", "compare to thresholds", "return verdict"]
   - `criteria`: { confidence_floor: 0.7, must_cite_kb: true, must_use_tool: "financial-ratio-calculator" }

2. Task → Compliance Analyst Agent
   - `task`: "Run KYC/AML screen on Acme Trading principals."
   - `expected`: ["screen against sanctions list", "retrieve KYC/AML circular", "return flags"]
   - `criteria`: { confidence_floor: 0.85, must_cite_kb: true, must_use_tool: "sanctions-check" }

3. Task → Operations Analyst Agent
   - `task`: "Verify document checklist completeness for the loan application."
   - `expected`: ["read checklist", "match against provided documents", "return gaps"]
   - `criteria`: { confidence_floor: 0.9, must_use_tool: "doc-checklist-verifier" }

Aggregation → Mini-App emission (FR-12) → "Business Loan Pre-Screen Case" Mini-App provisioned (FR-13–FR-15) with one row carrying the consolidated decision.

Closed-loop demo (SM-6): a User edits a field in the Mini-App → App Event `row.updated` fires → Event Trigger kicks a follow-on "Post-Filing Workflow."
