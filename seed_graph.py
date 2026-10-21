"""
seed_graph.py
=============
Seeds the FalkorDB 'CompanyBrain' graph with a rich synthetic engineering
organisation dataset. Also provides an optional helper to ingest real commits
and pull-requests from any public GitHub repository.

Usage:
    python seed_graph.py                          # seed synthetic data
    python seed_graph.py --github owner/repo      # + GitHub ingestion
"""

import os
import sys
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
import httpx
from falkordb import FalkorDB

load_dotenv()

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_db() -> FalkorDB:
    return FalkorDB(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", 6379)),
        password=os.getenv("FALKORDB_PASSWORD") or None,
    )


def get_graph(db: FalkorDB):
    return db.select_graph("CompanyBrain")


# ---------------------------------------------------------------------------
# Synthetic dataset
# ---------------------------------------------------------------------------

DEVELOPERS = [
    {
        "id": "dev_001",
        "name": "Priya Sharma",
        "handle": "@priya",
        "role": "Senior Engineer",
        "status": "active",
    },
    {
        "id": "dev_002",
        "name": "Marcus Chen",
        "handle": "@marcus",
        "role": "Staff Engineer",
        "status": "active",
    },
    {
        "id": "dev_003",
        "name": "Amara Okafor",
        "handle": "@amara",
        "role": "Tech Lead",
        "status": "active",
    },
    {
        "id": "dev_004",
        "name": "Lena Fischer",
        "handle": "@lena",
        "role": "Senior Engineer",
        "status": "active",
    },
    {
        "id": "dev_005",
        "name": "Tariq Hassan",
        "handle": "@tariq",
        "role": "Engineer",
        "status": "active",
    },
    {
        "id": "dev_006",
        "name": "Sofia Reyes",
        "handle": "@sofia",
        "role": "Senior Engineer",
        "status": "active",
    },
]

MODULES = [
    {
        "name": "auth-service",
        "path": "services/auth",
        "criticality": "critical",
        "doc_summary": "Handles JWT issuance, OAuth2 flows, SAML SSO integration, and session management. Used by every other service as the identity gateway.",
    },
    {
        "name": "billing-engine",
        "path": "services/billing",
        "criticality": "critical",
        "doc_summary": "Stripe subscription lifecycle management, prorated upgrades, invoice generation, and dunning logic. Directly tied to revenue recognition.",
    },
    {
        "name": "data-pipeline",
        "path": "pipelines/etl",
        "criticality": "high",
        "doc_summary": "Airflow-based ETL extracting from PostgreSQL, transforming with dbt, and loading into Snowflake data warehouse for analytics.",
    },
    {
        "name": "notification-service",
        "path": "services/notifications",
        "criticality": "high",
        "doc_summary": "Multi-channel notification dispatch (email via SendGrid, SMS via Twilio, push via FCM). Supports templating and user preferences.",
    },
    {
        "name": "api-gateway",
        "path": "infrastructure/gateway",
        "criticality": "critical",
        "doc_summary": "Kong-based API gateway handling rate limiting, request routing, mTLS termination, and API key management for all external clients.",
    },
    {
        "name": "ml-inference",
        "path": "services/ml",
        "criticality": "high",
        "doc_summary": "FastAPI wrapper around ONNX model serving. Handles feature preprocessing, model versioning via MLflow, and async batch inference.",
    },
    {
        "name": "user-profile",
        "path": "services/users",
        "criticality": "medium",
        "doc_summary": "CRUD service for user preferences, avatars, and org membership. Depends on auth-service for identity validation.",
    },
    {
        "name": "audit-log",
        "path": "services/audit",
        "criticality": "medium",
        "doc_summary": "Append-only audit trail using Kafka event streaming. Consumed by billing-engine and auth-service for compliance reporting.",
    },
]

