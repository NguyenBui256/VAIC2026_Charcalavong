--
-- PostgreSQL database dump
--


-- Dumped from database version 18.4 (Debian 18.4-1.pgdg13+1)
-- Dumped by pg_dump version 18.4 (Debian 18.4-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: users_set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.users_set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: action_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.action_bindings (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    database_id uuid NOT NULL,
    event_type character varying(32) DEFAULT 'row.created'::character varying NOT NULL,
    workflow_id uuid,
    notify_user_ids uuid[] DEFAULT '{}'::uuid[] NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    target_type character varying(16) DEFAULT 'workflow'::character varying NOT NULL,
    agent_id uuid,
    CONSTRAINT ck_action_bindings_event_type CHECK (((event_type)::text = ANY ((ARRAY['row.created'::character varying, 'row.updated'::character varying, 'row.deleted'::character varying])::text[]))),
    CONSTRAINT ck_action_bindings_target CHECK (((((target_type)::text = 'workflow'::text) AND (workflow_id IS NOT NULL) AND (agent_id IS NULL)) OR (((target_type)::text = 'agent'::text) AND (agent_id IS NOT NULL) AND (workflow_id IS NULL))))
);

ALTER TABLE ONLY public.action_bindings FORCE ROW LEVEL SECURITY;


--
-- Name: action_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.action_events (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    app_id uuid NOT NULL,
    database_id uuid,
    event_type character varying(32) NOT NULL,
    row_id uuid,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    status character varying(16) DEFAULT 'pending'::character varying NOT NULL,
    workflow_run_id uuid,
    result jsonb DEFAULT '{}'::jsonb NOT NULL,
    completed_notified boolean DEFAULT false NOT NULL,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone,
    CONSTRAINT ck_action_events_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'dispatched'::character varying, 'failed'::character varying, 'skipped'::character varying])::text[])))
);

ALTER TABLE ONLY public.action_events FORCE ROW LEVEL SECURITY;


