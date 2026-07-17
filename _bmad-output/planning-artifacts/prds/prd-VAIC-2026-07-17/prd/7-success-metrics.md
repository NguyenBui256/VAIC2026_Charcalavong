# 7. Success Metrics

*Each SM cross-references the FR(s) it validates. Counter-metrics counterbalance specific primary metrics.*

**Primary (rubric-aligned)**

- **SM-1**: Specialist collaboration visible — at demo, the platform demonstrably runs 2–3 Specialist Agents in one Workflow Run, each with its own KB and Tools. Target: ≥ 2 Agents, recommended 3. Validates FR-1, FR-7, FR-8, FR-9. **(SHB rubric bar 1.)**
- **SM-2**: Planner decomposition visible — at demo, the Orchestrator visibly decomposes the request into ≥ 2 Tasks and routes each to the right Agent. Target: ≥ 2 Tasks per Run, recommended 3. Validates FR-8, FR-9. **(SHB rubric bar 2.)**
- **SM-3**: Real tool use — each Specialist Agent invokes ≥ 1 Tool with a concrete input and a concrete output during the demo Run. Target: 100% of demo Agents. Validates FR-3, FR-9. **(SHB rubric bar 3.)**
- **SM-4**: Trace Dashboard renders end-to-end — the demo Run's Audit Trail is visible as both timeline and collaboration graph, with every step explorable. Target: 0 missing steps; graph renders in < 1 s. Validates FR-21, FR-22, FR-23. **(SHB rubric bar 4.)**

**Secondary (brief stretch + platform integrity)**

- **SM-5**: Generated Mini-App with real storage — the demo Run produces a Mini-App with a live JSONB Namespace, CRUD endpoints, and an auth-gated UI that the judge can open and edit. Target: 1 live Mini-App per demo. Validates FR-12, FR-13, FR-14, FR-15.
- **SM-6**: Closed loop demonstrated — an edit on the generated Mini-App emits an App Event that triggers a follow-on Workflow Run within 5 s. Target: 1 closed-loop firing per demo. Validates FR-17, FR-19.
- **SM-7**: User-configured Model — at least one demo Agent uses a Model the team selected at config time (not a hard-coded platform default). Target: 100% of demo Agents. Validates FR-5, FR-26.

**Counter-metrics (do not optimize)**

- **SM-C1**: Agent decision latency — do NOT over-optise Orchestrator or Agent latency at the cost of Audit Trail completeness. A faster Run with missing trace entries fails SM-4 even if SM-1–SM-3 pass. Counterbalances SM-1 through SM-3.
- **SM-C2**: Demo smoke-test variance — do NOT game the demo by hard-coding outputs. A Run that produces correct outputs without invoking Tools (per Audit Trail) fails SM-3 even if the screen looks right. Counterbalances SM-3.
- **SM-C3**: Tenant isolation probe — do NOT weaken per-Tenant isolation to ship a feature faster. A cross-Tenant read attempt must return 404 in every demo Run. Counterbalances SM-5.
