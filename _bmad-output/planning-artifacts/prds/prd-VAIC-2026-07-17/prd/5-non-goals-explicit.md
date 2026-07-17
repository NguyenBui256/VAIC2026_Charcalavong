# 5. Non-Goals (Explicit)

- **Mobile native apps.** v1 is web-only.
- **Cross-Tenant Mini-App marketplace / sharing.**
- **Fine-grained RBAC engine beyond Department + Visibility Tier + builder/manager/operator roles.**
- **Billing / commercial packaging.**
- **Agent-generated Mini-App code export to external repos.** Mini-Apps live inside VAIC.
- **Visual drag-drop workflow editor.** Workflows are described textually in v1; the Orchestrator decomposes dynamically.
- **Live OAuth to external systems** (Gmail, Calendar, bank core) in MVP. API Integrations point at stubbed FastAPI endpoints.
- **Streaming partial Agent responses** during a Run for MVP.
- **Exactly-once event delivery.** At-least-once with sequence numbers is the v1 contract.
- **Vietnamese-language enforcement on Agent outputs.** Agents respond in whatever language the prompt requests; the platform does not translate.
- **Public APIs / third-party developer surface.**
- **Production-grade secrets management.** Demo uses environment-loaded keys; rotation and HSM are post-hackathon.
- **Multi-region deployment.** Single-region for v1.