--
-- Name: agent_kb_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_kb_documents (
    agent_id uuid NOT NULL,
    document_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.agent_kb_documents FORCE ROW LEVEL SECURITY;


--
-- Name: agent_tools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_tools (
    agent_id uuid NOT NULL,
    tool_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.agent_tools FORCE ROW LEVEL SECURITY;


--
-- Name: agents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agents (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    department_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    system_prompt text NOT NULL,
    status character varying(32) DEFAULT 'draft'::character varying NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    model jsonb DEFAULT '{}'::jsonb NOT NULL
);

ALTER TABLE ONLY public.agents FORCE ROW LEVEL SECURITY;


--
-- Name: api_integrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_integrations (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    base_url character varying(2048) NOT NULL,
    auth_header_encrypted text NOT NULL,
    schema jsonb,
    last_used_at timestamp with time zone,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.api_integrations FORCE ROW LEVEL SECURITY;


--
-- Name: audit_evaluation_criteria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_evaluation_criteria (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(120) NOT NULL,
    description text NOT NULL,
    created_by_user_id uuid NOT NULL,
    updated_by_user_id uuid NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.audit_evaluation_criteria FORCE ROW LEVEL SECURITY;


--
-- Name: audit_evaluation_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_evaluation_jobs (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    requested_by_user_id uuid NOT NULL,
    requester_role character varying(64) NOT NULL,
    requester_department_id uuid,
    criteria_snapshot jsonb DEFAULT '[]'::jsonb NOT NULL,
    status character varying(32) DEFAULT 'queued'::character varying NOT NULL,
    phase character varying(64) DEFAULT 'queued'::character varying NOT NULL,
    progress integer DEFAULT 5 NOT NULL,
    error_code character varying(128) DEFAULT ''::character varying NOT NULL,
    error_message text DEFAULT ''::text NOT NULL,
    evaluation_id uuid,
    boundary_sequence bigint NOT NULL,
    boundary_hash character varying(64) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    ended_at timestamp with time zone
);

ALTER TABLE ONLY public.audit_evaluation_jobs FORCE ROW LEVEL SECURITY;


--
-- Name: audit_evaluations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_evaluations (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    evaluator_name character varying(255) NOT NULL,
    evaluator_version character varying(128) DEFAULT ''::character varying NOT NULL,
    evaluator_type character varying(32) DEFAULT 'rule'::character varying NOT NULL,
    status character varying(32) NOT NULL,
    score numeric(8,5),
    metrics jsonb DEFAULT '{}'::jsonb NOT NULL,
    criteria jsonb DEFAULT '[]'::jsonb NOT NULL,
    evidence_span_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    requested_by_user_id uuid,
    provider character varying(64) DEFAULT ''''''::character varying NOT NULL,
    model character varying(255) DEFAULT ''''''::character varying NOT NULL,
    overall_pass boolean,
    summary text DEFAULT ''''''::text NOT NULL,
    assessment text DEFAULT ''''''::text NOT NULL,
    insights jsonb DEFAULT '[]'::jsonb NOT NULL,
    issues jsonb DEFAULT '[]'::jsonb NOT NULL,
    strengths jsonb DEFAULT '[]'::jsonb NOT NULL,
    context_manifest jsonb DEFAULT '{}'::jsonb NOT NULL,
    input_tokens bigint DEFAULT '0'::bigint NOT NULL,
    output_tokens bigint DEFAULT '0'::bigint NOT NULL,
    latency_ms bigint DEFAULT '0'::bigint NOT NULL,
    estimated_cost_usd numeric(18,8) DEFAULT '0'::numeric NOT NULL
);

ALTER TABLE ONLY public.audit_evaluations FORCE ROW LEVEL SECURITY;


--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_events (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    span_id uuid,
    parent_span_id uuid,
    sequence_no bigint NOT NULL,
    occurred_at timestamp with time zone NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    event_type character varying(96) NOT NULL,
    phase character varying(16) DEFAULT 'instant'::character varying NOT NULL,
    severity character varying(16) DEFAULT 'info'::character varying NOT NULL,
    actor_type character varying(32) DEFAULT 'system'::character varying NOT NULL,
    actor_id uuid,
    status character varying(32),
    input_payload_id uuid,
    output_payload_id uuid,
    attributes jsonb DEFAULT '{}'::jsonb NOT NULL,
    schema_version integer DEFAULT 2 NOT NULL,
    prev_hash character varying(64) DEFAULT ''::character varying NOT NULL,
    event_hash character varying(64) NOT NULL
);

ALTER TABLE ONLY public.audit_events FORCE ROW LEVEL SECURITY;


--
-- Name: audit_payloads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_payloads (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    department_id uuid,
    content_type character varying(128) DEFAULT 'application/json'::character varying NOT NULL,
    classification character varying(32) DEFAULT 'confidential'::character varying NOT NULL,
    data jsonb NOT NULL,
    byte_size bigint NOT NULL,
    sha256 character varying(64) NOT NULL,
    redaction_count integer DEFAULT 0 NOT NULL,
    redaction_paths jsonb DEFAULT '[]'::jsonb NOT NULL,
    policy_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.audit_payloads FORCE ROW LEVEL SECURITY;


--
-- Name: audit_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_sessions (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    department_id uuid,
    workflow_id uuid,
    workflow_version character varying(128) DEFAULT ''::character varying NOT NULL,
    correlation_id uuid NOT NULL,
    parent_session_id uuid,
    trace_id uuid NOT NULL,
    name character varying(255) DEFAULT ''::character varying NOT NULL,
    trigger_type character varying(32) DEFAULT 'manual'::character varying NOT NULL,
    trigger_id uuid,
    source_event_id uuid,
    initiator_user_id uuid,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    current_span_id uuid,
    input_payload_id uuid,
    result_payload_id uuid,
    failure_summary text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    queued_at timestamp with time zone,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    llm_call_count bigint DEFAULT '0'::bigint NOT NULL,
    tool_call_count bigint DEFAULT '0'::bigint NOT NULL,
    rag_call_count bigint DEFAULT '0'::bigint NOT NULL,
    agent_count bigint DEFAULT '0'::bigint NOT NULL,
    retry_count bigint DEFAULT '0'::bigint NOT NULL,
    escalation_count bigint DEFAULT '0'::bigint NOT NULL,
    input_tokens bigint DEFAULT '0'::bigint NOT NULL,
    output_tokens bigint DEFAULT '0'::bigint NOT NULL,
    cached_tokens bigint DEFAULT '0'::bigint NOT NULL,
    reasoning_tokens bigint DEFAULT '0'::bigint NOT NULL,
    human_wait_ms bigint DEFAULT '0'::bigint NOT NULL,
    critical_path_ms bigint DEFAULT '0'::bigint NOT NULL,
    last_sequence bigint DEFAULT '0'::bigint NOT NULL,
    redaction_count bigint DEFAULT '0'::bigint NOT NULL,
    estimated_cost_usd numeric(18,8) DEFAULT '0'::numeric NOT NULL,
    last_hash character varying(64) DEFAULT ''::character varying NOT NULL,
    schema_version integer DEFAULT 2 NOT NULL,
    completeness_status character varying(32) DEFAULT 'complete'::character varying NOT NULL,
    attributes jsonb DEFAULT '{}'::jsonb NOT NULL
);

ALTER TABLE ONLY public.audit_sessions FORCE ROW LEVEL SECURITY;


--
-- Name: audit_spans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_spans (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    parent_span_id uuid,
    logical_node_id character varying(255) DEFAULT ''::character varying NOT NULL,
    task_id uuid,
    agent_id uuid,
    department_id uuid,
    actor_type character varying(32) DEFAULT 'system'::character varying NOT NULL,
    node_type character varying(64) NOT NULL,
    name character varying(255) NOT NULL,
    attempt_no integer DEFAULT 1 NOT NULL,
    status character varying(32) DEFAULT 'running'::character varying NOT NULL,
    queued_at timestamp with time zone,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    ended_at timestamp with time zone,
    duration_ms bigint,
    ttft_ms bigint,
    provider character varying(64) DEFAULT ''::character varying NOT NULL,
    model character varying(255) DEFAULT ''::character varying NOT NULL,
    tool_name character varying(255) DEFAULT ''::character varying NOT NULL,
    tool_version character varying(128) DEFAULT ''::character varying NOT NULL,
    kb_id uuid,
    kb_version character varying(128) DEFAULT ''::character varying NOT NULL,
    error_code character varying(128) DEFAULT ''::character varying NOT NULL,
    error_message text DEFAULT ''::text NOT NULL,
    input_tokens bigint DEFAULT '0'::bigint NOT NULL,
    output_tokens bigint DEFAULT '0'::bigint NOT NULL,
    cached_tokens bigint DEFAULT '0'::bigint NOT NULL,
    reasoning_tokens bigint DEFAULT '0'::bigint NOT NULL,
    estimated_cost_usd numeric(18,8) DEFAULT '0'::numeric NOT NULL,
    input_payload_id uuid,
    output_payload_id uuid,
    attributes jsonb DEFAULT '{}'::jsonb NOT NULL
);

ALTER TABLE ONLY public.audit_spans FORCE ROW LEVEL SECURITY;


--
-- Name: audit_trail; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_trail (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    step_id uuid NOT NULL,
    agent_id uuid,
    ts timestamp with time zone NOT NULL,
    type character varying(64) NOT NULL,
    input jsonb DEFAULT '{}'::jsonb NOT NULL,
    output jsonb DEFAULT '{}'::jsonb NOT NULL,
    latency_ms integer NOT NULL,
    model character varying(255)
);

ALTER TABLE ONLY public.audit_trail FORCE ROW LEVEL SECURITY;


--
-- Name: chat_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_attachments (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    filename character varying(255) NOT NULL,
    content_type character varying(128) NOT NULL,
    size_bytes integer NOT NULL,
    sha256 character varying(64) NOT NULL,
    storage_path text NOT NULL,
    extraction_status character varying(16) DEFAULT 'extracting'::character varying NOT NULL,
    extracted_text text,
    extraction_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_chat_attachment_status CHECK (((extraction_status)::text = ANY ((ARRAY['extracting'::character varying, 'ready'::character varying, 'failed'::character varying])::text[])))
);

ALTER TABLE ONLY public.chat_attachments FORCE ROW LEVEL SECURITY;


--
-- Name: chat_message_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_message_attachments (
    message_id uuid NOT NULL,
    attachment_id uuid NOT NULL,
    tenant_id uuid NOT NULL
);

ALTER TABLE ONLY public.chat_message_attachments FORCE ROW LEVEL SECURITY;


--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_messages (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    role character varying(16) NOT NULL,
    content text DEFAULT ''::text NOT NULL,
    status character varying(16) DEFAULT 'completed'::character varying NOT NULL,
    client_message_id character varying(128),
    reply_to_id uuid,
    provider_id character varying(32),
    model_name character varying(255),
    input_tokens integer,
    output_tokens integer,
    latency_ms integer,
    trace_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    error jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_chat_messages_role CHECK (((role)::text = ANY ((ARRAY['user'::character varying, 'assistant'::character varying, 'system'::character varying, 'tool'::character varying])::text[]))),
    CONSTRAINT ck_chat_messages_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'completed'::character varying, 'failed'::character varying])::text[])))
);

