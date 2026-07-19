"""Port interfaces (hexagonal core).

Story 1.4: defines the abstract Protocols that every adapter implements.
Concrete adapters arrive in later stories (1.5 Audit, 1.6 LLM, etc.).

Story 2.5 adds `AgentProviderPort` (deferred from 1.4) -- the Orchestrator's
(Epic 3) interface for dispatching Agent-internal retrieval Tasks, backed by
`kb_search` (`app/modules/agent_builder/kb_retrieval.py`).
"""
