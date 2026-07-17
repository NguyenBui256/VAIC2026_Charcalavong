# A4. Tool Configuration Schema (referenced by FR-3)

```yaml
name: "financial-ratio-calculator"
description: "Computes DSCR, current ratio, debt-to-equity from a financial summary."

header:
  auth: bearer            # or basic, api_key, none
  token_ref: "vault://tools/fr-calc"   # secrets via env / vault, never inline

input_schema:             # JSON Schema
  type: object
  required: [financial_summary]
  properties:
    financial_summary: { type: object }

output_schema:
  type: object
  required: [ratios, verdict]
  properties:
    ratios: { type: object }
    verdict: { enum: [pass, fail, review] }

embedded_python:          # optional, for tighter control
  source_ref: "tools/fr_calc.py"
  entry: compute_ratios
  network: false
  execution_budget_s: 10
```

Tool invocations that fail input validation are rejected before execution. Tool outputs that fail output validation are logged in the Audit Trail and surfaced as failed steps in the Trace Dashboard.