ALTER TABLE ONLY public.chat_messages FORCE ROW LEVEL SECURITY;


--
-- Name: chat_mutations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_mutations (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    message_id uuid NOT NULL,
    target_type character varying(32) NOT NULL,
    target_id uuid NOT NULL,
    before_snapshot jsonb NOT NULL,
    after_snapshot jsonb NOT NULL,
    before_version character varying(64) NOT NULL,
    after_version character varying(64) NOT NULL,
    status character varying(16) DEFAULT 'applied'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    undone_at timestamp with time zone,
    CONSTRAINT ck_chat_mutation_status CHECK (((status)::text = ANY ((ARRAY['applied'::character varying, 'undone'::character varying])::text[])))
);

ALTER TABLE ONLY public.chat_mutations FORCE ROW LEVEL SECURITY;


--
-- Name: chat_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_sessions (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    scope character varying(32) NOT NULL,
    target_type character varying(32) NOT NULL,
    target_id uuid NOT NULL,
    provider_id character varying(32),
    model_name character varying(255),
    title character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_chat_sessions_scope CHECK (((scope)::text = ANY ((ARRAY['execution'::character varying, 'graph_authoring'::character varying, 'mini_app_edit'::character varying])::text[]))),
    CONSTRAINT ck_chat_sessions_target CHECK (((target_type)::text = ANY ((ARRAY['agent'::character varying, 'workflow'::character varying, 'mini_app'::character varying])::text[])))
);

ALTER TABLE ONLY public.chat_sessions FORCE ROW LEVEL SECURITY;


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.departments FORCE ROW LEVEL SECURITY;


--
-- Name: kb_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kb_documents (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    department_id uuid,
    filename character varying(512) NOT NULL,
    content_type character varying(128) NOT NULL,
    size_bytes bigint NOT NULL,
    status character varying(32) DEFAULT 'processing'::character varying NOT NULL,
    failure_reason text,
    external_document_id character varying(255),
    chunk_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    content bytea
);

ALTER TABLE ONLY public.kb_documents FORCE ROW LEVEL SECURITY;


--
-- Name: mini_app_databases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mini_app_databases (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    entity_schema jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.mini_app_databases FORCE ROW LEVEL SECURITY;


--
-- Name: mini_app_rows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mini_app_rows (
    id uuid NOT NULL,
    app_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    department_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.mini_app_rows FORCE ROW LEVEL SECURITY;


--
-- Name: mini_apps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mini_apps (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    department_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(64) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    entity_schema jsonb NOT NULL,
    ui_spec jsonb NOT NULL,
    visibility_tier character varying(16) DEFAULT 'need_auth'::character varying NOT NULL,
    whitelist_user_ids uuid[] DEFAULT '{}'::uuid[] NOT NULL,
    build_status character varying(16) DEFAULT 'pending'::character varying NOT NULL,
    build_error text,
    bundle_path text,
    created_by_agent_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_id uuid,
    CONSTRAINT ck_mini_apps_build_status CHECK (((build_status)::text = ANY ((ARRAY['pending'::character varying, 'building'::character varying, 'ready'::character varying, 'failed'::character varying])::text[]))),
    CONSTRAINT ck_mini_apps_visibility_tier CHECK (((visibility_tier)::text = ANY ((ARRAY['public'::character varying, 'need_auth'::character varying, 'private'::character varying])::text[])))
);

ALTER TABLE ONLY public.mini_apps FORCE ROW LEVEL SECURITY;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    category character varying(64) NOT NULL,
    title character varying(255) NOT NULL,
    body text DEFAULT ''::text NOT NULL,
    ref jsonb DEFAULT '{}'::jsonb NOT NULL,
    read_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.notifications FORCE ROW LEVEL SECURITY;


--
-- Name: run_node_executions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.run_node_executions (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    node_key character varying(64) NOT NULL,
    agent_id uuid NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    input jsonb,
    output jsonb,
    approver_user_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    decision character varying(16),
    decided_by uuid,
    reason text,
    guidance text,
    decided_at timestamp with time zone,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_run_node_executions_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'awaiting_approval'::character varying, 'completed'::character varying, 'failed'::character varying, 'rejected'::character varying, 'skipped'::character varying, 'rolled_back'::character varying])::text[])))
);

ALTER TABLE ONLY public.run_node_executions FORCE ROW LEVEL SECURITY;


--
-- Name: run_rollback_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.run_rollback_requests (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    requester_node_key character varying(64) NOT NULL,
    target_node_key character varying(64) NOT NULL,
    reason text,
    status character varying(16) DEFAULT 'pending'::character varying NOT NULL,
    decided_by uuid,
    decided_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    refuse_reason text,
    CONSTRAINT ck_run_rollback_requests_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'accepted'::character varying, 'refused'::character varying])::text[])))
);

ALTER TABLE ONLY public.run_rollback_requests FORCE ROW LEVEL SECURITY;


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tasks (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    target_agent_id uuid NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    schema_payload jsonb NOT NULL,
    result jsonb,
    claimed_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_tasks_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'claimed'::character varying, 'completed'::character varying, 'failed'::character varying])::text[])))
);

ALTER TABLE ONLY public.tasks FORCE ROW LEVEL SECURITY;


