"""Adversarial Multi-Tenant Security Tests for MCP Server (Phase 19E).

Verifies strict tenant isolation across all Model Context Protocol (MCP) tools:
1. Missing credentials are rejected (401 unauthorized).
2. Invalid, expired, and revoked credentials are rejected.
3. Project Alpha credential cannot read Project Beta traces (404 trace_not_found).
4. Trace IDs from another project are rejected by every relevant tool.
5. Cross-project trace comparisons are rejected without exposing data.
6. Historical failure search cannot return another project's findings or embeddings.
7. Tool arguments cannot override the authenticated project (403 forbidden).
8. Unauthorized requests do not leak trace existence, payloads, or internal credentials (Anti-IDOR).
9. Valid credentials continue to access their own project's data.
10. Ingestion-only credentials (scopes=['ingest']) cannot access MCP read tools (403 forbidden).
11. MCP failures and logs never disclose raw API keys, JWTs, or sensitive configuration.
12. Compatibility with existing MCP protocol clients (mcp_server.call_tool).
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
import uuid
from typing import Any, Dict
from unittest.mock import patch

from pydantic import ValidationError
import pytest

from app.config import settings
from app.db.models import (
    DEFAULT_PROJECT_ID,
    EventModel,
    FailureEmbeddingModel,
    OrganizationModel,
    ProjectModel,
    TraceModel,
)
from app.db.repositories import (
    ApiKeyRepository,
    FailureEmbeddingRepository,
    OrganizationRepository,
    ProjectRepository,
    TraceRepository,
)
from app.mcp.auth import get_mcp_api_key, mcp_api_key_context, set_mcp_api_key
from app.models.auth import ApiKeyCreateRequest
from app.mcp.server import create_mcp_server, mcp_server
from app.mcp.tools import (
    compare_traces_handler,
    get_execution_graph_handler,
    get_trace_findings_handler,
    get_trace_handler,
    investigate_trace_handler,
    list_recent_traces_handler,
    search_historical_failures_handler,
    set_session_factory,
)
from app.models.event import EventType
from app.services.security import security_service


@pytest.fixture
async def mcp_tenant_fixture(test_db_session):
    """Set up two distinct tenant organizations, projects, API keys, and traces."""
    @asynccontextmanager
    async def factory():
        yield test_db_session

    set_session_factory(factory)

    org_repo = OrganizationRepository(test_db_session)
    proj_repo = ProjectRepository(test_db_session)
    key_repo = ApiKeyRepository(test_db_session)

    # 1. Create two separate organizations
    org_alpha = await org_repo.create(name="Alpha Corp", slug="alpha-corp")
    org_beta = await org_repo.create(name="Beta Corp", slug="beta-corp")

    # 2. Create projects in each organization
    proj_alpha = await proj_repo.create(
        organization_id=org_alpha.id,
        name="Project Alpha",
        slug="project-alpha",
        description="Alpha project workspace",
    )
    proj_beta = await proj_repo.create(
        organization_id=org_beta.id,
        name="Project Beta",
        slug="project-beta",
        description="Beta project workspace",
    )

    # 3. Create API keys
    # Alpha MCP key
    raw_key_alpha, prefix_a, hash_a = security_service.generate_ingestion_api_key()
    key_alpha = await key_repo.create(
        project_id=proj_alpha.id,
        name="Alpha MCP Key",
        key_prefix=prefix_a,
        key_hash=hash_a,
        key_type="mcp",
        scopes=["mcp", "read"],
    )

    # Beta MCP key
    raw_key_beta, prefix_b, hash_b = security_service.generate_ingestion_api_key()
    key_beta = await key_repo.create(
        project_id=proj_beta.id,
        name="Beta MCP Key",
        key_prefix=prefix_b,
        key_hash=hash_b,
        key_type="mcp",
        scopes=["mcp", "read"],
    )

    # Ingestion-only key for Alpha (strictly prohibited from MCP read tools)
    raw_key_ingest, prefix_ing, hash_ing = security_service.generate_ingestion_api_key()
    key_ingest = await key_repo.create(
        project_id=proj_alpha.id,
        name="Alpha Ingest-Only Key",
        key_prefix=prefix_ing,
        key_hash=hash_ing,
        key_type="ingestion",
        scopes=["ingest"],
    )

    # Expired key for Alpha
    raw_key_expired, prefix_exp, hash_exp = security_service.generate_ingestion_api_key()
    key_expired = await key_repo.create(
        project_id=proj_alpha.id,
        name="Alpha Expired Key",
        key_prefix=prefix_exp,
        key_hash=hash_exp,
        key_type="mcp",
        scopes=["mcp"],
        expires_at=datetime.now(timezone.utc) - timedelta(days=2),
    )

    # Revoked key for Alpha
    raw_key_revoked, prefix_rev, hash_rev = security_service.generate_ingestion_api_key()
    key_revoked = await key_repo.create(
        project_id=proj_alpha.id,
        name="Alpha Revoked Key",
        key_prefix=prefix_rev,
        key_hash=hash_rev,
        key_type="mcp",
        scopes=["mcp"],
    )
    await key_repo.revoke(key_revoked.id)

    # 4. Create traces
    now = datetime.now(timezone.utc)
    trace_a1 = TraceModel(
        trace_id="trace-alpha-001",
        name="Alpha Agent Flow 1",
        project_id=proj_alpha.id,
        project_name=proj_alpha.name,
        start_time=now,
        end_time=now + timedelta(seconds=5),
        status="completed",
        metadata_={"tenant": "alpha"},
    )
    trace_a2 = TraceModel(
        trace_id="trace-alpha-002",
        name="Alpha Agent Flow 2",
        project_id=proj_alpha.id,
        project_name=proj_alpha.name,
        start_time=now,
        end_time=now + timedelta(seconds=8),
        status="failed",
        metadata_={"tenant": "alpha"},
    )
    trace_b1 = TraceModel(
        trace_id="trace-beta-001",
        name="Beta Agent Flow 1",
        project_id=proj_beta.id,
        project_name=proj_beta.name,
        start_time=now,
        end_time=now + timedelta(seconds=12),
        status="completed",
        metadata_={"tenant": "beta", "confidential": "secret-beta-plan"},
    )

    test_db_session.add_all([trace_a1, trace_a2, trace_b1])
    await test_db_session.flush()

    # 5. Create Events for traces
    ev_a1 = EventModel(
        event_id="ev-alpha-start",
        trace_id=trace_a1.trace_id,
        event_type="AGENT_START",
        timestamp=now,
        data={"query": "process invoice", "token": "alpha-secret-tok"},
        metadata_={},
    )
    ev_a2 = EventModel(
        event_id="ev-alpha-end",
        trace_id=trace_a1.trace_id,
        parent_event_id="ev-alpha-start",
        event_type="AGENT_END",
        timestamp=now + timedelta(seconds=5),
        data={"status": "success"},
        metadata_={},
    )
    ev_b1 = EventModel(
        event_id="ev-beta-start",
        trace_id=trace_b1.trace_id,
        event_type="AGENT_START",
        timestamp=now,
        data={"query": "classified beta task", "api_key": "beta-raw-key-secret"},
        metadata_={},
    )
    test_db_session.add_all([ev_a1, ev_a2, ev_b1])
    await test_db_session.flush()

    # 6. Create Failure Embeddings
    emb_repo = FailureEmbeddingRepository(test_db_session)
    vector_a = [0.1] * 768
    vector_b = [0.9] * 768

    await emb_repo.upsert(
        trace_id=trace_a1.trace_id,
        finding_id="finding-alpha-err",
        rule="explicit_error",
        category="error",
        severity="error",
        searchable_text="Alpha connection timeout",
        embedding=vector_a,
        metadata={"project_name": proj_alpha.name},
        project_id=proj_alpha.id,
    )
    await emb_repo.upsert(
        trace_id=trace_b1.trace_id,
        finding_id="finding-beta-err",
        rule="explicit_error",
        category="error",
        severity="critical",
        searchable_text="Beta critical nuclear shutdown failure",
        embedding=vector_b,
        metadata={"project_name": proj_beta.name},
        project_id=proj_beta.id,
    )
    await test_db_session.commit()

    fixtures_data = {
        "org_alpha": org_alpha,
        "org_beta": org_beta,
        "proj_alpha": proj_alpha,
        "proj_beta": proj_beta,
        "key_alpha": raw_key_alpha,
        "key_beta": raw_key_beta,
        "key_ingest_only": raw_key_ingest,
        "key_expired": raw_key_expired,
        "key_revoked": raw_key_revoked,
        "trace_a1": trace_a1,
        "trace_a2": trace_a2,
        "trace_b1": trace_b1,
    }

    yield fixtures_data

    set_mcp_api_key(None)
    set_session_factory(None)


# ==============================================================================
# 1. Missing credentials are rejected
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_missing_credentials_rejected(mcp_tenant_fixture):
    """MCP tools reject requests when credentials are completely missing."""
    set_mcp_api_key(None)
    with patch.dict("os.environ", {}, clear=True):
        res1 = await get_trace_handler("trace-alpha-001")
        assert res1["error"] == "unauthorized"
        assert "authentication required" in res1["message"].lower()

        res2 = await get_execution_graph_handler("trace-alpha-001")
        assert res2["error"] == "unauthorized"

        res3 = await get_trace_findings_handler("trace-alpha-001")
        assert res3["error"] == "unauthorized"

        res4 = await investigate_trace_handler("trace-alpha-001")
        assert res4["error"] == "unauthorized"

        res5 = await compare_traces_handler("trace-alpha-001", "trace-alpha-002")
        assert res5["error"] == "unauthorized"

        res6 = await search_historical_failures_handler("timeout")
        assert res6["error"] == "unauthorized"

        res7 = await list_recent_traces_handler()
        assert res7["error"] == "unauthorized"


# ==============================================================================
# 2. Invalid, expired, and revoked credentials are rejected
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_invalid_credentials_rejected(mcp_tenant_fixture):
    """MCP tools reject invalid, unhashed, or fabricated credentials."""
    set_mcp_api_key("al_live_invalid_fabricated_secret_key")
    res = await get_trace_handler("trace-alpha-001")
    assert res["error"] == "unauthorized"
    assert "invalid or revoked" in res["message"].lower()


@pytest.mark.asyncio
async def test_mcp_expired_credentials_rejected(mcp_tenant_fixture):
    """MCP tools reject expired credentials."""
    set_mcp_api_key(mcp_tenant_fixture["key_expired"])
    res = await get_trace_handler("trace-alpha-001")
    assert res["error"] == "unauthorized"
    assert "expired" in res["message"].lower()


@pytest.mark.asyncio
async def test_mcp_revoked_credentials_rejected(mcp_tenant_fixture):
    """MCP tools reject revoked credentials."""
    set_mcp_api_key(mcp_tenant_fixture["key_revoked"])
    res = await get_trace_handler("trace-alpha-001")
    assert res["error"] == "unauthorized"
    assert "invalid or revoked" in res["message"].lower()


@pytest.mark.asyncio
async def test_mcp_production_environment_rejects_legacy_dev_key(mcp_tenant_fixture):
    """In production environment, legacy dev keys are strictly rejected."""
    set_mcp_api_key("test_api_key_123")
    with patch.object(settings, "environment", "production"):
        res = await get_trace_handler("trace-alpha-001")
        assert res["error"] == "unauthorized"
        assert "invalid" in res["message"].lower()


# ==============================================================================
# 3. Project Alpha credential cannot read Project Beta traces
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_alpha_cannot_read_beta_trace(mcp_tenant_fixture):
    """Project Alpha credential cannot read Project Beta trace details."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])
    res = await get_trace_handler("trace-beta-001")
    assert res["error"] == "trace_not_found"
    assert "trace 'trace-beta-001' not found" in res["message"].lower()


