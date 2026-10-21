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
# Optional: GitHub Ingestion — Rich Sub-Module Partitioning
# ---------------------------------------------------------------------------

# Keyword → sub-module suffix mapping (order matters: first match wins)
_MODULE_KEYWORD_MAP = [
    (["auth", "oauth", "jwt", "login", "session", "sso", "token", "saml", "permission", "role", "rbac"], "auth"),
    (["api", "route", "endpoint", "request", "response", "handler", "middleware", "gateway", "proxy", "rest", "graphql"], "api"),
    (["cli", "command", "terminal", "shell", "script", "argparse", "click", "typer"], "cli"),
    (["test", "spec", "fixture", "mock", "stub", "pytest", "jest", "coverage", "ci", "lint"], "testing"),
    (["core", "engine", "base", "model", "schema", "database", "db", "orm", "migration", "redis", "cache", "store"], "core"),
    (["docs", "readme", "changelog", "document", "wiki", "guide"], "docs"),
    (["ui", "frontend", "component", "react", "vue", "html", "css", "style", "design"], "ui"),
    (["deploy", "docker", "k8s", "kubernetes", "infra", "terraform", "helm", "release", "build", "pipeline", "ci/cd", "github action"], "infra"),
]

def _classify_pr_to_submodule(title: str, body: str, repo: str) -> str:
    """Return a sub-module name for a PR based on its title/body keywords."""
    text = (title + " " + (body or "")).lower()
    for keywords, suffix in _MODULE_KEYWORD_MAP:
        if any(kw in text for kw in keywords):
            return f"{repo}-{suffix}"
    return f"{repo}-core"  # default bucket