--
-- Name: tenant_audit_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_audit_keys (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    algorithm character varying(32) DEFAULT 'Ed25519'::character varying NOT NULL,
    public_key bytea NOT NULL,
    encrypted_private_key bytea NOT NULL,
    nonce bytea NOT NULL,
    fingerprint character varying(64) NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.tenant_audit_keys FORCE ROW LEVEL SECURITY;


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    audit_key_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.tenants FORCE ROW LEVEL SECURITY;


--
-- Name: tools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tools (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    tool_type character varying(32) NOT NULL,
    display_name character varying(255) NOT NULL,
    description text NOT NULL,
    params_schema jsonb NOT NULL,
    output_schema jsonb DEFAULT '{}'::jsonb NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    credential_ref text,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    kind character varying(16) DEFAULT 'builtin'::character varying NOT NULL,
    integration_id uuid,
    CONSTRAINT ck_tools_type CHECK (((tool_type)::text = ANY ((ARRAY['rag'::character varying, 'gmail'::character varying, 'calendar'::character varying])::text[])))
);

ALTER TABLE ONLY public.tools FORCE ROW LEVEL SECURITY;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    department_id uuid,
    email character varying(320) NOT NULL,
    role character varying(64) DEFAULT 'member'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    password_hash character varying(255),
    is_active boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.users FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_edges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workflow_edges (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    workflow_id uuid NOT NULL,
    from_node_id uuid NOT NULL,
    to_node_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.workflow_edges FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workflow_files (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    filename character varying(255) NOT NULL,
    content_type character varying(255) NOT NULL,
    size_bytes integer NOT NULL,
    storage_path text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.workflow_files FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_node_approvers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workflow_node_approvers (
    node_id uuid NOT NULL,
    user_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.workflow_node_approvers FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workflow_nodes (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    workflow_id uuid NOT NULL,
    node_key character varying(64) NOT NULL,
    label character varying(255) NOT NULL,
    agent_id uuid NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    position_x double precision DEFAULT '0'::double precision NOT NULL,
    position_y double precision DEFAULT '0'::double precision NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.workflow_nodes FORCE ROW LEVEL SECURITY;


--
-- Name: workflow_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workflow_runs (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    workflow_id uuid NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    input jsonb DEFAULT '{}'::jsonb NOT NULL,
    result jsonb,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    graph_snapshot jsonb,
    CONSTRAINT ck_workflow_runs_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'awaiting_human'::character varying, 'completed'::character varying, 'completed_with_failures'::character varying, 'failed'::character varying, 'timed_out'::character varying])::text[])))
);

ALTER TABLE ONLY public.workflow_runs FORCE ROW LEVEL SECURITY;