# ==============================================================================
# 4. Trace IDs from another project are rejected by every relevant tool
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_cross_project_trace_rejected_by_all_tools(mcp_tenant_fixture):
    """Every trace inspection tool rejects a trace belonging to another tenant."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])
    beta_trace_id = "trace-beta-001"

    # Tool 1: get_trace
    t1 = await get_trace_handler(beta_trace_id)
    assert t1["error"] == "trace_not_found"

    # Tool 2: get_execution_graph
    t2 = await get_execution_graph_handler(beta_trace_id)
    assert t2["error"] == "trace_not_found"

    # Tool 3: get_trace_findings
    t3 = await get_trace_findings_handler(beta_trace_id)
    assert t3["error"] == "trace_not_found"

    # Tool 4: investigate_trace
    t4 = await investigate_trace_handler(beta_trace_id)
    assert t4["error"] == "trace_not_found"


# ==============================================================================
# 5. Cross-project trace comparisons are rejected
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_cross_project_comparison_rejected(mcp_tenant_fixture):
    """compare_traces rejects cross-tenant comparisons without disclosing data."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])

    # Alpha vs Beta (Beta unauthorized)
    res1 = await compare_traces_handler("trace-alpha-001", "trace-beta-001")
    assert res1["error"] == "trace_not_found"
    assert "trace-beta-001" in res1["message"]

    # Beta vs Alpha (Beta unauthorized)
    res2 = await compare_traces_handler("trace-beta-001", "trace-alpha-001")
    assert res2["error"] == "trace_not_found"
    assert "trace-beta-001" in res2["message"]

    # Beta vs Beta (caller lacks access to Beta)
    res3 = await compare_traces_handler("trace-beta-001", "trace-beta-001")
    # Identical traces are rejected before lookup, or rejected with trace_not_found
    assert res3["error"] in ("invalid_parameter", "trace_not_found")


