"""Adversarial Tenant Isolation & Server-Side Authorization Tests (Phase 19C).

Verifies the 12 core multi-tenant security invariants:
1. User A cannot list User B's traces.
2. User A cannot access User B's trace by guessing its ID (anti-IDOR 404).
3. User A cannot access another tenant's graph, reconstruction, findings, or investigation.
4. User A cannot search another tenant's failure embeddings.
5. A comparison containing an unauthorized trace is rejected without exposing data.
6. Manipulating query parameters or headers cannot bypass authorized project scoping.
7. WebSocket access and subscription changes reject unauthorized trace/project IDs.
8. Authorized users retain complete access to their own project data.
9. Organization roles ("owner", "admin", "viewer") enforce intended privileges.
10. Missing, invalid, and expired credentials remain strictly rejected (401).
11. Ingestion API keys are prohibited from dashboard read endpoints (403).
12. Project-specific ingestion prevents cross-project trace hijacking (403).
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    ApiKeyModel,
    EventModel,
    FailureEmbeddingModel,
    OrganizationMemberModel,
    OrganizationModel,
    ProjectModel,
    TraceModel,
    UserModel,
)
from app.db.session import get_db
from app.main import app
from app.services.security import security_service

# Valid RFC 4122 UUID constants for test entities
ORG_A_ID = "11111111-0000-0000-0000-000000000001"
ORG_B_ID = "22222222-0000-0000-0000-000000000002"
USER_A1_ID = "aaaaaaaa-0000-0000-0000-000000000001"
USER_A2_ID = "aaaaaaaa-0000-0000-0000-000000000002"
USER_B1_ID = "bbbbbbbb-0000-0000-0000-000000000001"
PROJ_A1_ID = "33333333-0000-0000-0000-000000000001"
PROJ_A2_ID = "33333333-0000-0000-0000-000000000002"
PROJ_B1_ID = "44444444-0000-0000-0000-000000000001"
KEY_A_ID = "55555555-0000-0000-0000-000000000001"
KEY_B_ID = "66666666-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Multi-Tenant Seed Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def multi_tenant_fixture(test_db_session):
    """Seed two distinct organizations with users, projects, traces, events, and failure embeddings."""
    now = datetime.now(timezone.utc)

    # 1. Organization Alpha & Beta
    org_a = OrganizationModel(id=ORG_A_ID, name="Organization Alpha", slug="org-alpha")
    org_b = OrganizationModel(id=ORG_B_ID, name="Organization Beta", slug="org-beta")
    test_db_session.add_all([org_a, org_b])
    await test_db_session.flush()

    # 2. Users:
    # User A1: Owner in Org A
    # User A2: Viewer in Org A
    # User B1: Owner in Org B
    pwd_hash = security_service.hash_password("Password123!")
    user_a1 = UserModel(id=USER_A1_ID, email="a1_owner@alpha.com", hashed_password=pwd_hash, full_name="Alpha Owner")
    user_a2 = UserModel(id=USER_A2_ID, email="a2_viewer@alpha.com", hashed_password=pwd_hash, full_name="Alpha Viewer")
    user_b1 = UserModel(id=USER_B1_ID, email="b1_owner@beta.com", hashed_password=pwd_hash, full_name="Beta Owner")
    test_db_session.add_all([user_a1, user_a2, user_b1])
    await test_db_session.flush()

    # 3. Memberships & Roles
    m_a1 = OrganizationMemberModel(organization_id=org_a.id, user_id=user_a1.id, role="owner")
    m_a2 = OrganizationMemberModel(organization_id=org_a.id, user_id=user_a2.id, role="viewer")
    m_b1 = OrganizationMemberModel(organization_id=org_b.id, user_id=user_b1.id, role="owner")
    test_db_session.add_all([m_a1, m_a2, m_b1])
    await test_db_session.flush()

    # 4. Projects:
    # Org A has Project A1 and Project A2
    # Org B has Project B1
    proj_a1 = ProjectModel(id=PROJ_A1_ID, organization_id=org_a.id, name="Project Alpha One", slug="proj-a1")
    proj_a2 = ProjectModel(id=PROJ_A2_ID, organization_id=org_a.id, name="Project Alpha Two", slug="proj-a2")
    proj_b1 = ProjectModel(id=PROJ_B1_ID, organization_id=org_b.id, name="Project Beta One", slug="proj-b1")
    test_db_session.add_all([proj_a1, proj_a2, proj_b1])
    await test_db_session.flush()

    # 5. Ingestion API keys for Project A1 and Project B1
    raw_key_a = "al_live_alpha11111111111111111111111111111111111111111111"
    raw_key_b = "al_live_beta11111111111111111111111111111111111111111111"
    key_a = ApiKeyModel(
        id=KEY_A_ID,
        project_id=proj_a1.id,
        name="Key Alpha 1",
        key_prefix="al_live_alpha1",
        key_hash=security_service.hash_api_key(raw_key_a),
        key_type="ingestion",
        scopes=["ingest"],
    )
    key_b = ApiKeyModel(
        id=KEY_B_ID,
        project_id=proj_b1.id,
        name="Key Beta 1",
        key_prefix="al_live_beta11",
        key_hash=security_service.hash_api_key(raw_key_b),
        key_type="ingestion",
        scopes=["ingest"],
    )
    test_db_session.add_all([key_a, key_b])
    await test_db_session.flush()

    # 6. Traces:
    # Trace A1 in Project A1
    # Trace A2 in Project A2
    # Trace B1 in Project B1
    tr_a1 = TraceModel(
        trace_id="trace-alpha-001",
        name="Alpha Invoicing Agent",
        project_id=proj_a1.id,
        project_name="Project Alpha One",
        start_time=now - timedelta(minutes=10),
        end_time=now - timedelta(minutes=8),
        status="completed",
        metadata_={"tenant": "alpha"},
    )
    tr_a2 = TraceModel(
        trace_id="trace-alpha-002",
        name="Alpha Payment Agent",
        project_id=proj_a2.id,
        project_name="Project Alpha Two",
        start_time=now - timedelta(minutes=5),
        end_time=now - timedelta(minutes=4),
        status="completed",
        metadata_={"tenant": "alpha"},
    )
    tr_b1 = TraceModel(
        trace_id="trace-beta-001",
        name="Beta Settlement Agent",
        project_id=proj_b1.id,
        project_name="Project Beta One",
        start_time=now - timedelta(minutes=7),
        end_time=now - timedelta(minutes=6),
        status="failed",
        metadata_={"tenant": "beta"},
    )
    test_db_session.add_all([tr_a1, tr_a2, tr_b1])
    await test_db_session.flush()

    # 7. Events for Traces
    ev_a1 = EventModel(
        event_id="ev-alpha-001",
        trace_id=tr_a1.trace_id,
        event_type="AGENT_START",
        timestamp=now - timedelta(minutes=10),
        data={"action": "invoice_start"},
        metadata_={},
    )
    ev_a2 = EventModel(
        event_id="ev-alpha-002",
        trace_id=tr_a2.trace_id,
        event_type="AGENT_START",
        timestamp=now - timedelta(minutes=5),
        data={"action": "payment_start"},
        metadata_={},
    )
    ev_b1 = EventModel(
        event_id="ev-beta-001",
        trace_id=tr_b1.trace_id,
        event_type="AGENT_START",
        timestamp=now - timedelta(minutes=7),
        data={"action": "settle_start"},
        metadata_={},
    )
    ev_b2 = EventModel(
        event_id="ev-beta-002",
        trace_id=tr_b1.trace_id,
        event_type="ERROR",
        timestamp=now - timedelta(minutes=6),
        data={"error": "Database query connection timeout in settlement"},
        metadata_={},
    )
    test_db_session.add_all([ev_a1, ev_a2, ev_b1, ev_b2])
    await test_db_session.flush()

    # 8. Failure Embeddings for Semantic Search Isolation
    emb_vector = [0.1] * 768
    fe_a = FailureEmbeddingModel(
        trace_id=tr_a1.trace_id,
        project_id=proj_a1.id,
        finding_id="finding-alpha-001",
        rule="connection_timeout",
        category="network",
        severity="critical",
        searchable_text="Agent Trace: Alpha Invoicing Agent\nFinding Rule: connection_timeout\nFailure Message: Database query connection timeout occurred",
        embedding=emb_vector,
        metadata_={"message": "Database query connection timeout occurred"},
    )
    fe_b = FailureEmbeddingModel(
        trace_id=tr_b1.trace_id,
        project_id=proj_b1.id,
        finding_id="finding-beta-001",
        rule="connection_timeout",
        category="network",
        severity="critical",
        searchable_text="Agent Trace: Beta Settlement Agent\nFinding Rule: connection_timeout\nFailure Message: Database query connection timeout in settlement",
        embedding=emb_vector,
        metadata_={"message": "Database query connection timeout in settlement"},
    )
    test_db_session.add_all([fe_a, fe_b])
    await test_db_session.flush()

    return {
        "user_a1_token": security_service.create_access_token(user_a1.id, user_a1.email),
        "user_a2_token": security_service.create_access_token(user_a2.id, user_a2.email),
        "user_b1_token": security_service.create_access_token(user_b1.id, user_b1.email),
        "api_key_a": raw_key_a,
        "api_key_b": raw_key_b,
        "tr_a1": tr_a1.trace_id,
        "tr_a2": tr_a2.trace_id,
        "tr_b1": tr_b1.trace_id,
        "proj_a1": proj_a1.id,
        "proj_a2": proj_a2.id,
        "proj_b1": proj_b1.id,
    }


@pytest.fixture
async def client(override_get_db):
    """Async test client matching test_auth.py pattern."""
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test Case 1: Trace Listing Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_a_cannot_list_user_b_traces(client: AsyncClient, multi_tenant_fixture):
    """1. User A lists traces and receives only Alpha traces; User B traces are excluded."""
    res_a = await client.get("/api/v1/traces", headers=_auth(multi_tenant_fixture["user_a1_token"]))
    assert res_a.status_code == 200
    traces_a = res_a.json()
    tids_a = {t["trace_id"] for t in traces_a}

    assert multi_tenant_fixture["tr_a1"] in tids_a
    assert multi_tenant_fixture["tr_a2"] in tids_a
    assert multi_tenant_fixture["tr_b1"] not in tids_a  # STRICT TENANT ISOLATION

    # Symmetrically, User B only sees Beta traces
    res_b = await client.get("/api/v1/traces", headers=_auth(multi_tenant_fixture["user_b1_token"]))
    assert res_b.status_code == 200
    traces_b = res_b.json()
    tids_b = {t["trace_id"] for t in traces_b}

    assert multi_tenant_fixture["tr_b1"] in tids_b
    assert multi_tenant_fixture["tr_a1"] not in tids_b
    assert multi_tenant_fixture["tr_a2"] not in tids_b


# ---------------------------------------------------------------------------
# Test Case 2: Anti-IDOR Resource Existence Protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_trace_by_guessing_id(client: AsyncClient, multi_tenant_fixture):
    """2. Accessing another tenant's trace returns 404 Not Found (same as non-existent)."""
    # Guessing User B's trace ID returns 404
    res_unauth = await client.get(
        f"/api/v1/traces/{multi_tenant_fixture['tr_b1']}",
        headers=_auth(multi_tenant_fixture["user_a1_token"]),
    )
    assert res_unauth.status_code == 404
    assert res_unauth.json()["detail"] == f"Trace '{multi_tenant_fixture['tr_b1']}' not found"

    # Non-existent trace ID returns identical 404 response structure
    res_nonexistent = await client.get(
        "/api/v1/traces/non_existent_trace_9999",
        headers=_auth(multi_tenant_fixture["user_a1_token"]),
    )
    assert res_nonexistent.status_code == 404
    assert res_nonexistent.json()["detail"] == "Trace 'non_existent_trace_9999' not found"