--
-- Name: workflows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workflows (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    constraints jsonb DEFAULT '[]'::jsonb NOT NULL,
    confidence_threshold double precision DEFAULT '0.7'::double precision NOT NULL,
    escalation_timeout_seconds integer DEFAULT 300 NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.workflows FORCE ROW LEVEL SECURITY;


--
-- Name: action_bindings action_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_bindings
    ADD CONSTRAINT action_bindings_pkey PRIMARY KEY (id);


--
-- Name: action_events action_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_events
    ADD CONSTRAINT action_events_pkey PRIMARY KEY (id);


--
-- Name: agent_kb_documents agent_kb_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_kb_documents
    ADD CONSTRAINT agent_kb_documents_pkey PRIMARY KEY (agent_id, document_id);


--
-- Name: agent_tools agent_tools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_tools
    ADD CONSTRAINT agent_tools_pkey PRIMARY KEY (agent_id, tool_id);


--
-- Name: agents agents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_pkey PRIMARY KEY (id);


--
-- Name: api_integrations api_integrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_integrations
    ADD CONSTRAINT api_integrations_pkey PRIMARY KEY (id);


--
-- Name: audit_evaluation_criteria audit_evaluation_criteria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_evaluation_criteria
    ADD CONSTRAINT audit_evaluation_criteria_pkey PRIMARY KEY (id);


--
-- Name: audit_evaluation_jobs audit_evaluation_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_evaluation_jobs
    ADD CONSTRAINT audit_evaluation_jobs_pkey PRIMARY KEY (id);


--
-- Name: audit_evaluations audit_evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_evaluations
    ADD CONSTRAINT audit_evaluations_pkey PRIMARY KEY (id);


--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: audit_payloads audit_payloads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_payloads
    ADD CONSTRAINT audit_payloads_pkey PRIMARY KEY (id);


--
-- Name: audit_sessions audit_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_sessions
    ADD CONSTRAINT audit_sessions_pkey PRIMARY KEY (id);


--
-- Name: audit_spans audit_spans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_spans
    ADD CONSTRAINT audit_spans_pkey PRIMARY KEY (id);


--
-- Name: audit_trail audit_trail_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_trail
    ADD CONSTRAINT audit_trail_pkey PRIMARY KEY (id);


--
-- Name: chat_attachments chat_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_attachments
    ADD CONSTRAINT chat_attachments_pkey PRIMARY KEY (id);


--
-- Name: chat_message_attachments chat_message_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message_attachments
    ADD CONSTRAINT chat_message_attachments_pkey PRIMARY KEY (message_id, attachment_id);


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: chat_mutations chat_mutations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_mutations
    ADD CONSTRAINT chat_mutations_pkey PRIMARY KEY (id);


--
-- Name: chat_sessions chat_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_pkey PRIMARY KEY (id);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: kb_documents kb_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_documents
    ADD CONSTRAINT kb_documents_pkey PRIMARY KEY (id);


--
-- Name: mini_app_databases mini_app_databases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_app_databases
    ADD CONSTRAINT mini_app_databases_pkey PRIMARY KEY (id);


--
-- Name: mini_app_rows mini_app_rows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_app_rows
    ADD CONSTRAINT mini_app_rows_pkey PRIMARY KEY (id);


--
-- Name: mini_apps mini_apps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_apps
    ADD CONSTRAINT mini_apps_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: run_node_executions run_node_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_node_executions
    ADD CONSTRAINT run_node_executions_pkey PRIMARY KEY (id);


--
-- Name: run_rollback_requests run_rollback_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_rollback_requests
    ADD CONSTRAINT run_rollback_requests_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: tenant_audit_keys tenant_audit_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_audit_keys
    ADD CONSTRAINT tenant_audit_keys_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: tools tools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_pkey PRIMARY KEY (id);


--
-- Name: action_bindings uq_action_bindings_tenant_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_bindings
    ADD CONSTRAINT uq_action_bindings_tenant_name UNIQUE (tenant_id, name);


--
-- Name: audit_events uq_audit_event_sequence; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT uq_audit_event_sequence UNIQUE (session_id, sequence_no);


--
-- Name: audit_sessions uq_audit_session_run; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_sessions
    ADD CONSTRAINT uq_audit_session_run UNIQUE (tenant_id, run_id);


--
-- Name: chat_messages uq_chat_client_message; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT uq_chat_client_message UNIQUE (session_id, client_message_id);


--
-- Name: mini_app_databases uq_mini_app_databases_tenant_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_app_databases
    ADD CONSTRAINT uq_mini_app_databases_tenant_name UNIQUE (tenant_id, name);


--
-- Name: mini_apps uq_mini_apps_tenant_slug; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_apps
    ADD CONSTRAINT uq_mini_apps_tenant_slug UNIQUE (tenant_id, slug);


--
-- Name: run_node_executions uq_run_node_executions_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_node_executions
    ADD CONSTRAINT uq_run_node_executions_key UNIQUE (run_id, node_key);


--
-- Name: tenant_audit_keys uq_tenant_audit_key_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_audit_keys
    ADD CONSTRAINT uq_tenant_audit_key_version UNIQUE (tenant_id, version);


--
-- Name: workflow_edges uq_workflow_edges_pair; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_edges
    ADD CONSTRAINT uq_workflow_edges_pair UNIQUE (from_node_id, to_node_id);


--
-- Name: workflow_nodes uq_workflow_nodes_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_nodes
    ADD CONSTRAINT uq_workflow_nodes_key UNIQUE (workflow_id, node_key);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: workflow_edges workflow_edges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_edges
    ADD CONSTRAINT workflow_edges_pkey PRIMARY KEY (id);


--
-- Name: workflow_files workflow_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_files
    ADD CONSTRAINT workflow_files_pkey PRIMARY KEY (id);


--
-- Name: workflow_node_approvers workflow_node_approvers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_node_approvers
    ADD CONSTRAINT workflow_node_approvers_pkey PRIMARY KEY (node_id, user_id);


--
-- Name: workflow_nodes workflow_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_nodes
    ADD CONSTRAINT workflow_nodes_pkey PRIMARY KEY (id);


--
-- Name: workflow_runs workflow_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_runs
    ADD CONSTRAINT workflow_runs_pkey PRIMARY KEY (id);


--
-- Name: workflows workflows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_pkey PRIMARY KEY (id);


--
-- Name: ix_action_bindings_db_event; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_bindings_db_event ON public.action_bindings USING btree (database_id, event_type);


--
-- Name: ix_action_events_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_events_tenant_status ON public.action_events USING btree (tenant_id, status);


--
-- Name: ix_agent_kb_documents_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_kb_documents_document_id ON public.agent_kb_documents USING btree (document_id);


--
-- Name: ix_agent_kb_documents_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_kb_documents_tenant_id ON public.agent_kb_documents USING btree (tenant_id);


--
-- Name: ix_agent_tools_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_tools_tenant_id ON public.agent_tools USING btree (tenant_id);


--
-- Name: ix_agent_tools_tool_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_tools_tool_id ON public.agent_tools USING btree (tool_id);


--
-- Name: ix_agents_department_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agents_department_id ON public.agents USING btree (department_id);


--
-- Name: ix_agents_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agents_tenant_id ON public.agents USING btree (tenant_id);


--
-- Name: ix_api_integrations_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_api_integrations_tenant_id ON public.api_integrations USING btree (tenant_id);


--
-- Name: ix_audit_evaluation_criteria_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_evaluation_criteria_tenant ON public.audit_evaluation_criteria USING btree (tenant_id);


--
-- Name: ix_audit_evaluation_jobs_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_evaluation_jobs_tenant ON public.audit_evaluation_jobs USING btree (tenant_id);


--
-- Name: ix_audit_evaluations_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_evaluations_tenant ON public.audit_evaluations USING btree (tenant_id);


--
-- Name: ix_audit_events_session_sequence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_session_sequence ON public.audit_events USING btree (session_id, sequence_no);


--
-- Name: ix_audit_events_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_tenant ON public.audit_events USING btree (tenant_id);


--
-- Name: ix_audit_events_type_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_type_time ON public.audit_events USING btree (event_type, occurred_at);


--
-- Name: ix_audit_payloads_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_payloads_tenant ON public.audit_payloads USING btree (tenant_id);


--
-- Name: ix_audit_sessions_status_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_sessions_status_created ON public.audit_sessions USING btree (status, created_at);


--
-- Name: ix_audit_sessions_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_sessions_tenant ON public.audit_sessions USING btree (tenant_id);


--
-- Name: ix_audit_spans_dimensions; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_spans_dimensions ON public.audit_spans USING btree (agent_id, node_type, status, model);


--
-- Name: ix_audit_spans_session_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_spans_session_parent ON public.audit_spans USING btree (session_id, parent_span_id);


--
-- Name: ix_audit_spans_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_spans_tenant ON public.audit_spans USING btree (tenant_id);


--
-- Name: ix_audit_trail_run_id_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_trail_run_id_ts ON public.audit_trail USING btree (run_id, ts);


--
-- Name: ix_audit_trail_tenant_id_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_trail_tenant_id_ts ON public.audit_trail USING btree (tenant_id, ts);


--
-- Name: ix_chat_messages_session_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_messages_session_created ON public.chat_messages USING btree (session_id, created_at);


--
-- Name: ix_chat_sessions_owner_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_sessions_owner_updated ON public.chat_sessions USING btree (owner_id, updated_at);


--
-- Name: ix_kb_documents_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_documents_owner_id ON public.kb_documents USING btree (owner_id);


--
-- Name: ix_kb_documents_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_documents_tenant_id ON public.kb_documents USING btree (tenant_id);


--
-- Name: ix_mini_app_databases_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mini_app_databases_tenant_id ON public.mini_app_databases USING btree (tenant_id);


--
-- Name: ix_mini_app_rows_app_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mini_app_rows_app_id ON public.mini_app_rows USING btree (app_id);


--
-- Name: ix_mini_app_rows_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mini_app_rows_tenant_id ON public.mini_app_rows USING btree (tenant_id);


--
-- Name: ix_mini_apps_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mini_apps_tenant_id ON public.mini_apps USING btree (tenant_id);


--
-- Name: ix_notifications_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user_created ON public.notifications USING btree (user_id, created_at);


--
-- Name: ix_run_node_executions_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_run_node_executions_run_id ON public.run_node_executions USING btree (run_id);


--
-- Name: ix_run_node_executions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_run_node_executions_status ON public.run_node_executions USING btree (status);


--
-- Name: ix_run_node_executions_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_run_node_executions_tenant_id ON public.run_node_executions USING btree (tenant_id);


--
-- Name: ix_run_rollback_requests_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_run_rollback_requests_run_id ON public.run_rollback_requests USING btree (run_id);


--
-- Name: ix_run_rollback_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_run_rollback_requests_status ON public.run_rollback_requests USING btree (status);


--
-- Name: ix_run_rollback_requests_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_run_rollback_requests_tenant_id ON public.run_rollback_requests USING btree (tenant_id);


--
-- Name: ix_tasks_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_run_id ON public.tasks USING btree (run_id);


--
-- Name: ix_tasks_status_target_agent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_status_target_agent ON public.tasks USING btree (status, target_agent_id);


--
-- Name: ix_tasks_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_tenant_id ON public.tasks USING btree (tenant_id);


--
-- Name: ix_tenant_audit_keys_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenant_audit_keys_tenant ON public.tenant_audit_keys USING btree (tenant_id);


--
-- Name: ix_tools_integration_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tools_integration_id ON public.tools USING btree (integration_id);


--
-- Name: ix_tools_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tools_tenant_id ON public.tools USING btree (tenant_id);


--
-- Name: ix_workflow_edges_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_edges_tenant_id ON public.workflow_edges USING btree (tenant_id);


--
-- Name: ix_workflow_edges_workflow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_edges_workflow_id ON public.workflow_edges USING btree (workflow_id);


--
-- Name: ix_workflow_files_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_files_tenant_id ON public.workflow_files USING btree (tenant_id);


--
-- Name: ix_workflow_node_approvers_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_node_approvers_tenant_id ON public.workflow_node_approvers USING btree (tenant_id);


--
-- Name: ix_workflow_node_approvers_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_node_approvers_user_id ON public.workflow_node_approvers USING btree (user_id);


--
-- Name: ix_workflow_nodes_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_nodes_tenant_id ON public.workflow_nodes USING btree (tenant_id);


--
-- Name: ix_workflow_nodes_workflow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_nodes_workflow_id ON public.workflow_nodes USING btree (workflow_id);


--
-- Name: ix_workflow_runs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_runs_status ON public.workflow_runs USING btree (status);


--
-- Name: ix_workflow_runs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflow_runs_tenant_id ON public.workflow_runs USING btree (tenant_id);


--
-- Name: ix_workflows_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workflows_tenant_id ON public.workflows USING btree (tenant_id);


--
-- Name: uq_audit_eval_criterion_active_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_audit_eval_criterion_active_name ON public.audit_evaluation_criteria USING btree (tenant_id, lower((name)::text)) WHERE is_active;


--
-- Name: uq_audit_eval_job_active_session; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_audit_eval_job_active_session ON public.audit_evaluation_jobs USING btree (session_id) WHERE ((status)::text = ANY ((ARRAY['queued'::character varying, 'collecting_context'::character varying, 'judging'::character varying, 'validating'::character varying])::text[]));


--
-- Name: users users_updated_at_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER users_updated_at_trigger BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.users_set_updated_at();


--
-- Name: action_bindings action_bindings_agent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_bindings
    ADD CONSTRAINT action_bindings_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES public.agents(id) ON DELETE CASCADE;


--
-- Name: action_bindings action_bindings_database_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_bindings
    ADD CONSTRAINT action_bindings_database_id_fkey FOREIGN KEY (database_id) REFERENCES public.mini_app_databases(id) ON DELETE CASCADE;


--
-- Name: action_bindings action_bindings_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_bindings
    ADD CONSTRAINT action_bindings_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: action_bindings action_bindings_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_bindings
    ADD CONSTRAINT action_bindings_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: action_bindings action_bindings_workflow_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_bindings
    ADD CONSTRAINT action_bindings_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(id) ON DELETE CASCADE;


--
-- Name: action_events action_events_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_events
    ADD CONSTRAINT action_events_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.mini_apps(id) ON DELETE CASCADE;


--
-- Name: action_events action_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_events
    ADD CONSTRAINT action_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: agent_kb_documents agent_kb_documents_agent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_kb_documents
    ADD CONSTRAINT agent_kb_documents_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES public.agents(id) ON DELETE CASCADE;


--
-- Name: agent_kb_documents agent_kb_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_kb_documents
    ADD CONSTRAINT agent_kb_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.kb_documents(id) ON DELETE CASCADE;


--
-- Name: agent_kb_documents agent_kb_documents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_kb_documents
    ADD CONSTRAINT agent_kb_documents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: agent_tools agent_tools_agent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_tools
    ADD CONSTRAINT agent_tools_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES public.agents(id) ON DELETE CASCADE;


--
-- Name: agent_tools agent_tools_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_tools
    ADD CONSTRAINT agent_tools_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: agent_tools agent_tools_tool_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_tools
    ADD CONSTRAINT agent_tools_tool_id_fkey FOREIGN KEY (tool_id) REFERENCES public.tools(id) ON DELETE CASCADE;


--
-- Name: agents agents_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE RESTRICT;


--
-- Name: agents agents_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: agents agents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: api_integrations api_integrations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_integrations
    ADD CONSTRAINT api_integrations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: audit_evaluation_jobs audit_evaluation_jobs_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_evaluation_jobs
    ADD CONSTRAINT audit_evaluation_jobs_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.audit_sessions(id);


--
-- Name: audit_evaluations audit_evaluations_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_evaluations
    ADD CONSTRAINT audit_evaluations_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.audit_sessions(id);


--
-- Name: audit_events audit_events_input_payload_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_input_payload_id_fkey FOREIGN KEY (input_payload_id) REFERENCES public.audit_payloads(id);


--
-- Name: audit_events audit_events_output_payload_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_output_payload_id_fkey FOREIGN KEY (output_payload_id) REFERENCES public.audit_payloads(id);


--
-- Name: audit_events audit_events_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.audit_sessions(id);


--
-- Name: audit_sessions audit_sessions_parent_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_sessions
    ADD CONSTRAINT audit_sessions_parent_session_id_fkey FOREIGN KEY (parent_session_id) REFERENCES public.audit_sessions(id);


--
-- Name: audit_spans audit_spans_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_spans
    ADD CONSTRAINT audit_spans_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.audit_sessions(id);


--
-- Name: chat_attachments chat_attachments_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_attachments
    ADD CONSTRAINT chat_attachments_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: chat_attachments chat_attachments_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_attachments
    ADD CONSTRAINT chat_attachments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: chat_message_attachments chat_message_attachments_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message_attachments
    ADD CONSTRAINT chat_message_attachments_attachment_id_fkey FOREIGN KEY (attachment_id) REFERENCES public.chat_attachments(id) ON DELETE RESTRICT;


--
-- Name: chat_message_attachments chat_message_attachments_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message_attachments
    ADD CONSTRAINT chat_message_attachments_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chat_messages(id) ON DELETE CASCADE;


--
-- Name: chat_message_attachments chat_message_attachments_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message_attachments
    ADD CONSTRAINT chat_message_attachments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: chat_messages chat_messages_reply_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_reply_to_id_fkey FOREIGN KEY (reply_to_id) REFERENCES public.chat_messages(id) ON DELETE SET NULL;


--
-- Name: chat_messages chat_messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id) ON DELETE CASCADE;


