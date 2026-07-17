"""Story 2.3 — provider catalog endpoint + PATCH persistence of `model` /
`system_prompt` (AC1, AC4, AC8, AC9).

Test plan (AC # -> test name):
- AC1  GET /agents/providers lists Anthropic configured, others not
       -> test_get_providers_lists_anthropic_configured_others_not
- AC4  PATCH persists {provider, model_name, parameters} as data
       -> test_patch_persists_model_ref
- AC8  PATCH persists system_prompt
       -> test_patch_persists_system_prompt
- AC9  Saving an unconfigured provider (openai) succeeds at config time
       -> test_patch_accepts_unconfigured_provider_at_config_time
- T2.2 Unknown provider id is rejected
       -> test_patch_rejects_unknown_provider_id
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_agent(
    client: TestClient, token: str, *, department_id: str, name: str = "Support Bot"
) -> dict[str, Any]:
    r = client.post(
        "/agents",
        json={
            "name": name,
            "department_id": department_id,
            "system_prompt": "You are a helpful assistant.",
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# AC1 — GET /agents/providers
# ---------------------------------------------------------------------------


def test_get_providers_lists_anthropic_configured_others_not(
    agent_client: TestClient, agent_seed_data: dict[str, Any], monkeypatch
) -> None:
    from app.core.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("VAIC_ANTHROPIC_API_KEY", "sk-ant-test-key")
    get_settings.cache_clear()
    try:
        token = login_token(agent_client, "builder@tenantc.example")
        r = agent_client.get("/agents/providers", headers=_auth_headers(token))
        assert r.status_code == 200, r.text
        by_id = {p["id"]: p for p in r.json()["data"]}
        assert by_id["anthropic"]["configured"] is True
        assert len(by_id["anthropic"]["models"]) >= 1
        for provider_id in ("openai", "google", "ollama"):
            assert by_id[provider_id]["configured"] is False
            assert by_id[provider_id]["models"] == []
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# AC4 — PATCH persists {provider, model_name, parameters} as data
# ---------------------------------------------------------------------------


def test_patch_persists_model_ref(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    model_ref = {
        "provider": "anthropic",
        "model_name": "claude-sonnet-4-5",
        "parameters": {"temperature": 0.7, "max_tokens": 2048},
    }
    r = agent_client.patch(
        f"/agents/{created['id']}",
        json={"model": model_ref},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["model"] == model_ref

    r_get = agent_client.get(f"/agents/{created['id']}", headers=_auth_headers(token))
    assert r_get.json()["data"]["model"] == model_ref


# ---------------------------------------------------------------------------
# AC8 — PATCH persists system_prompt
# ---------------------------------------------------------------------------


def test_patch_persists_system_prompt(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    new_prompt = "You are a specialist in {{tool:rag.search}} and {{kb:agent_id}}."
    r = agent_client.patch(
        f"/agents/{created['id']}",
        json={"system_prompt": new_prompt},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["system_prompt"] == new_prompt


# ---------------------------------------------------------------------------
# AC9 — unconfigured provider accepted at config time
# ---------------------------------------------------------------------------


def test_patch_accepts_unconfigured_provider_at_config_time(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    """Saving provider="openai" (a placeholder, always unconfigured) must
    succeed — the failure only surfaces at run time (FR-5 consequence)."""
    token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    r = agent_client.patch(
        f"/agents/{created['id']}",
        json={"model": {"provider": "openai", "model_name": "gpt-4o", "parameters": {}}},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["model"]["provider"] == "openai"


def test_patch_rejects_unknown_provider_id(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    r = agent_client.patch(
        f"/agents/{created['id']}",
        json={"model": {"provider": "not-a-real-provider", "model_name": "x", "parameters": {}}},
        headers=_auth_headers(token),
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "unknown_provider"