# ---------------------------------------------------------------------------
# Test Case 3: Downstream Read Endpoint Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_a_cannot_access_another_tenant_downstream_endpoints(client: AsyncClient, multi_tenant_fixture):
    """3. User A cannot access User B's execution graph, findings, investigation, or index."""
    tr_b1 = multi_tenant_fixture["tr_b1"]
    headers_a = _auth(multi_tenant_fixture["user_a1_token"])

    # Execution Graph
    res_graph = await client.get(f"/api/v1/traces/{tr_b1}/graph", headers=headers_a)
    assert res_graph.status_code == 404
    assert f"Trace '{tr_b1}' not found" in res_graph.json()["detail"]

    # Trace Findings
    res_findings = await client.get(f"/api/v1/traces/{tr_b1}/findings", headers=headers_a)
    assert res_findings.status_code == 404
    assert f"Trace '{tr_b1}' not found" in res_findings.json()["detail"]

    # AI Root-Cause Investigation
    res_inv = await client.get(f"/api/v1/traces/{tr_b1}/investigation", headers=headers_a)
    assert res_inv.status_code == 404
    assert f"Trace '{tr_b1}' not found" in res_inv.json()["detail"]

    # Re-indexing Trace
    res_index = await client.post(f"/api/v1/traces/{tr_b1}/index", headers=headers_a)
    assert res_index.status_code == 404
    assert f"Trace '{tr_b1}' not found" in res_index.json()["detail"]