# ==============================================================================
# 6. Failure search cannot return another project's findings or embeddings
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_failure_search_strictly_scoped_to_tenant(mcp_tenant_fixture):
    """search_historical_failures strictly confines vector queries to authorized project."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])

    res = await search_historical_failures_handler(query="error failure shutdown", limit=10)
    assert "results" in res
    results = res["results"]

    # Must contain only Alpha failures, Beta failure must NOT be returned
    returned_trace_ids = [r["trace_id"] for r in results]
    assert "trace-alpha-001" in returned_trace_ids
    assert "trace-beta-001" not in returned_trace_ids

    for item in results:
        assert item["trace_id"] != "trace-beta-001"
        assert "nuclear" not in item["message"].lower()


# ==============================================================================
# 7. Tool arguments cannot override the authenticated project
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_tool_arguments_cannot_override_project(mcp_tenant_fixture):
    """Tool arguments attempting to access another project ID or slug are rejected."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])
    proj_beta = mcp_tenant_fixture["proj_beta"]

    # In list_recent_traces with project=beta_id
    res_list1 = await list_recent_traces_handler(project=proj_beta.id)
    assert res_list1["error"] == "forbidden"
    assert "cannot override" in res_list1["message"].lower()

    # In list_recent_traces with project=beta_slug
    res_list2 = await list_recent_traces_handler(project=proj_beta.slug)
    assert res_list2["error"] == "forbidden"

    # In search_historical_failures with project=beta_id
    res_search1 = await search_historical_failures_handler("error", project=proj_beta.id)
    assert res_search1["error"] == "forbidden"

    # In search_historical_failures with project=beta_name
    res_search2 = await search_historical_failures_handler("error", project=proj_beta.name)
    assert res_search2["error"] == "forbidden"


