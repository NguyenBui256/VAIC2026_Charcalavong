---
title: VAIC — Enterprise AI-Agent Platform for Banking Automation
status: draft
created: 2026-07-17
updated: 2026-07-17
---


# Product Brief: VAIC


> A hackathon-stage product brief. Focus: the **platform architecture and backend logic** that make multi-expert agent collaboration and agent-generated mini-apps real for Vietnamese bank employees and managers. Demo scenarios come *after* the platform is sound.


## Executive Summary


**VAIC** is an enterprise AI-agent platform built to automate **cross-department, multi-step banking workflows** — the kind that today stall between teams, inboxes, and spreadsheets. It lets a bank configure **multiple specialist AI agents** (each with its own knowledge base, tools, and API integrations), coordinate them through a **workflow orchestrator** that decomposes complex requests, and have those agents **generate working mini-apps** — each with an auto-provisioned backend and per-tenant database — so every flow gets a real interface and persistent storage.


The bet: in Vietnamese banking, the unautomated work is not single tasks — it is *multi-step flows that cross departments* (lending, KYC/AML, approvals, exceptions). Single chatbots cannot own those flows because there is no place for the work to *live*. VAIC's closed loop — **agents generate the app → the app emits events back → agents react** — turns a chat into a system that actually carries the work.


**Why now:** agent platforms and MCP matured into the mainstream in 2026, so the building blocks are commodity; Vietnamese banks are actively modernizing internal tooling. The wedge is not the building blocks — it is **their integration**, aimed at one vertical.


## The Problem


Bank employees and managers spend their day on **multi-step, cross-department flows**: a loan application touches Credit, Legal/Compliance, and Operations; an exception touches Branch, Risk, and Back-Office. Today these flows run on **email, chat, Excel, and tribal knowledge**. The cost:


- **No single owner of the workflow** — work bounces between inboxes; status is "let me check."
- **Repetitive judgment work** — policy lookups, document checks, data entry — done manually every time.
- **No system of record for the flow itself** — data scatters across files; nothing captures the *decision trail*.
- **IT cannot keep up** — every new internal tool needs a dev team and a backlog ticket.


Single-agent chatbots help with *a question* but not *a process*: they cannot hold state across departments, cannot hand off cleanly, and produce nothing persistent. The gap is the **flow**, not the answer.


## The Solution


VAIC is a multi-tenant web platform with four working parts:


1. **Agent Builder** — configure specialist agents per department: a per-agent **Knowledge Base** (uploaded policy docs, regulations, text; retrieved via RAG), **tool calling**, **API integrations** (internal systems, Gmail, Calendar), configurable prompts and model choice. Per-agent KB isolation so Credit cannot read HR's docs. Tool config accepts header (auth), input schema, output schema, and optional embedded Python for tighter control.
2. **Workflow Orchestrator** — a coordinator agent **dynamically decomposes** a complex request (over JSON/YAML task schemas: `task / input / output / expected / criteria`) and dispatches subtasks to specialist agents. Agents coordinate through **MCP**, which doubles as the shared task store. On conflict or ambiguity the agents cannot self-resolve, the orchestrator **falls back to a human** with current status — human-in-the-loop, with per-step feedback.
3. **Mini-App Builder** — from a description + expected output, an agent **generates a mini-app**: UI + auto-provisioned backend + per-tenant database, stored and run on VAIC. Visibility tiers: **Public** / **Need-Auth** (account + department) / **Private** (whitelisted). Mini-apps **emit events back** into the orchestrator — the workflow and its UI form one closed loop.
4. **Actions** — **cron** schedules and **in-app event triggers** that fire agents at the right time (daily reports, weekly reconciliations, "when a form is submitted").


**The closed loop is the product:** a manager describes a flow → the orchestrator decomposes it → specialist agents work it → a mini-app is generated for staff to operate → the app emits events as humans act → agents react. The work now *lives somewhere*.


## What Makes This Different (honest)


The agent-builder category is **crowded** — Dify, LangFlow, Copilot Studio, Agentforce all ship KB/RAG + tool calling + MCP. **MCP is table-stakes in 2026, not a differentiator.** VAIC does not win on "having agents."


Where it earns its place:


- **The closed loop — agent → generated app → event → agent.** No surveyed competitor lets an agent *generate a deployable mini-app with a hosted backend that emits events back into the orchestrating workflow*. That integration is architecturally novel. It is **not a moat** — it is an execution lead.
- **Multi-expert collaboration on one vertical.** General-purpose agent platforms stay shallow across industries; VAIC goes deep on **Vietnamese banking cross-department flows** — the vocabulary, the policy structure, the maker-checker norms.
- **Per-tenant storage with visibility tiers.** JSONB-backed flexibility (schema-per-app) with department-level isolation — what regulated industries require, and what consumer app-generators (Lovable, Bolt) ignore.


If there is a moat, it is **vertical depth and execution speed**, not any single feature.


