# 1. Vision

Vietnamese bank employees and managers spend their day moving **cross-department, multi-step flows** — lending, KYC/AML, exception handling, approvals — across email, chat, Excel, and tribal knowledge. Single-agent chatbots help with *a question* but not *a process*: they cannot hold state across departments, hand off cleanly, or produce anything persistent. The gap is the **flow**, not the answer.

**VAIC closes that gap.** It is a web platform where a bank's own staff can configure multiple **Specialist Agents** (each with its own knowledge base, tools, API integrations, prompt, and model), coordinate them through a **Workflow Orchestrator** that decomposes a complex request into structured tasks, dispatch those tasks over **MCP**, and have the agents **generate Mini-Apps** — each with an auto-provisioned backend and per-tenant storage — that emit events back into the orchestrator. The work now lives somewhere: a chat becomes a system that carries the work.

The closed loop — **agent generates app → app emits events → agents react** — is what makes VAIC architecturally novel in a 2026 category where agent builders, RAG, and MCP are commodity. The competitive wedge is not any single feature; it is the **integration of those features aimed at one vertical** (Vietnamese banking cross-department work) plus **execution speed**.

For the **Hack CX Together 2026** demo, the platform must demonstrably run end-to-end on one configured cross-department flow, satisfying the rubric's four bars (specialist collaboration, planner decomposition, real tool use, trace dashboard) plus the brief's stretch (a generated mini-app with real storage).