# ==============================================================================
# 8. Unauthorized requests do not leak trace existence or payloads (Anti-IDOR)
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_anti_idor_uniform_error_responses(mcp_tenant_fixture):
    """Verify that another tenant's trace produces identical error to a non-existent trace."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])

    err_unauthorized_tenant = await get_trace_handler("trace-beta-001")
    err_completely_nonexistent = await get_trace_handler("trace-completely-fictional-999")

    assert err_unauthorized_tenant["error"] == "trace_not_found"
    assert err_completely_nonexistent["error"] == "trace_not_found"

    # Error payload formats match exactly
    assert set(err_unauthorized_tenant.keys()) == set(err_completely_nonexistent.keys())
    assert "not found" in err_unauthorized_tenant["message"].lower()
    assert "not found" in err_completely_nonexistent["message"].lower()

    # Verify no confidential payload or project metadata leaked
    res_json = json.dumps(err_unauthorized_tenant)
    assert "secret-beta-plan" not in res_json
    assert "Beta" not in res_json


# ==============================================================================
# 9. Valid credentials continue to access own project's data
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_valid_credentials_access_own_project_data(mcp_tenant_fixture):
    """Valid credentials successfully access own project's traces, graphs, and findings."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])

    # 1. get_trace
    t1 = await get_trace_handler("trace-alpha-001")
    assert t1["trace_id"] == "trace-alpha-001"
    assert t1["project_name"] == "Project Alpha"
    assert len(t1["events"]) == 2

    # 2. get_execution_graph
    graph = await get_execution_graph_handler("trace-alpha-001")
    assert graph["trace_id"] == "trace-alpha-001"
    assert graph["node_count"] == 2

    # 3. get_trace_findings
    findings = await get_trace_findings_handler("trace-alpha-001")
    assert findings["trace_id"] == "trace-alpha-001"

    # 4. compare_traces within same tenant
    comp = await compare_traces_handler("trace-alpha-001", "trace-alpha-002")
    assert comp["trace_a"]["trace_id"] == "trace-alpha-001"
    assert comp["trace_b"]["trace_id"] == "trace-alpha-002"

    # 5. list_recent_traces
    trace_list = await list_recent_traces_handler()
    assert trace_list["total"] >= 2
    listed_ids = [t["trace_id"] for t in trace_list["traces"]]
    assert "trace-alpha-001" in listed_ids
    assert "trace-alpha-002" in listed_ids
    assert "trace-beta-001" not in listed_ids


