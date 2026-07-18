"""Static specs for the Epic 7 demo Specialist Agents + Tools + Workflow.

Data only — no DB/service calls. Kept separate from
`bootstrap_demo_agents_workflow.py` per the file-size dev-rule (keep files
under ~200 lines; split by concern).

Mirrors PRD `docs/prd.md` Appendix:
- §A6 (Orchestrator Decomposition example) — the 3 Agent/Tool pairing.
- §A8 (Bootstrapping the Demo Tenant) — 3 Specialist Agents, each with a
  Model selection + >=1 Tool.

Tools are no longer embedded-Python specs per Agent — each Agent now simply
references catalog `tool_type`s (seeded once per tenant via
`tool_catalog_service.seed_default_tools`) and is granted a set of demo KB
documents (seeded tenant-wide into the KB store).
"""

from __future__ import annotations

from typing import Any, TypedDict

from app.core.settings import get_settings


class AgentSpec(TypedDict):
    name: str
    department: str
    system_prompt: str
    tool_types: list[str]        # catalog tool_types this agent references
    kb_doc_filenames: list[str]  # demo KB docs granted to this agent


# Demo KB documents seeded into the tenant-wide store (filename -> content_type).
DEMO_KB_DOCS: tuple[dict[str, str], ...] = (
    {"filename": "SHB-Lending-Policy.md", "content_type": "text/markdown"},
    {"filename": "KYC-AML-Circular.md", "content_type": "text/markdown"},
    {"filename": "Ops-Document-Checklist.md", "content_type": "text/markdown"},
)

AGENT_SPECS: tuple[AgentSpec, ...] = (
    {
        "name": "Credit Analyst",
        "department": "Credit",
        "system_prompt": (
            "You are the Credit Analyst for SHB Demo Bank. Retrieve relevant "
            "lending-policy clauses from your Knowledge Base and return ONLY a "
            "JSON object with a numeric 'confidence' in [0,1] and a 'rationale'."
        ),
        "tool_types": ["rag"],
        "kb_doc_filenames": ["SHB-Lending-Policy.md"],
    },
    {
        "name": "Compliance Analyst",
        "department": "Legal/Compliance",
        "system_prompt": (
            "You are the Compliance Analyst for SHB Demo Bank. Retrieve the "
            "KYC/AML circular from your Knowledge Base and return ONLY a JSON "
            "object with a numeric 'confidence' in [0,1] and a 'rationale'."
        ),
        "tool_types": ["rag"],
        "kb_doc_filenames": ["KYC-AML-Circular.md"],
    },
    {
        "name": "Operations Analyst",
        "department": "Operations",
        "system_prompt": (
            "You are the Operations Analyst for SHB Demo Bank. Retrieve the "
            "document checklist from your Knowledge Base and return ONLY a JSON "
            "object with a numeric 'confidence' in [0,1] and a 'rationale'."
        ),
        "tool_types": ["rag"],
        "kb_doc_filenames": ["Ops-Document-Checklist.md"],
    },
)

def get_agent_model_ref() -> dict[str, Any]:
    """Model selected at config time (§A8), fully `.env`-driven.

    `provider`/`model_name` come from `Settings.llm_provider`/`llm_model`
    (`VAIC_LLM_PROVIDER`/`VAIC_LLM_MODEL`) -- the `openai` adapter targets
    the FPT AI Marketplace (OpenAI-compatible, `VAIC_LLM_BASE_URL`) by
    default. `configured` depends on `VAIC_LLM_API_KEY`/`ANTHROPIC_API_KEY`
    being set in the runtime environment (see `core/settings.py::llm_api_key`).
    """
    settings = get_settings()
    return {
        "provider": settings.llm_provider,
        "model_name": settings.llm_model,
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
    "DEMO_KB_DOCS",
    "get_agent_model_ref",
    "DEMO_WORKFLOW_NAME",
    "DEMO_WORKFLOW_DESCRIPTION",
    "AgentSpec",
]
