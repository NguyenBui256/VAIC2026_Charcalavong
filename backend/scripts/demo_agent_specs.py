"""Static specs for the Epic 7 demo Specialist Agents + Tools + Workflow.

Data only — no DB/service calls. Kept separate from
`bootstrap_demo_agents_workflow.py` per the file-size dev-rule (keep files
under ~200 lines; split by concern).

Mirrors PRD `docs/prd.md` Appendix:
- §A6 (Orchestrator Decomposition example) — the 3 Agent/Tool pairing.
- §A8 (Bootstrapping the Demo Tenant) — 3 Specialist Agents, each with a
  Model selection + >=1 Tool.

`embedded_python` scripts run inside `SubprocessSandbox`
(`app/core/adapters/sandbox.py`): the Tool's raw arguments arrive as a JSON
string on stdin; the script must print exactly one JSON object as its last
stdout line. Only `sys`/`json` (stdlib, unblocked) are used here — no
network/filesystem access is available to embedded Tools (AR-14).
"""

from __future__ import annotations

from typing import Any, TypedDict


class ToolSpec(TypedDict):
    display_name: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    embedded_python: str


class AgentSpec(TypedDict):
    name: str
    department: str
    system_prompt: str
    tool: ToolSpec


# ---------------------------------------------------------------------------
# Embedded-Python Tool sources (stdin JSON in, one JSON line on stdout out).
# ---------------------------------------------------------------------------

_FR_CALC_SRC = (
    "import json, sys\n"
    "data = json.loads(sys.stdin.read())\n"
    "fs = data.get('financial_summary', {})\n"
    "ca = fs.get('current_assets', 0)\n"
    "cl = fs.get('current_liabilities', 0)\n"
    "ebitda = fs.get('ebitda', 0)\n"
    "debt_service = fs.get('debt_service', 0)\n"
    "current_ratio = (ca / cl) if cl else 0\n"
    "dscr = (ebitda / debt_service) if debt_service else 0\n"
    "if current_ratio >= 1.2 and dscr >= 1.25:\n"
    "    verdict = 'pass'\n"
    "elif current_ratio >= 1.0:\n"
    "    verdict = 'review'\n"
    "else:\n"
    "    verdict = 'fail'\n"
    "print(json.dumps({'ratios': {'current_ratio': round(current_ratio, 2), "
    "'dscr': round(dscr, 2)}, 'verdict': verdict}))\n"
)

_SANCTIONS_SRC = (
    "import json, sys\n"
    "data = json.loads(sys.stdin.read())\n"
    "principals = data.get('principals', [])\n"
    "sanctions_list = {'john doe', 'acme sanctions co', 'evil corp'}\n"
    "flags = [p for p in principals if str(p).strip().lower() in sanctions_list]\n"
    "print(json.dumps({'flags': flags}))\n"
)

_CHECKLIST_SRC = (
    "import json, sys\n"
    "data = json.loads(sys.stdin.read())\n"
    "required = set(data.get('required_documents', []))\n"
    "provided = set(data.get('provided_documents', []))\n"
    "missing = sorted(required - provided)\n"
    "print(json.dumps({'missing': missing}))\n"
)


AGENT_SPECS: tuple[AgentSpec, ...] = (
    {
        "name": "Credit Analyst",
        "department": "Credit",
        "system_prompt": (
            "You are the Credit Analyst for SHB Demo Bank. Given a borrower's "
            "financial summary, retrieve relevant lending-policy clauses, "
            "compute financial ratios via the financial-ratio-calculator "
            "tool, and return ONLY a JSON object with a numeric 'confidence' "
            "in [0,1] and a 'rationale' string."
        ),
        "tool": {
            "display_name": "financial-ratio-calculator",
            "input_schema": {
                "type": "object",
                "required": ["financial_summary"],
                "properties": {
                    "financial_summary": {
                        "type": "object",
                        "required": [
                            "revenue", "current_assets", "current_liabilities",
                            "ebitda", "debt_service",
                        ],
                        "properties": {
                            "revenue": {"type": "number"},
                            "current_assets": {"type": "number"},
                            "current_liabilities": {"type": "number"},
                            "ebitda": {"type": "number"},
                            "debt_service": {"type": "number"},
                        },
                    }
                },
            },
            "output_schema": {
                "type": "object",
                "required": ["ratios", "verdict"],
                "properties": {
                    "ratios": {"type": "object"},
                    "verdict": {"enum": ["pass", "fail", "review"]},
                },
            },
            "embedded_python": _FR_CALC_SRC,
        },
    },
    {
        "name": "Compliance Analyst",
        "department": "Legal/Compliance",
        "system_prompt": (
            "You are the Compliance Analyst for SHB Demo Bank. Given a list "
            "of loan-applicant principals, retrieve the KYC/AML circular, "
            "screen each principal via the sanctions-check tool, and return "
            "ONLY a JSON object with a numeric 'confidence' in [0,1] and a "
            "'rationale' string."
        ),
        "tool": {
            "display_name": "sanctions-check",
            "input_schema": {
                "type": "object",
                "required": ["principals"],
                "properties": {
                    "principals": {"type": "array", "items": {"type": "string"}}
                },
            },
            "output_schema": {
                "type": "object",
                "required": ["flags"],
                "properties": {"flags": {"type": "array"}},
            },
            "embedded_python": _SANCTIONS_SRC,
        },
    },
    {
        "name": "Operations Analyst",
        "department": "Operations",
        "system_prompt": (
            "You are the Operations Analyst for SHB Demo Bank. Given a "
            "required document checklist and the documents actually "
            "provided, verify completeness via the doc-checklist-verifier "
            "tool, and return ONLY a JSON object with a numeric "
            "'confidence' in [0,1] and a 'rationale' string."
        ),
        "tool": {
            "display_name": "doc-checklist-verifier",
            "input_schema": {
                "type": "object",
                "required": ["required_documents", "provided_documents"],
                "properties": {
                    "required_documents": {"type": "array", "items": {"type": "string"}},
                    "provided_documents": {"type": "array", "items": {"type": "string"}},
                },
            },
            "output_schema": {
                "type": "object",
                "required": ["missing"],
                "properties": {"missing": {"type": "array"}},
            },
            "embedded_python": _CHECKLIST_SRC,
        },
    },
)

# Model selected at config time (§A8) — the `openai` adapter targets the FPT
# AI Marketplace (OpenAI-compatible, `VAIC_LLM_BASE_URL`) serving
# DeepSeek-V4-Flash; `configured` depends on `ANTHROPIC_API_KEY` being set in
# the runtime environment (see `core/settings.py::llm_api_key`).
AGENT_MODEL_REF: dict[str, Any] = {
    "provider": "openai",
    "model_name": "DeepSeek-V4-Flash",
    "parameters": {},
}

DEMO_WORKFLOW_NAME = "Business Loan Pre-Screen"
DEMO_WORKFLOW_DESCRIPTION = (
    "Pre-screen a business loan application for a corporate borrower: verify "
    "financial ratios against lending policy (Credit Analyst), run a "
    "KYC/AML sanctions screen on the applicant's principals (Compliance "
    "Analyst), and confirm the required document checklist is complete "
    "(Operations Analyst) before advancing the application to underwriting."
)

__all__ = [
    "AGENT_SPECS",
    "AGENT_MODEL_REF",
    "DEMO_WORKFLOW_NAME",
    "DEMO_WORKFLOW_DESCRIPTION",
    "AgentSpec",
    "ToolSpec",
]
