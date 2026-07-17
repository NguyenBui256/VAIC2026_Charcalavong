# A1. Task Schema (referenced by FR-8)

The **Task Schema** is the JSON/YAML contract every Task emitted by the Orchestrator conforms to.

```yaml
task:                     # human-readable summary, ≤ 120 chars
  summary: "Verify applicant's financial ratios against lending policy"

target_agent_id:          # UUID; must resolve to a Specialist Agent in the Run's Tenant
  "..."
input:                    # JSON Schema-validated object the target Agent receives
  financial_summary:
    revenue: 12000000000  # VND
    # ...

output:                   # declared output shape, used by Orchestrator at aggregation
  type: object
  properties:
    verdict: { enum: [pass, fail, review] }
    ratios: { type: object }
    rationale: { type: string }

expected:                 # what the Orchestrator expects the Agent to do
  - "Retrieve relevant lending-policy clauses via KB"
  - "Compute three financial ratios"
  - "Compare each ratio against the policy threshold"
  - "Return a verdict with rationale"

criteria:                 # rubric the Agent's response is evaluated against
  confidence_floor: 0.7
  must_cite_kb: true
  must_use_tool: "financial-ratio-calculator"
```

Rejected Tasks (schema-invalid) are dropped and logged. Tasks with `target_agent_id` outside the Run's Tenant or Department scope are rejected before dispatch.