async def ingest_github_repo(
    owner: str,
    repo: str,
    max_prs: int = 20,
    clear_existing: bool = True,
) -> dict:
    """
    Pull real PR data from a public GitHub repository and insert into FalkorDB.

    Improvements over the naive version:
      - Optionally clears existing graph so only this repo is shown.
      - Partitions PRs into 4–5 logical sub-modules (core/api/auth/cli/infra/…)
        based on title + body keyword matching.
      - Creates DEPENDS_ON edges: api→core, auth→core, cli→api, infra→core.
      - Creates active Feature nodes linked via REQUIRES_MODULE to each sub-module.
      - Cross-assigns REVIEWED edges from other contributors when GitHub
        requested_reviewers is empty, so Q3 always produces real backup ranks.

    Requires GITHUB_TOKEN env var for higher rate limits (optional but recommended).
    """
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    db = get_db()
    graph = get_graph(db)

    # --- Optionally wipe the existing graph ---
    if clear_existing:
        clear_graph(graph)
        print(f"  ✓ Cleared graph — will show only {owner}/{repo}")

    ingested = {"prs": 0, "developers": 0, "modules": 0, "features": 0}
    seen_users: dict[str, str] = {}   # login → handle
    module_authors: dict[str, list[str]] = {}  # module_name → [handles]
    module_reviewers: dict[str, list[str]] = {}

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # ── Fetch closed (merged) PRs ──────────────────────────────────────
        resp = await client.get(
            f"{base_url}/pulls",
            params={"state": "closed", "per_page": min(max_prs, 100), "sort": "updated"},
        )
        if resp.status_code != 200:
            return {"error": f"GitHub API error: {resp.status_code} — {resp.text[:200]}", **ingested}

        prs = [p for p in resp.json() if p.get("merged_at")]
        if not prs:
            return {"error": "No merged PRs found in this repo.", **ingested}

        # ── Classify PRs into sub-modules ──────────────────────────────────
        # Build a per-PR classification
        pr_module_map: dict[int, str] = {}
        for pr_data in prs:
            submod = _classify_pr_to_submodule(
                pr_data["title"],
                pr_data.get("body") or "",
                repo,
            )
            pr_module_map[pr_data["number"]] = submod

        # Collect all unique sub-modules
        all_submodules = sorted(set(pr_module_map.values()))

        # ── Create sub-module nodes ────────────────────────────────────────
        submod_criticality = {"core": "critical", "auth": "critical", "api": "high",
                               "infra": "high", "testing": "medium", "cli": "medium",
                               "docs": "low", "ui": "medium"}
        for submod_name in all_submodules:
            suffix = submod_name.split("-")[-1]
            crit = submod_criticality.get(suffix, "medium")
            graph.query(
                """
                MERGE (m:Module {name: $name})
                ON CREATE SET m.path = $path, m.criticality = $criticality,
                              m.doc_summary = $doc_summary
                """,
                {
                    "name": submod_name,
                    "path": f"github/{owner}/{repo}/{suffix}",
                    "criticality": crit,
                    "doc_summary": (
                        f"GitHub {owner}/{repo} — {suffix} subsystem. "
                        f"Auto-classified from merged PR title/body keywords."
                    ),
                },
            )
            module_authors[submod_name] = []
            module_reviewers[submod_name] = []
        ingested["modules"] = len(all_submodules)
        print(f"  ✓ Created {len(all_submodules)} sub-module nodes: {all_submodules}")

        # ── DEPENDS_ON edges between sub-modules ──────────────────────────
        # Standard dependency chain: api→core, auth→core, cli→api, infra→core
        core_mod = f"{repo}-core"
        api_mod  = f"{repo}-api"
        auth_mod = f"{repo}-auth"
        cli_mod  = f"{repo}-cli"
        infra_mod = f"{repo}-infra"
        dep_edges = [
            (api_mod,   core_mod),
            (auth_mod,  core_mod),
            (cli_mod,   api_mod),
            (infra_mod, core_mod),
        ]
        dep_count = 0
        for src_mod, tgt_mod in dep_edges:
            if src_mod in all_submodules and tgt_mod in all_submodules:
                graph.query(
                    """
                    MATCH (a:Module {name: $src}), (b:Module {name: $tgt})
                    MERGE (a)-[:DEPENDS_ON]->(b)
                    """,
                    {"src": src_mod, "tgt": tgt_mod},
                )
                dep_count += 1
        if dep_count:
            print(f"  ✓ Created {dep_count} DEPENDS_ON edges between sub-modules")

        # ── Ingest PRs ─────────────────────────────────────────────────────
        for pr_data in prs:
            pr_num = pr_data["number"]
            submod_name = pr_module_map[pr_num]
            pr_id = f"gh_{owner}_{repo}_{pr_num}"
            author_login = pr_data["user"]["login"]
            author_handle = f"@{author_login}"

            # Upsert developer node
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
                seen_users[author_login] = author_handle
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

            # AUTHORED edge
            graph.query(
                """
                MATCH (d:Developer {handle: $handle}), (pr:PullRequest {id: $pr_id})
                MERGE (d)-[:AUTHORED]->(pr)
                """,
                {"handle": author_handle, "pr_id": pr_id},
            )
            module_authors[submod_name].append(author_handle)

            # MODIFIES edge → classified sub-module
            graph.query(
                """
                MATCH (pr:PullRequest {id: $pr_id}), (m:Module {name: $mod_name})
                MERGE (pr)-[:MODIFIES]->(m)
                """,
                {"pr_id": pr_id, "mod_name": submod_name},
            )

            # REVIEWED edges: use requested_reviewers from GitHub payload
            reviewers_from_gh = [
                r["login"]
                for r in pr_data.get("requested_reviewers", [])
                if r.get("login") and r["login"] != author_login
            ]
            for rev_login in reviewers_from_gh:
                rev_handle = f"@{rev_login}"
                # Upsert reviewer developer node
                if rev_login not in seen_users:
                    graph.query(
                        """
                        MERGE (d:Developer {handle: $handle})
                        ON CREATE SET d.id = $id, d.name = $name,
                                      d.role = 'Engineer', d.status = 'active'
                        """,
                        {
                            "handle": rev_handle,
                            "id": f"gh_{rev_login}",
                            "name": rev_login,
                        },
                    )
                    seen_users[rev_login] = rev_handle
                    ingested["developers"] += 1
                graph.query(
                    """
                    MATCH (d:Developer {handle: $handle}), (pr:PullRequest {id: $pr_id})
                    MERGE (d)-[:REVIEWED]->(pr)
                    """,
                    {"handle": rev_handle, "pr_id": pr_id},
                )
                module_reviewers[submod_name].append(rev_handle)

            ingested["prs"] += 1

        # ── Cross-assign REVIEWED edges if requested_reviewers was always empty ──
        # This ensures Q3 (recommend_backup_engineer) always has reviewer data.
        all_handles = list(seen_users.values())
        for submod_name in all_submodules:
            if not module_reviewers[submod_name] and len(all_handles) >= 2:
                authors_for_mod = list(set(module_authors.get(submod_name, [])))
                # Pick contributors who did NOT author PRs on this module
                non_authors = [h for h in all_handles if h not in authors_for_mod]
                if not non_authors:
                    non_authors = [h for h in all_handles if h != authors_for_mod[0]] if authors_for_mod else []

                # Assign up to 2 cross-reviewers to the first PR of this module
                cross_reviewers = non_authors[:2]
                # Get first PR for this module
                result = graph.query(
                    """
                    MATCH (pr:PullRequest)-[:MODIFIES]->(m:Module {name: $mod_name})
                    RETURN pr.id AS pr_id LIMIT 1
                    """,
                    {"mod_name": submod_name},
                )
                if result and result.result_set:
                    first_pr_id = result.result_set[0][0]
                    for rev_handle in cross_reviewers:
                        graph.query(
                            """
                            MATCH (d:Developer {handle: $handle}), (pr:PullRequest {id: $pr_id})
                            MERGE (d)-[:REVIEWED]->(pr)
                            """,
                            {"handle": rev_handle, "pr_id": first_pr_id},
                        )
                        module_reviewers[submod_name].append(rev_handle)

        # ── Feature nodes linked to sub-modules ───────────────────────────
        feature_templates = [
            {
                "name": f"Production Release v2.0",
                "deadline_days": 5,
                "status": "in_progress",
                "revenue_impact": "$1.2M ARR",
                "prefer_suffix": "core",
            },
            {
                "name": f"Core Architecture Scaling",
                "deadline_days": 10,
                "status": "in_progress",
                "revenue_impact": "$800K ARR",
                "prefer_suffix": "api",
            },
            {
                "name": f"Enterprise Security Audit",
                "deadline_days": 14,
                "status": "in_progress",
                "revenue_impact": "$650K compliance",
                "prefer_suffix": "auth",
            },
            {
                "name": f"Developer Experience Overhaul",
                "deadline_days": 21,
                "status": "planned",
                "revenue_impact": "$300K efficiency",
                "prefer_suffix": "cli",
            },
        ]

        feat_id = 1
        for tmpl in feature_templates:
            # Prefer the sub-module matching the feature's domain, fall back to any
            preferred = f"{repo}-{tmpl['prefer_suffix']}"
            feat_module = preferred if preferred in all_submodules else (all_submodules[0] if all_submodules else None)
            if not feat_module:
                continue
            fid = f"gh_feat_{owner}_{repo}_{feat_id}"
            graph.query(
                """
                MERGE (f:Feature {id: $id})
                ON CREATE SET f.name = $name, f.deadline_days = $deadline_days,
                              f.status = $status, f.revenue_impact = $revenue_impact
                """,
                {
                    "id": fid,
                    "name": tmpl["name"],
                    "deadline_days": tmpl["deadline_days"],
                    "status": tmpl["status"],
                    "revenue_impact": tmpl["revenue_impact"],
                },
            )
            graph.query(
                """
                MATCH (f:Feature {id: $feat_id}), (m:Module {name: $mod_name})
                MERGE (f)-[:REQUIRES_MODULE]->(m)
                """,
                {"feat_id": fid, "mod_name": feat_module},
            )
            feat_id += 1
            ingested["features"] = ingested.get("features", 0) + 1

        print(f"  ✓ Created {ingested.get('features', 0)} Feature nodes with REQUIRES_MODULE edges")

    print(
        f"  ✓ Ingested {ingested['prs']} PRs, {ingested['developers']} developers, "
        f"{ingested['modules']} sub-modules from {owner}/{repo}"
    )
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