--
-- Name: chat_messages chat_messages_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: chat_mutations chat_mutations_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_mutations
    ADD CONSTRAINT chat_mutations_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chat_messages(id) ON DELETE CASCADE;


--
-- Name: chat_mutations chat_mutations_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_mutations
    ADD CONSTRAINT chat_mutations_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id) ON DELETE CASCADE;


--
-- Name: chat_mutations chat_mutations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_mutations
    ADD CONSTRAINT chat_mutations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: chat_sessions chat_sessions_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: chat_sessions chat_sessions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: departments departments_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: kb_documents kb_documents_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_documents
    ADD CONSTRAINT kb_documents_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: kb_documents kb_documents_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_documents
    ADD CONSTRAINT kb_documents_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: kb_documents kb_documents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_documents
    ADD CONSTRAINT kb_documents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: mini_app_databases mini_app_databases_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_app_databases
    ADD CONSTRAINT mini_app_databases_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: mini_app_databases mini_app_databases_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_app_databases
    ADD CONSTRAINT mini_app_databases_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: mini_app_rows mini_app_rows_app_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_app_rows
    ADD CONSTRAINT mini_app_rows_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.mini_apps(id) ON DELETE CASCADE;


--
-- Name: mini_app_rows mini_app_rows_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_app_rows
    ADD CONSTRAINT mini_app_rows_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: mini_apps mini_apps_database_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_apps
    ADD CONSTRAINT mini_apps_database_id_fkey FOREIGN KEY (database_id) REFERENCES public.mini_app_databases(id) ON DELETE SET NULL;