## Who This Serves


- **Primary users** — **bank employees and managers** running cross-department work daily: credit officers, compliance analysts, operations staff, branch managers. They want the flow to *move* without chasing it.
- **Secondary users** — **IT / internal-tools teams** who cannot ship internal tools fast enough today; VAIC lets the business build its own automation without a dev queue.
- **Geography:** **Vietnamese users first** — Vietnamese-language UX, local banking regulations (NHNN circulars), local integrations.
- **Buyer (hackathon context):** **banking operators** — the operations leadership who own the cross-department flows VAIC automates. The hackathon rubric rewards exactly this: 2–3 specialist agents (Credit, Legal/Compliance, Operations) collaborating on one complex request, a planner that decomposes and assigns work, real tool use (APIs, data queries, concrete actions), and a trace dashboard.


## How It Works — Architecture


Because the platform must be sound before the demo, this is the load-bearing section.


**Tech stack:**
- **Backend:** **FastAPI** (Python) — async, schema-friendly, fits LLM/tool-call work.
- **Database:** **PostgreSQL** — single source of truth; **JSONB** columns for mini-app entity storage (flexible per-app schema without per-app migrations).
- **Frontend:** **ReactJS** — design direction per the team's reference (`docs/UI Screenshot.png`).
- **LLM layer:** model-agnostic (configurable per agent); MCP client for tool and task exchange.


**Multi-tenancy & data model:**
- Tenant = enterprise (a bank). Within a tenant: users, departments, roles.
- **Agents** are tenant-scoped configs (KB reference, prompt, model, tools, API credentials).
- **Mini-apps** own a JSONB-backed data namespace per app; rows carry `tenant_id`, `department_id`, `owner_id`, visibility tier. Access enforced via the visibility tier + role.
- **Workflows** are runs of the orchestrator; every step, tool call, retrieval, and decision is **logged for trace** (required by the hackathon rubric and by banking audit).


**Orchestration:**
- Orchestrator receives a request → LLM decomposes into structured tasks (JSON/YAML schema) → tasks dispatched to specialist agents via MCP → results aggregated → on conflict or low confidence, escalate to a human with status + per-step feedback loop.
- MCP doubles as the **task store** — the shared state agents read and write through.


**Auto-backend for mini-apps:**
- Agent emits an **entity schema (JSON)** + UI spec → VAIC provisions a JSONB table namespace, CRUD endpoints, and an auth-gated UI automatically → app registered with a visibility tier → app events route back into the orchestrator's action bus.


**Actions:** cron + an internal event bus; mini-app events and schedules both enqueue agent runs.


**Audit / trace:** every agent decision logged — docs retrieved, tools called, prompts, model, latency per step. This *is* the rubric's trace-dashboard input and the demo's "why this beats a chatbot" evidence.


## Success Criteria


**Hackathon — the four rubric bars:**
1. **2–3 specialized digital experts** (e.g., Credit, Legal/Compliance, Operations) collaborating on **one complex request**.
2. **Orchestration by a planner** that decomposes the work and assigns tasks to specialist executor agents.
3. **Practical tool use** — agents call APIs, query data, and perform concrete actions, not just return text.
4. **Trace dashboard** — agent traces, task status, decisions, and collaboration flows visible end-to-end.


On top of the rubric: the demo produces a **mini-app with real storage + backend**, and (stretch, not scored) a side-by-side vs a single-agent chatbot.


**Product:**
- Employees/managers automate a real daily workflow end-to-end without IT.
- Workflow traces pass internal audit review.
- `[TO BE DEFINED]` Quantitative success metrics (cycle time, accuracy, adoption) will be set **after the platform is ready**, with the mentor.


## Scope


**In for v1 (hackathon + immediately after):**
- Agent Builder (per-agent KB/RAG, tools, API integrations, prompt, model).
- Workflow Orchestrator (LLM dynamic decomposition, MCP task store, human-in-the-loop fallback).
- Mini-App Builder (agent-generated app + auto JSONB backend + visibility tiers + events back).
- Actions (cron + in-app event triggers).
- Trace/audit logging tied to the rubric's trace dashboard.


**Explicitly OUT for v1 (v1 = web platform only):**
- Mobile native apps (web only for v1).
- Cross-tenant app marketplace / sharing.
- Fine-grained RBAC engine beyond department + visibility tier.
- Billing / commercial packaging.
- Agent-generated mini-app code export to external repos.


## Vision


If VAIC works, in 2–3 years it becomes **the way Vietnamese banks build internal software** — every cross-department flow becomes an orchestrated set of specialist agents with a generated app front-end, and the business ships automation without a dev ticket. The same skeleton extends to insurance, public-sector permitting, and any regulated vertical where the *flow* — not the answer — is the unit of work.


---


*Draft v2 — redlines applied. Open item: quantitative product success metrics deferred (`[TO BE DEFINED]`).*