# ==============================================================================
# 10. Ingestion-only credentials cannot access MCP read tools
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_ingestion_only_key_rejected(mcp_tenant_fixture):
    """API key with only scopes=['ingest'] is rejected with 403 forbidden."""
    set_mcp_api_key(mcp_tenant_fixture["key_ingest_only"])

    res1 = await get_trace_handler("trace-alpha-001")
    assert res1["error"] == "forbidden"
    assert "ingestion-only" in res1["message"].lower()

    res2 = await list_recent_traces_handler()
    assert res2["error"] == "forbidden"

    res3 = await search_historical_failures_handler("error")
    assert res3["error"] == "forbidden"


# ==============================================================================
# 11. MCP failures and logs never disclose raw API keys or secrets
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_redacts_secrets_in_event_data_and_errors(mcp_tenant_fixture):
    """Event payloads and error responses redact secret tokens."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])

    t1 = await get_trace_handler("trace-alpha-001")
    event_data = t1["events"][0]["data"]

    # In ev_a1: data was {"query": "process invoice", "token": "alpha-secret-tok"}
    assert event_data["token"] == "[REDACTED]"
    assert event_data["query"] == "process invoice"


# ==============================================================================
# 12. Existing MCP functionality remains compatible with supported clients
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_protocol_server_call_tool_compatibility(mcp_tenant_fixture):
    """The MCPServer protocol interface (call_tool) functions properly with tenant scoping."""
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])

    # Valid invocation via mcp_server.call_tool
    res_raw = await mcp_server.call_tool("get_trace", {"trace_id": "trace-alpha-001"})
    assert res_raw is not None
    assert len(res_raw.content) >= 1
    content_a = res_raw.content[0].text
    parsed_a = json.loads(content_a)
    assert parsed_a["trace_id"] == "trace-alpha-001"
    assert parsed_a["project_name"] == "Project Alpha"

    # Cross-tenant attempt via mcp_server.call_tool
    res_beta = await mcp_server.call_tool("get_trace", {"trace_id": "trace-beta-001"})
    assert res_beta is not None
    assert len(res_beta.content) >= 1
    content_b = res_beta.content[0].text
    parsed_b = json.loads(content_b)
    assert parsed_b["error"] == "trace_not_found"
    assert "not found" in parsed_b["message"].lower()


# ==============================================================================
# 13. Resource template tenant isolation (agentlens://traces/{trace_id})
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_resource_template_tenant_isolation(mcp_tenant_fixture):
    """Reading trace resource template verifies caller project ownership."""
    # 1. Valid read for own trace
    set_mcp_api_key(mcp_tenant_fixture["key_alpha"])
    res_contents = await mcp_server.read_resource("agentlens://traces/trace-alpha-001")
    assert len(res_contents) >= 1
    parsed_own = json.loads(res_contents[0].content)
    assert parsed_own["trace_id"] == "trace-alpha-001"
    assert parsed_own["project_name"] == "Project Alpha"

    # 2. Cross-tenant read returns trace_not_found (Anti-IDOR)
    res_cross = await mcp_server.read_resource("agentlens://traces/trace-beta-001")
    assert len(res_cross) >= 1
    parsed_cross = json.loads(res_cross[0].content)
    assert parsed_cross["error"] == "trace_not_found"
    assert "not found" in parsed_cross["message"].lower()

    # 3. Ingestion-only key rejected with forbidden
    set_mcp_api_key(mcp_tenant_fixture["key_ingest_only"])
    res_ingest = await mcp_server.read_resource("agentlens://traces/trace-alpha-001")
    assert len(res_ingest) >= 1
    parsed_ingest = json.loads(res_ingest[0].content)
    assert parsed_ingest["error"] == "forbidden"

    # 4. Unauthenticated read rejected with unauthorized
    set_mcp_api_key(None)
    with patch.dict("os.environ", {}, clear=True):
        res_unauth = await mcp_server.read_resource("agentlens://traces/trace-alpha-001")
        assert len(res_unauth) >= 1
        parsed_unauth = json.loads(res_unauth[0].content)
        assert parsed_unauth["error"] == "unauthorized"


# ==============================================================================
# 14. Asynchronous and concurrent context isolation
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_concurrent_context_isolation(mcp_tenant_fixture):
    """Concurrent asyncio tasks with different tenant credentials remain strictly isolated."""
    key_alpha = mcp_tenant_fixture["key_alpha"]
    key_beta = mcp_tenant_fixture["key_beta"]

    async def run_alpha_worker(worker_id: int):
        async with mcp_api_key_context(key_alpha):
            await asyncio.sleep(0.01)
            # Alpha reading Alpha trace -> must succeed
            res_a = await get_trace_handler("trace-alpha-001")
            assert res_a.get("trace_id") == "trace-alpha-001"

            # Alpha reading Beta trace -> must fail with trace_not_found
            res_b = await get_trace_handler("trace-beta-001")
            assert res_b.get("error") == "trace_not_found"

    async def run_beta_worker(worker_id: int):
        async with mcp_api_key_context(key_beta):
            await asyncio.sleep(0.01)
            # Beta reading Beta trace -> must succeed
            res_b = await get_trace_handler("trace-beta-001")
            assert res_b.get("trace_id") == "trace-beta-001"

            # Beta reading Alpha trace -> must fail with trace_not_found
            res_a = await get_trace_handler("trace-alpha-001")
            assert res_a.get("error") == "trace_not_found"

    # Interleave 10 Alpha workers and 10 Beta workers concurrently
    tasks = []
    for i in range(10):
        tasks.append(run_alpha_worker(i))
        tasks.append(run_beta_worker(i))

    await asyncio.gather(*tasks)


# ==============================================================================
# 15. Scope allowlist and privilege escalation prevention
# ==============================================================================


def test_api_key_scope_allowlist_validation():
    """ApiKeyCreateRequest rejects invalid scopes, wildcards, and unknown key types."""
    # 1. Valid configurations
    req_valid = ApiKeyCreateRequest(name="Valid Key", scopes=["mcp", "read"], key_type="mcp")
    assert req_valid.scopes == ["mcp", "read"]
    assert req_valid.key_type == "mcp"

    # 2. Reject privilege-escalating or unsupported scope
    with pytest.raises(ValidationError) as exc1:
        ApiKeyCreateRequest(name="Bad Key", scopes=["admin"])
    assert "unsupported scope" in str(exc1.value).lower()

    # 3. Reject wildcard scope
    with pytest.raises(ValidationError) as exc2:
        ApiKeyCreateRequest(name="Wildcard Key", scopes=["*"])
    assert "unsupported scope" in str(exc2.value).lower()

    # 4. Reject unsupported key_type
    with pytest.raises(ValidationError) as exc3:
        ApiKeyCreateRequest(name="Bad Type", key_type="superuser")
    assert "unsupported key_type" in str(exc3.value).lower()

    # 5. Reject empty scopes list
    with pytest.raises(ValidationError) as exc4:
        ApiKeyCreateRequest(name="Empty Scopes", scopes=[])
    assert "must not be empty" in str(exc4.value).lower()