--
-- Name: mini_apps mini_apps_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_apps
    ADD CONSTRAINT mini_apps_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: mini_apps mini_apps_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mini_apps
    ADD CONSTRAINT mini_apps_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: run_node_executions run_node_executions_agent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_node_executions
    ADD CONSTRAINT run_node_executions_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES public.agents(id) ON DELETE RESTRICT;


--
-- Name: run_node_executions run_node_executions_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_node_executions
    ADD CONSTRAINT run_node_executions_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: run_node_executions run_node_executions_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_node_executions
    ADD CONSTRAINT run_node_executions_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.workflow_runs(id) ON DELETE CASCADE;


--
-- Name: run_node_executions run_node_executions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_node_executions
    ADD CONSTRAINT run_node_executions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: run_rollback_requests run_rollback_requests_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_rollback_requests
    ADD CONSTRAINT run_rollback_requests_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: run_rollback_requests run_rollback_requests_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_rollback_requests
    ADD CONSTRAINT run_rollback_requests_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.workflow_runs(id) ON DELETE CASCADE;


--
-- Name: run_rollback_requests run_rollback_requests_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_rollback_requests
    ADD CONSTRAINT run_rollback_requests_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.workflow_runs(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_target_agent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_target_agent_id_fkey FOREIGN KEY (target_agent_id) REFERENCES public.agents(id) ON DELETE RESTRICT;


--
-- Name: tasks tasks_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tools tools_integration_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES public.api_integrations(id) ON DELETE RESTRICT;


--
-- Name: tools tools_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: tools tools_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: users users_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL;


--
-- Name: users users_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: workflow_edges workflow_edges_from_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_edges
    ADD CONSTRAINT workflow_edges_from_node_id_fkey FOREIGN KEY (from_node_id) REFERENCES public.workflow_nodes(id) ON DELETE CASCADE;


--
-- Name: workflow_edges workflow_edges_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_edges
    ADD CONSTRAINT workflow_edges_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: workflow_edges workflow_edges_to_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_edges
    ADD CONSTRAINT workflow_edges_to_node_id_fkey FOREIGN KEY (to_node_id) REFERENCES public.workflow_nodes(id) ON DELETE CASCADE;


--
-- Name: workflow_edges workflow_edges_workflow_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_edges
    ADD CONSTRAINT workflow_edges_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(id) ON DELETE CASCADE;


--
-- Name: workflow_files workflow_files_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_files
    ADD CONSTRAINT workflow_files_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: workflow_files workflow_files_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_files
    ADD CONSTRAINT workflow_files_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: workflow_node_approvers workflow_node_approvers_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_node_approvers
    ADD CONSTRAINT workflow_node_approvers_node_id_fkey FOREIGN KEY (node_id) REFERENCES public.workflow_nodes(id) ON DELETE CASCADE;


--
-- Name: workflow_node_approvers workflow_node_approvers_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_node_approvers
    ADD CONSTRAINT workflow_node_approvers_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: workflow_node_approvers workflow_node_approvers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_node_approvers
    ADD CONSTRAINT workflow_node_approvers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: workflow_nodes workflow_nodes_agent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_nodes
    ADD CONSTRAINT workflow_nodes_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES public.agents(id) ON DELETE RESTRICT;


--
-- Name: workflow_nodes workflow_nodes_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_nodes
    ADD CONSTRAINT workflow_nodes_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: workflow_nodes workflow_nodes_workflow_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_nodes
    ADD CONSTRAINT workflow_nodes_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(id) ON DELETE CASCADE;


--
-- Name: workflow_runs workflow_runs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_runs
    ADD CONSTRAINT workflow_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: workflow_runs workflow_runs_workflow_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflow_runs
    ADD CONSTRAINT workflow_runs_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(id) ON DELETE RESTRICT;


--
-- Name: workflows workflows_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: workflows workflows_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: action_bindings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.action_bindings ENABLE ROW LEVEL SECURITY;

--
-- Name: action_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.action_events ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_kb_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_kb_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: agent_tools; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agent_tools ENABLE ROW LEVEL SECURITY;

--
-- Name: agents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;

--
-- Name: api_integrations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.api_integrations ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_evaluation_criteria; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_evaluation_criteria ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_evaluation_criteria audit_evaluation_criteria_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_evaluation_criteria_tenant_policy ON public.audit_evaluation_criteria USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: audit_evaluation_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_evaluation_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_evaluation_jobs audit_evaluation_jobs_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_evaluation_jobs_tenant_policy ON public.audit_evaluation_jobs USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: audit_evaluations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_evaluations ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_evaluations audit_evaluations_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_evaluations_tenant_policy ON public.audit_evaluations USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: audit_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_events audit_events_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_events_tenant_policy ON public.audit_events USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: audit_payloads; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_payloads ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_payloads audit_payloads_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_payloads_tenant_policy ON public.audit_payloads USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: audit_sessions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_sessions audit_sessions_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_sessions_tenant_policy ON public.audit_sessions USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: audit_spans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_spans ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_spans audit_spans_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY audit_spans_tenant_policy ON public.audit_spans USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: audit_trail; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_trail ENABLE ROW LEVEL SECURITY;

--
-- Name: chat_attachments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chat_attachments ENABLE ROW LEVEL SECURITY;

--
-- Name: chat_attachments chat_attachments_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY chat_attachments_tenant_policy ON public.chat_attachments USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: chat_message_attachments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chat_message_attachments ENABLE ROW LEVEL SECURITY;

--
-- Name: chat_message_attachments chat_message_attachments_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY chat_message_attachments_tenant_policy ON public.chat_message_attachments USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: chat_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: chat_messages chat_messages_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY chat_messages_tenant_policy ON public.chat_messages USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: chat_mutations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chat_mutations ENABLE ROW LEVEL SECURITY;

--
-- Name: chat_mutations chat_mutations_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY chat_mutations_tenant_policy ON public.chat_mutations USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: chat_sessions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: chat_sessions chat_sessions_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY chat_sessions_tenant_policy ON public.chat_sessions USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: departments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;

--
-- Name: kb_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.kb_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: mini_app_databases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.mini_app_databases ENABLE ROW LEVEL SECURITY;

--
-- Name: mini_app_rows; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.mini_app_rows ENABLE ROW LEVEL SECURITY;

--
-- Name: mini_apps; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.mini_apps ENABLE ROW LEVEL SECURITY;

--
-- Name: notifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

--
-- Name: run_node_executions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.run_node_executions ENABLE ROW LEVEL SECURITY;

--
-- Name: run_rollback_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.run_rollback_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: tasks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

--
-- Name: tenant_audit_keys; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tenant_audit_keys ENABLE ROW LEVEL SECURITY;

--
-- Name: tenant_audit_keys tenant_audit_keys_tenant_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_audit_keys_tenant_policy ON public.tenant_audit_keys USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: action_bindings tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.action_bindings USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: action_events tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.action_events USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: agent_kb_documents tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.agent_kb_documents USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: agent_tools tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.agent_tools USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: agents tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.agents USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: api_integrations tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.api_integrations USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: audit_trail tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.audit_trail USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: departments tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.departments USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: kb_documents tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.kb_documents USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: mini_app_databases tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.mini_app_databases USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: mini_app_rows tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.mini_app_rows USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: mini_apps tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.mini_apps USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: notifications tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.notifications USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: run_node_executions tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.run_node_executions USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: run_rollback_requests tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.run_rollback_requests USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: tasks tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.tasks USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: tools tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.tools USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: users tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.users USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: workflow_edges tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.workflow_edges USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: workflow_files tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.workflow_files USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: workflow_node_approvers tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.workflow_node_approvers USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: workflow_nodes tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.workflow_nodes USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: workflow_runs tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.workflow_runs USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: workflows tenant_isolation_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_policy ON public.workflows USING ((tenant_id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((tenant_id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: tenants tenant_isolation_self; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation_self ON public.tenants USING ((id = (current_setting('app.tenant_id'::text))::uuid)) WITH CHECK ((id = (current_setting('app.tenant_id'::text))::uuid));


--
-- Name: tenants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;

--
-- Name: tools; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tools ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_edges; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workflow_edges ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_files; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workflow_files ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_node_approvers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workflow_node_approvers ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_nodes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workflow_nodes ENABLE ROW LEVEL SECURITY;

--
-- Name: workflow_runs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY;

--
-- Name: workflows; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.workflows ENABLE ROW LEVEL SECURITY;

--
-- Name: TABLE action_bindings; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.action_bindings TO vaic_app;


--
-- Name: TABLE action_events; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.action_events TO vaic_app;


--
-- Name: TABLE agent_kb_documents; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.agent_kb_documents TO vaic_app;


--
-- Name: TABLE agent_tools; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.agent_tools TO vaic_app;


--
-- Name: TABLE agents; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.agents TO vaic_app;


--
-- Name: TABLE api_integrations; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.api_integrations TO vaic_app;


--
-- Name: TABLE audit_evaluation_criteria; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.audit_evaluation_criteria TO vaic_app;


--
-- Name: TABLE audit_evaluation_jobs; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.audit_evaluation_jobs TO vaic_app;


--
-- Name: TABLE audit_evaluations; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT ON TABLE public.audit_evaluations TO vaic_app;


--
-- Name: TABLE audit_events; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT ON TABLE public.audit_events TO vaic_app;


--
-- Name: TABLE audit_payloads; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT ON TABLE public.audit_payloads TO vaic_app;


--
-- Name: TABLE audit_sessions; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.audit_sessions TO vaic_app;


--
-- Name: TABLE audit_spans; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.audit_spans TO vaic_app;


--
-- Name: TABLE audit_trail; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT ON TABLE public.audit_trail TO vaic_app;


--
-- Name: TABLE chat_attachments; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.chat_attachments TO vaic_app;


--
-- Name: TABLE chat_message_attachments; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.chat_message_attachments TO vaic_app;


--
-- Name: TABLE chat_messages; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.chat_messages TO vaic_app;


--
-- Name: TABLE chat_mutations; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.chat_mutations TO vaic_app;


--
-- Name: TABLE chat_sessions; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.chat_sessions TO vaic_app;


--
-- Name: TABLE departments; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.departments TO vaic_app;


--
-- Name: TABLE kb_documents; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.kb_documents TO vaic_app;


--
-- Name: TABLE mini_app_databases; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.mini_app_databases TO vaic_app;


--
-- Name: TABLE mini_app_rows; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.mini_app_rows TO vaic_app;


--
-- Name: TABLE mini_apps; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.mini_apps TO vaic_app;


--
-- Name: TABLE notifications; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.notifications TO vaic_app;


--
-- Name: TABLE run_node_executions; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.run_node_executions TO vaic_app;


--
-- Name: TABLE run_rollback_requests; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.run_rollback_requests TO vaic_app;


--
-- Name: TABLE tasks; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.tasks TO vaic_app;


--
-- Name: TABLE tenant_audit_keys; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT ON TABLE public.tenant_audit_keys TO vaic_app;


--
-- Name: TABLE tenants; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.tenants TO vaic_app;


--
-- Name: TABLE tools; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.tools TO vaic_app;


--
-- Name: TABLE users; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.users TO vaic_app;


--
-- Name: TABLE workflow_edges; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.workflow_edges TO vaic_app;


--
-- Name: TABLE workflow_files; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.workflow_files TO vaic_app;


--
-- Name: TABLE workflow_node_approvers; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.workflow_node_approvers TO vaic_app;


--
-- Name: TABLE workflow_nodes; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.workflow_nodes TO vaic_app;


--
-- Name: TABLE workflow_runs; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.workflow_runs TO vaic_app;


--
-- Name: TABLE workflows; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.workflows TO vaic_app;


--
-- PostgreSQL database dump complete
--