# ---------------------------------------------------------------------------
# Test Case 4: Historical Failure Semantic Vector Search Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_a_cannot_search_another_tenant_failure_embeddings(client: AsyncClient, multi_tenant_fixture):
    """4. Vector similarity search returns only findings belonging to authorized projects."""
    query = "Database query connection timeout"

    # User A searches -> only Alpha findings returned
    res_a = await client.get(
        f"/api/v1/failures/search?q={query}",
        headers=_auth(multi_tenant_fixture["user_a1_token"]),
    )
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total_results"] == 1
    assert data_a["results"][0]["trace_id"] == multi_tenant_fixture["tr_a1"]
    assert "Alpha Invoicing Agent" in data_a["results"][0]["searchable_text"]

    # User B searches identical query -> only Beta findings returned
    res_b = await client.get(
        f"/api/v1/failures/search?q={query}",
        headers=_auth(multi_tenant_fixture["user_b1_token"]),
    )
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total_results"] == 1
    assert data_b["results"][0]["trace_id"] == multi_tenant_fixture["tr_b1"]
    assert "Beta Settlement Agent" in data_b["results"][0]["searchable_text"]


# ---------------------------------------------------------------------------
# Test Case 5: Comparison Endpoint Boundary Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comparison_containing_unauthorized_trace_rejected(client: AsyncClient, multi_tenant_fixture):
    """5. Comparing traces across tenant boundaries is rejected without exposing data."""
    tr_a1 = multi_tenant_fixture["tr_a1"]
    tr_a2 = multi_tenant_fixture["tr_a2"]
    tr_b1 = multi_tenant_fixture["tr_b1"]
    headers_a = _auth(multi_tenant_fixture["user_a1_token"])

    # trace_b belongs to tenant B -> rejected
    res1 = await client.get(f"/api/v1/traces/compare?trace_a={tr_a1}&trace_b={tr_b1}", headers=headers_a)
    assert res1.status_code == 404
    assert res1.json()["detail"] == f"Trace '{tr_b1}' not found"

    # trace_a belongs to tenant B -> rejected
    res2 = await client.get(f"/api/v1/traces/compare?trace_a={tr_b1}&trace_b={tr_a1}", headers=headers_a)
    assert res2.status_code == 404
    assert res2.json()["detail"] == f"Trace '{tr_b1}' not found"

    # Comparing two authorized traces of User A succeeds
    res_valid = await client.get(f"/api/v1/traces/compare?trace_a={tr_a1}&trace_b={tr_a2}", headers=headers_a)
    assert res_valid.status_code == 200
    assert res_valid.json()["trace_a"]["trace_id"] == tr_a1
    assert res_valid.json()["trace_b"]["trace_id"] == tr_a2