PULL_REQUESTS = [
    {
        "id": "pr_001",
        "title": "feat: Add SAML 2.0 IdP integration to auth-service",
        "summary": "Implements SAML 2.0 assertion parsing and SP metadata generation. Added OneLogin library, XML signature validation, and session binding. Modified JWTIssuer to accept SAML assertions as identity proofs.",
        "merged_days_ago": 5,
        "author": "@priya",
        "reviewers": ["@marcus"],
        "modifies": ["auth-service"],
    },
    {
        "id": "pr_002",
        "title": "fix: OAuth2 PKCE flow token exchange race condition",
        "summary": "Resolved race condition in PKCE code_verifier cache using Redis atomic SETNX. Added integration tests for concurrent token exchange. Fixed 3 production incidents in last month.",
        "merged_days_ago": 12,
        "author": "@priya",
        "reviewers": ["@amara"],
        "modifies": ["auth-service"],
    },
    {
        "id": "pr_003",
        "title": "feat: Stripe webhook idempotency and retry logic",
        "summary": "Added idempotency key management for Stripe webhook processing. Implemented exponential backoff retry queue using Celery. Added subscription pause/resume state machine.",
        "merged_days_ago": 8,
        "author": "@marcus",
        "reviewers": ["@lena"],
        "modifies": ["billing-engine"],
    },
    {
        "id": "pr_004",
        "title": "feat: Prorated billing calculation engine",
        "summary": "Implements mid-cycle plan upgrade/downgrade proration. Uses billing period snapshots stored in PostgreSQL. Integrated with Stripe's upcoming invoice preview API.",
        "merged_days_ago": 20,
        "author": "@marcus",
        "reviewers": ["@priya"],
        "modifies": ["billing-engine", "audit-log"],
    },
    {
        "id": "pr_005",
        "title": "refactor: dbt model performance optimisation",
        "summary": "Replaced sequential dbt model runs with parallelised DAG execution. Added incremental materialisation for large fact tables. Query runtime reduced by 67%.",
        "merged_days_ago": 3,
        "author": "@amara",
        "reviewers": ["@tariq"],
        "modifies": ["data-pipeline"],
    },
    {
        "id": "pr_006",
        "title": "feat: Snowflake dynamic data masking for PII",
        "summary": "Implements column-level security policies for PII fields using Snowflake row access policies. Added masking roles for GDPR compliance.",
        "merged_days_ago": 15,
        "author": "@amara",
        "reviewers": ["@sofia"],
        "modifies": ["data-pipeline"],
    },
    {
        "id": "pr_007",
        "title": "feat: Multi-channel notification template engine",
        "summary": "Built Jinja2-based templating system with channel-specific rendering. Added A/B testing hooks for email subject lines. Integrated user preference filtering.",
        "merged_days_ago": 7,
        "author": "@lena",
        "reviewers": ["@priya"],
        "modifies": ["notification-service"],
    },
    {
        "id": "pr_008",
        "title": "fix: SendGrid batch send 429 rate limit handling",
        "summary": "Added token bucket rate limiter for SendGrid API calls. Implemented dead letter queue for failed sends. Added Prometheus metrics for delivery success rates.",
        "merged_days_ago": 22,
        "author": "@lena",
        "reviewers": ["@marcus"],
        "modifies": ["notification-service"],
    },
    {
        "id": "pr_009",
        "title": "feat: Kong plugin for JWT validation and tenant routing",
        "summary": "Custom Kong Lua plugin extracting tenant_id from JWT claims and routing to tenant-specific backend pools. Added circuit breaker integration.",
        "merged_days_ago": 10,
        "author": "@priya",
        "reviewers": ["@amara"],
        "modifies": ["api-gateway", "auth-service"],
    },
    {
        "id": "pr_010",
        "title": "feat: ONNX model serving with async batching",
        "summary": "Implements dynamic batching for ONNX inference requests using asyncio queues. Batch window of 50ms. Added model warm-up hooks and health check endpoints.",
        "merged_days_ago": 18,
        "author": "@tariq",
        "reviewers": ["@sofia"],
        "modifies": ["ml-inference"],
    },
    {
        "id": "pr_011",
        "title": "feat: MLflow model registry integration",
        "summary": "Added MLflow tracking client for experiment logging and model versioning. Implemented blue-green model deployment via feature flags. Rollback in under 30s.",
        "merged_days_ago": 30,
        "author": "@tariq",
        "reviewers": ["@amara"],
        "modifies": ["ml-inference"],
    },
    {
        "id": "pr_012",
        "title": "feat: User profile org membership and RBAC",
        "summary": "Implemented org-level role-based access control. Added bulk member invitation workflow. Integrated with auth-service for permission enforcement.",
        "merged_days_ago": 6,
        "author": "@sofia",
        "reviewers": ["@lena"],
        "modifies": ["user-profile", "auth-service"],
    },
]

MODULE_DEPENDENCIES = [
    ("api-gateway", "auth-service"),
    ("api-gateway", "billing-engine"),
    ("api-gateway", "ml-inference"),
    ("billing-engine", "audit-log"),
    ("billing-engine", "notification-service"),
    ("auth-service", "audit-log"),
    ("ml-inference", "data-pipeline"),
    ("user-profile", "auth-service"),
    ("user-profile", "notification-service"),
]