# ---------------------------------------------------------------------------
# Test Case 6: Parameter Manipulation Cannot Bypass Scoping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parameter_manipulation_cannot_access_unauthorized_project(client: AsyncClient, multi_tenant_fixture):
    """6. Manipulating query parameters or headers cannot leak another tenant's project traces."""
    headers_a = _auth(multi_tenant_fixture["user_a1_token"])
    proj_b1 = multi_tenant_fixture["proj_b1"]

    # Filtering by User B's project ID returns 404 (Anti-IDOR)
    res_query = await client.get(f"/api/v1/traces?project={proj_b1}", headers=headers_a)
    assert res_query.status_code == 404

    # Supplying header X-AgentLens-Project for User B's project returns 404
    res_header = await client.get(
        "/api/v1/traces",
        headers={**headers_a, "X-AgentLens-Project": "proj-b1"},
    )
    assert res_header.status_code == 404

    # Searching failures with User B's project filter returns 404
    res_search = await client.get(
        f"/api/v1/failures/search?q=timeout&project={proj_b1}",
        headers=headers_a,
    )
    assert res_search.status_code == 404


# ---------------------------------------------------------------------------
# Test Case 7: Real-Time WebSocket Authorization & Subscription Protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_websocket_rejects_unauthorized_trace_and_subscription_changes(override_get_db, multi_tenant_fixture):
    """7. WebSocket connection and dynamic subscription changes reject unauthorized traces."""
    app.dependency_overrides[get_db] = override_get_db

    tr_a1 = multi_tenant_fixture["tr_a1"]
    tr_b1 = multi_tenant_fixture["tr_b1"]
    token_a = multi_tenant_fixture["user_a1_token"]
    key_a = multi_tenant_fixture["api_key_a"]

    with TestClient(app) as ws_client:
        # 1. Connecting directly to User B's trace with User A's token is closed before subscription
        with pytest.raises(Exception):
            with ws_client.websocket_connect(f"/api/v1/ws/traces/{tr_b1}?token={token_a}") as ws:
                ws.receive_text()

        # 2. Connecting with Ingestion Key for Project A to trace in Project B is rejected
        with pytest.raises(Exception):
            with ws_client.websocket_connect(f"/api/v1/ws/traces/{tr_b1}?token={key_a}") as ws:
                ws.receive_text()

        # 3. Connecting to authorized trace succeeds and ping/pong works
        with ws_client.websocket_connect(f"/api/v1/ws/traces/{tr_a1}?token={token_a}") as ws:
            ws.send_text("ping")
            assert ws.receive_text() == "pong"

            # Dynamic subscription to User B's trace is rejected
            ws.send_text(json.dumps({"action": "subscribe", "trace_id": tr_b1}))
            sub_resp = json.loads(ws.receive_text())
            assert "error" in sub_resp
            assert f"Trace '{tr_b1}' not found" in sub_resp["error"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test Case 8: Authorized Access Retained
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authorized_user_retains_access_to_own_data(client: AsyncClient, multi_tenant_fixture):
    """8. Authorized users retain complete access to their own projects and traces."""
    tr_a1 = multi_tenant_fixture["tr_a1"]
    headers_a = _auth(multi_tenant_fixture["user_a1_token"])

    # Detail reconstruction
    res_trace = await client.get(f"/api/v1/traces/{tr_a1}", headers=headers_a)
    assert res_trace.status_code == 200
    assert res_trace.json()["trace_id"] == tr_a1

    # Execution Graph
    res_graph = await client.get(f"/api/v1/traces/{tr_a1}/graph", headers=headers_a)
    assert res_graph.status_code == 200
    assert res_graph.json()["trace_id"] == tr_a1

    # Findings
    res_findings = await client.get(f"/api/v1/traces/{tr_a1}/findings", headers=headers_a)
    assert res_findings.status_code == 200


# ---------------------------------------------------------------------------
# Test Case 9: Organization Roles Enforce Permissions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_organization_roles_enforce_intended_permissions(client: AsyncClient, multi_tenant_fixture):
    """9. Organization roles ('owner' vs 'viewer') enforce intended permissions."""
    proj_a1 = multi_tenant_fixture["proj_a1"]
    headers_owner = _auth(multi_tenant_fixture["user_a1_token"])
    headers_viewer = _auth(multi_tenant_fixture["user_a2_token"])

    # 1. Owner can create API keys
    res_create = await client.post(
        f"/api/v1/projects/{proj_a1}/api-keys",
        json={"name": "Owner Key", "expires_in_days": 30},
        headers=headers_owner,
    )
    assert res_create.status_code == 201
    created_key_id = res_create.json()["id"]

    # 2. Viewer can view API key list
    res_list = await client.get(f"/api/v1/projects/{proj_a1}/api-keys", headers=headers_viewer)
    assert res_list.status_code == 200
    assert any(k["id"] == created_key_id for k in res_list.json())

    # 3. Viewer is FORBIDDEN (403) from creating API keys
    res_viewer_create = await client.post(
        f"/api/v1/projects/{proj_a1}/api-keys",
        json={"name": "Viewer Key Attempt"},
        headers=headers_viewer,
    )
    assert res_viewer_create.status_code == 403
    assert "Insufficient permissions" in res_viewer_create.json()["detail"]

    # 4. Viewer is FORBIDDEN (403) from revoking API keys
    res_viewer_del = await client.delete(
        f"/api/v1/projects/{proj_a1}/api-keys/{created_key_id}",
        headers=headers_viewer,
    )
    assert res_viewer_del.status_code == 403

    # 5. Owner can revoke API key
    res_owner_del = await client.delete(
        f"/api/v1/projects/{proj_a1}/api-keys/{created_key_id}",
        headers=headers_owner,
    )
    assert res_owner_del.status_code == 200


# ---------------------------------------------------------------------------
# Test Case 10: Missing, Invalid, Expired Credentials Rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_invalid_expired_credentials_rejected(client: AsyncClient, multi_tenant_fixture):
    """10. Unauthenticated or expired requests are strictly rejected with 401."""
    # Missing credentials
    res_missing = await client.get("/api/v1/traces")
    assert res_missing.status_code == 401

    # Malformed token
    res_malformed = await client.get("/api/v1/traces", headers={"Authorization": "Bearer not_a_jwt"})
    assert res_malformed.status_code == 401

    # Expired token
    expired_token = security_service.create_access_token(
        user_id=USER_A1_ID,
        email="a1_owner@alpha.com",
        expires_delta=timedelta(seconds=-10),
    )
    res_expired = await client.get("/api/v1/traces", headers=_auth(expired_token))
    assert res_expired.status_code == 401


# ---------------------------------------------------------------------------
# Test Case 11: Ingestion API Keys Blocked on Dashboard Read Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_api_keys_cannot_access_dashboard_read_endpoints(client: AsyncClient, multi_tenant_fixture):
    """11. Ingestion API keys (Channel 2) cannot access dashboard read endpoints (403)."""
    key_headers = {"Authorization": f"Bearer {multi_tenant_fixture['api_key_a']}"}
    tr_a1 = multi_tenant_fixture["tr_a1"]

    # List traces
    res = await client.get("/api/v1/traces", headers=key_headers)
    assert res.status_code == 403

    # Trace detail
    res = await client.get(f"/api/v1/traces/{tr_a1}", headers=key_headers)
    assert res.status_code == 403

    # Execution graph
    res = await client.get(f"/api/v1/traces/{tr_a1}/graph", headers=key_headers)
    assert res.status_code == 403

    # Findings
    res = await client.get(f"/api/v1/traces/{tr_a1}/findings", headers=key_headers)
    assert res.status_code == 403

    # Failure search
    res = await client.get("/api/v1/failures/search?q=timeout", headers=key_headers)
    assert res.status_code == 403

    # Trace compare
    res = await client.get(f"/api/v1/traces/compare?trace_a={tr_a1}&trace_b={tr_a1}", headers=key_headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Test Case 12: Project Ingestion Prevents Cross-Project Hijacking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_specific_ingestion_prevents_trace_hijacking(client: AsyncClient, multi_tenant_fixture):
    """12. Project A ingestion key cannot ingest events into a trace owned by Project B."""
    key_a_headers = {"Authorization": f"Bearer {multi_tenant_fixture['api_key_a']}"}
    tr_b1 = multi_tenant_fixture["tr_b1"]

    event_payload = {
        "event_id": "evt_hijack_attempt_001",
        "trace_id": tr_b1,  # Belongs to Project B!
        "event_type": "TOOL_CALL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {"tool": "malicious_tool"},
        "metadata": {},
    }

    res = await client.post("/api/v1/events", json=[event_payload], headers=key_a_headers)
    assert res.status_code == 403
    assert "belongs to another project" in res.json()["detail"]