FEATURES = [
    {
        "id": "feat_001",
        "name": "SSO Enterprise Login",
        "deadline_days": 3,
        "status": "in_progress",
        "revenue_impact": "$2.4M ARR",
        "requires": ["auth-service", "api-gateway"],
    },
    {
        "id": "feat_002",
        "name": "Usage-Based Billing v2",
        "deadline_days": 7,
        "status": "in_progress",
        "revenue_impact": "$1.8M ARR",
        "requires": ["billing-engine", "data-pipeline"],
    },
    {
        "id": "feat_003",
        "name": "AI-Powered Churn Prediction",
        "deadline_days": 14,
        "status": "in_progress",
        "revenue_impact": "$950K retention",
        "requires": ["ml-inference", "data-pipeline"],
    },
    {
        "id": "feat_004",
        "name": "Smart Notification Campaigns",
        "deadline_days": 21,
        "status": "planned",
        "revenue_impact": "$600K upsell",
        "requires": ["notification-service"],
    },
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def clear_graph(graph) -> None:
    """Delete all nodes and relationships."""
    try:
        graph.query("MATCH (n) DETACH DELETE n")
        print("  ✓ Cleared existing graph data")
    except Exception:
        print("  ✓ Graph was empty — nothing to clear")


def seed_developers(graph) -> None:
    for dev in DEVELOPERS:
        graph.query(
            """
            CREATE (:Developer {
                id: $id, name: $name, handle: $handle,
                role: $role, status: $status
            })
            """,
            dev,
        )
    print(f"  ✓ Created {len(DEVELOPERS)} Developer nodes")


def seed_modules(graph) -> None:
    for mod in MODULES:
        graph.query(
            """
            CREATE (:Module {
                name: $name, path: $path,
                criticality: $criticality, doc_summary: $doc_summary
            })
            """,
            mod,
        )
    print(f"  ✓ Created {len(MODULES)} Module nodes")


def seed_module_dependencies(graph) -> None:
    for src, tgt in MODULE_DEPENDENCIES:
        graph.query(
            """
            MATCH (a:Module {name: $src}), (b:Module {name: $tgt})
            CREATE (a)-[:DEPENDS_ON]->(b)
            """,
            {"src": src, "tgt": tgt},
        )
    print(f"  ✓ Created {len(MODULE_DEPENDENCIES)} DEPENDS_ON edges")


def seed_pull_requests(graph) -> None:
    for pr in PULL_REQUESTS:
        # Create PR node
        graph.query(
            """
            CREATE (:PullRequest {
                id: $id, title: $title,
                summary: $summary, merged_days_ago: $merged_days_ago
            })
            """,
            {
                "id": pr["id"],
                "title": pr["title"],
                "summary": pr["summary"],
                "merged_days_ago": pr["merged_days_ago"],
            },
        )
        # AUTHORED edge
        graph.query(
            """
            MATCH (d:Developer {handle: $handle}), (pr:PullRequest {id: $pr_id})
            CREATE (d)-[:AUTHORED]->(pr)
            """,
            {"handle": pr["author"], "pr_id": pr["id"]},
        )
        # REVIEWED edges
        for reviewer in pr["reviewers"]:
            graph.query(
                """
                MATCH (d:Developer {handle: $handle}), (pr:PullRequest {id: $pr_id})
                CREATE (d)-[:REVIEWED]->(pr)
                """,
                {"handle": reviewer, "pr_id": pr["id"]},
            )
        # MODIFIES edges
        for mod_name in pr["modifies"]:
            graph.query(
                """
                MATCH (pr:PullRequest {id: $pr_id}), (m:Module {name: $mod_name})
                CREATE (pr)-[:MODIFIES]->(m)
                """,
                {"pr_id": pr["id"], "mod_name": mod_name},
            )
    print(f"  ✓ Created {len(PULL_REQUESTS)} PullRequest nodes with AUTHORED/REVIEWED/MODIFIES edges")


def seed_features(graph) -> None:
    for feat in FEATURES:
        graph.query(
            """
            CREATE (:Feature {
                id: $id, name: $name, deadline_days: $deadline_days,
                status: $status, revenue_impact: $revenue_impact
            })
            """,
            {
                "id": feat["id"],
                "name": feat["name"],
                "deadline_days": feat["deadline_days"],
                "status": feat["status"],
                "revenue_impact": feat["revenue_impact"],
            },
        )
        for mod_name in feat["requires"]:
            graph.query(
                """
                MATCH (f:Feature {id: $feat_id}), (m:Module {name: $mod_name})
                CREATE (f)-[:REQUIRES_MODULE]->(m)
                """,
                {"feat_id": feat["id"], "mod_name": mod_name},
            )
    print(f"  ✓ Created {len(FEATURES)} Feature nodes with REQUIRES_MODULE edges")


def seed_graph() -> None:
    print("\n🌱 Seeding FalkorDB 'CompanyBrain' graph...")
    db = get_db()
    graph = get_graph(db)

    clear_graph(graph)
    seed_developers(graph)
    seed_modules(graph)
    seed_module_dependencies(graph)
    seed_pull_requests(graph)
    seed_features(graph)

    print("\n✅ Graph seeded successfully!")
    print(f"   Nodes: {len(DEVELOPERS)} developers, {len(MODULES)} modules,")
    print(f"          {len(PULL_REQUESTS)} pull-requests, {len(FEATURES)} features")
    print(f"   Edges: {len(MODULE_DEPENDENCIES)} DEPENDS_ON chains +")
    print(f"          AUTHORED / REVIEWED / MODIFIES / REQUIRES_MODULE")


# ---------------------------------------------------------------------------
# Optional: GitHub Ingestion
# ---------------------------------------------------------------------------

async def ingest_github_repo(owner: str, repo: str, max_prs: int = 20) -> dict:
    """
    Pull real PR data from a public GitHub repository and insert into FalkorDB.
    Requires GITHUB_TOKEN env var for higher rate limits (optional).
    """
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    db = get_db()
    graph = get_graph(db)

    # Create a synthetic Module for this repo
    repo_module = {
        "name": repo,
        "path": f"github/{owner}/{repo}",
        "criticality": "high",
        "doc_summary": f"Public GitHub repository: {owner}/{repo}",
    }
    graph.query(
        """
        MERGE (:Module {name: $name, path: $path,
               criticality: $criticality, doc_summary: $doc_summary})
        """,
        repo_module,
    )

    ingested = {"prs": 0, "developers": 0}

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # Fetch closed PRs
        resp = await client.get(
            f"{base_url}/pulls",
            params={"state": "closed", "per_page": max_prs, "sort": "updated"},
        )
        if resp.status_code != 200:
            return {"error": f"GitHub API error: {resp.status_code}", **ingested}

        prs = resp.json()
        seen_users = set()

        for pr_data in prs:
            if not pr_data.get("merged_at"):
                continue

            pr_id = f"gh_{owner}_{repo}_{pr_data['number']}"
            author_login = pr_data["user"]["login"]
            author_handle = f"@{author_login}"

            # Upsert developer
            if author_login not in seen_users:
                graph.query(
                    """
                    MERGE (d:Developer {handle: $handle})
                    ON CREATE SET d.id = $id, d.name = $name,
                                  d.role = 'Engineer', d.status = 'active'
                    """,
                    {
                        "handle": author_handle,
                        "id": f"gh_{author_login}",
                        "name": pr_data["user"].get("name") or author_login,
                    },
                )
                seen_users.add(author_login)
                ingested["developers"] += 1

            # Compute merged_days_ago
            merged_at = datetime.fromisoformat(
                pr_data["merged_at"].replace("Z", "+00:00")
            )
            merged_days_ago = (datetime.now(timezone.utc) - merged_at).days

            # Create PR node
            graph.query(
                """
                MERGE (pr:PullRequest {id: $id})
                ON CREATE SET pr.title = $title, pr.summary = $summary,
                              pr.merged_days_ago = $merged_days_ago
                """,
                {
                    "id": pr_id,
                    "title": pr_data["title"][:200],
                    "summary": (pr_data.get("body") or "")[:500],
                    "merged_days_ago": merged_days_ago,
                },
            )

            # Relationships
            graph.query(
                """
                MATCH (d:Developer {handle: $handle}), (pr:PullRequest {id: $pr_id})
                MERGE (d)-[:AUTHORED]->(pr)
                """,
                {"handle": author_handle, "pr_id": pr_id},
            )
            graph.query(
                """
                MATCH (pr:PullRequest {id: $pr_id}), (m:Module {name: $mod_name})
                MERGE (pr)-[:MODIFIES]->(m)
                """,
                {"pr_id": pr_id, "mod_name": repo},
            )
            ingested["prs"] += 1

    print(f"  ✓ Ingested {ingested['prs']} PRs and {ingested['developers']} developers from {owner}/{repo}")
    return ingested


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    seed_graph()

    if "--github" in sys.argv:
        idx = sys.argv.index("--github")
        try:
            owner, repo = sys.argv[idx + 1].split("/")
            print(f"\n🐙 Ingesting GitHub repo: {owner}/{repo}")
            result = asyncio.run(ingest_github_repo(owner, repo))
            print(f"   Ingested: {result}")
        except (IndexError, ValueError):
            print("Usage: python seed_graph.py --github owner/repo")
