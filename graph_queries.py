"""
graph_queries.py
================
The 4 core FalkorDB OpenCypher query functions for BusFactor Zero.

Each function returns a dict with:
  - 'result'  : the query result (list of dicts)
  - 'cypher'  : the exact Cypher string executed (for the UI inspector)
  - 'params'  : parameters passed to the query
"""

import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()


# ---------------------------------------------------------------------------
# DB connection helper
# ---------------------------------------------------------------------------

def get_graph():
    db = FalkorDB(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", 6379)),
        username=os.getenv("FALKORDB_USERNAME") or None,
        password=os.getenv("FALKORDB_PASSWORD") or None,
        ssl=os.getenv("FALKORDB_SSL", "false").lower() == "true",
    )
    return db.select_graph("CompanyBrain")


def _result_to_dicts(result) -> list[dict]:
    """Convert FalkorDB QueryResult to a list of plain dicts."""
    rows = []
    if not result or not result.result_set:
        return rows
    headers = []
    for h in result.header:
        if isinstance(h, (list, tuple)) and len(h) >= 2:
            headers.append(
                h[1].decode("utf-8") if isinstance(h[1], bytes) else str(h[1])
            )
        else:
            headers.append(h.decode("utf-8") if isinstance(h, bytes) else str(h))
    for row in result.result_set:
        record = {}
        for i, header in enumerate(headers):
            val = row[i]
            if hasattr(val, "properties"):
                val = dict(val.properties)
            elif isinstance(val, list):
                cleaned = []
                for item in val:
                    if hasattr(item, "properties"):
                        cleaned.append(dict(item.properties))
                    elif isinstance(item, bytes):
                        cleaned.append(item.decode("utf-8"))
                    else:
                        cleaned.append(item)
                val = cleaned
            elif isinstance(val, bytes):
                val = val.decode("utf-8")
            record[header] = val
        rows.append(record)
    return rows


# ---------------------------------------------------------------------------
# Q1: detect_bus_factor_bottlenecks
# ---------------------------------------------------------------------------
# Checks both PR authorship AND agent-committed SHADOW_ASSIGNED_TO edges.
# When an AgentMemory mitigation is committed in Q4, the module gains a shadow
# maintainer (effective_bus_factor > 1) and is immediately resolved!

BUS_FACTOR_CYPHER = """
MATCH (f:Feature {status: 'in_progress'})-[:REQUIRES_MODULE]->(m:Module)
MATCH (d:Developer)-[:AUTHORED]->(pr:PullRequest)-[:MODIFIES]->(m)
OPTIONAL MATCH (shadow:Developer)-[:SHADOW_ASSIGNED_TO]->(m)
WITH m,
     collect(DISTINCT d.handle) AS authors,
     collect(DISTINCT shadow.handle) AS shadows,
     collect(DISTINCT f.name) AS blocking_features,
     min(f.deadline_days) AS min_deadline_days,
     collect(DISTINCT f.revenue_impact) AS revenue_impacts
WHERE size(authors) = 1 AND size(shadows) = 0
RETURN m.name AS module,
       m.criticality AS criticality,
       m.doc_summary AS doc_summary,
       authors[0] AS sole_expert,
       blocking_features[0] AS blocking_feature,
       blocking_features AS all_blocking_features,
       min_deadline_days AS deadline_days,
       revenue_impacts[0] AS revenue_impact,
       size(authors) AS bus_factor
ORDER BY
  CASE m.criticality
    WHEN 'critical' THEN 0
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    ELSE 3
  END ASC,
  min_deadline_days ASC
""".strip()


def detect_bus_factor_bottlenecks() -> dict:
    """
    Q1 — Find every active Feature whose required Module has only 1 unique PR
    author and 0 agent-assigned shadow maintainers (Bus Factor = 1).
    """
    graph = get_graph()
    result = graph.query(BUS_FACTOR_CYPHER)
    return {
        "cypher": BUS_FACTOR_CYPHER,
        "params": {},
        "result": _result_to_dicts(result),
    }


# ---------------------------------------------------------------------------
# Q2: simulate_developer_unavailable
# ---------------------------------------------------------------------------
# Traverses BOTH incoming and outgoing DEPENDS_ON*1..3 paths to capture the
# true organizational blast radius: services that depend on the compromised
# module (<-[:DEPENDS_ON*1..3]-) AND upstream modules it integrates with.

BLAST_RADIUS_CYPHER = """
MATCH (d:Developer {handle: $dev_handle})
MATCH (d)-[:AUTHORED]->(pr:PullRequest)-[:MODIFIES]->(direct_module:Module)
WITH d, collect(DISTINCT direct_module) AS direct_modules
UNWIND direct_modules AS dm
OPTIONAL MATCH (dependent:Module)-[:DEPENDS_ON*1..3]->(dm)
WHERE NOT (dependent IN direct_modules)
WITH d, direct_modules, collect(DISTINCT dependent) AS cascade_dependents
UNWIND direct_modules AS dm2
OPTIONAL MATCH (dm2)-[:DEPENDS_ON*1..2]->(upstream:Module)
WHERE NOT (upstream IN direct_modules) AND NOT (upstream IN cascade_dependents)
WITH d, direct_modules, cascade_dependents, collect(DISTINCT upstream) AS upstream_deps
WITH d, direct_modules, (cascade_dependents + upstream_deps) AS all_cascade
UNWIND (direct_modules + all_cascade) AS impacted_mod
OPTIONAL MATCH (f:Feature)-[:REQUIRES_MODULE]->(impacted_mod)
WITH d, direct_modules, all_cascade, collect(DISTINCT f) AS blocked_features
RETURN d.name AS developer,
       d.handle AS handle,
       [m IN direct_modules WHERE m IS NOT NULL | m.name] AS directly_compromised,
       [m IN all_cascade WHERE m IS NOT NULL | m.name] AS cascade_compromised,
       [feat IN blocked_features WHERE feat IS NOT NULL | {
           name: feat.name,
           revenue: feat.revenue_impact,
           deadline: feat.deadline_days,
           status: feat.status
       }] AS blocked_features,
       size(direct_modules) + size(all_cascade) AS blast_radius_score
""".strip()


def simulate_developer_unavailable(dev_handle: str) -> dict:
    """
    Q2 — Multi-hop blast-radius traversal. Calculates which modules lose their
    maintainer, which 1-to-3 hop dependent modules cascade into risk, and
    which client features are threatened across the impacted subgraph.
    """
    graph = get_graph()
    params = {"dev_handle": dev_handle}
    result = graph.query(BLAST_RADIUS_CYPHER, params)
    return {
        "cypher": BLAST_RADIUS_CYPHER,
        "params": params,
        "result": _result_to_dicts(result),
    }


# ---------------------------------------------------------------------------
# Q3: recommend_backup_engineer
# ---------------------------------------------------------------------------
# Uses pure OpenCypher scalar projections to avoid Null-Map grouping issues in
# FalkorDB while combining code-review history (+3 pts per PR reviewed) and
# 1..2 hop adjacent module authorship (+1 pt per adjacent PR authored).

BACKUP_ENGINEER_CYPHER = """
MATCH (m:Module {name: $module_name})
MATCH (cand:Developer {status: 'active'})
WHERE cand.handle <> $unavailable_dev
OPTIONAL MATCH (cand)-[:REVIEWED]->(rpr:PullRequest)-[:MODIFIES]->(m)
WITH m, cand, count(DISTINCT rpr) AS review_count
OPTIONAL MATCH (m)-[:DEPENDS_ON*1..2]-(adj:Module)<-[:MODIFIES]-(apr:PullRequest)<-[:AUTHORED]-(cand)
WHERE adj.name <> m.name
WITH m, cand, review_count, count(DISTINCT apr) AS adjacent_pr_count, collect(DISTINCT adj.name) AS adj_modules
OPTIONAL MATCH (cand)-[:AUTHORED]->(cpr:PullRequest)-[:MODIFIES]->(m)
WITH cand, review_count, adjacent_pr_count, adj_modules, count(DISTINCT cpr) AS coauthor_count
WITH cand,
     (coauthor_count * 4) + (review_count * 3) + (adjacent_pr_count * 1) AS proximity_score,
     (CASE WHEN coauthor_count > 0 THEN ['Co-authored PRs on this module'] ELSE [] END) +
     (CASE WHEN review_count > 0 THEN ['Reviewed ' + toString(review_count) + ' PR(s) on this module'] ELSE [] END) +
     (CASE WHEN adjacent_pr_count > 0 THEN ['Maintains adjacent modules: ' + coalesce(adj_modules[0], '')] ELSE [] END) AS reasons
WHERE proximity_score > 0
RETURN cand.name AS recommended_dev,
       cand.handle AS handle,
       cand.role AS role,
       proximity_score,
       reasons
ORDER BY proximity_score DESC, cand.name ASC
LIMIT 3
""".strip()


def recommend_backup_engineer(module_name: str, unavailable_dev_handle: str) -> dict:
    """
    Q3 — Graph collaborative filtering. Ranks active backup engineers by
    weighted graph proximity: co-authors (+4), PR reviewers on the target
    module (+3), and authors of 1-2 hop DEPENDS_ON adjacent modules (+1).
    """
    graph = get_graph()
    params = {
        "module_name": module_name,
        "unavailable_dev": unavailable_dev_handle,
    }
    result = graph.query(BACKUP_ENGINEER_CYPHER, params)
    return {
        "cypher": BACKUP_ENGINEER_CYPHER,
        "params": params,
        "result": _result_to_dicts(result),
    }


# ---------------------------------------------------------------------------
# Q4: commit_agent_handoff_memory
# ---------------------------------------------------------------------------

HANDOFF_MEMORY_CYPHER = """
MATCH (m:Module {name: $module_name})
MATCH (d:Developer {handle: $backup_dev_handle})
CREATE (mem:AgentMemory {
    id: $memory_id,
    timestamp: $timestamp,
    action_type: 'handoff_briefing',
    module_name: $module_name,
    backup_handle: $backup_dev_handle,
    summary: $handoff_summary,
    confidence: $confidence
})
CREATE (mem)-[:MITIGATES_RISK_ON]->(m)
MERGE (d)-[r:SHADOW_ASSIGNED_TO {assigned_by_agent: true}]->(m)
SET r.timestamp = $timestamp, r.memory_id = $memory_id
RETURN mem.id AS memory_id,
       d.name AS backup_dev,
       d.handle AS backup_handle,
       m.name AS module,
       mem.timestamp AS committed_at
""".strip()


def commit_agent_handoff_memory(
    module_name: str,
    backup_dev_handle: str,
    handoff_summary: str,
    confidence: float = 0.92,
) -> dict:
    """
    Q4 — Mutates FalkorDB live. Creates an AgentMemory node containing the
    GraphRAG-generated onboarding briefing and writes a SHADOW_ASSIGNED_TO edge
    between the backup developer and the at-risk module.
    """
    graph = get_graph()
    memory_id = f"mem_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now(timezone.utc).isoformat()

    params = {
        "memory_id": memory_id,
        "timestamp": timestamp,
        "handoff_summary": handoff_summary,
        "confidence": confidence,
        "module_name": module_name,
        "backup_dev_handle": backup_dev_handle,
    }
    result = graph.query(HANDOFF_MEMORY_CYPHER, params)
    return {
        "cypher": HANDOFF_MEMORY_CYPHER,
        "params": {k: v for k, v in params.items() if k != "handoff_summary"},
        "result": _result_to_dicts(result),
        "memory_id": memory_id,
    }


# ---------------------------------------------------------------------------
# Graph visualisation helper
# ---------------------------------------------------------------------------

GRAPH_NODES_CYPHER = "MATCH (n) RETURN n, labels(n) AS labels"
GRAPH_EDGES_CYPHER = "MATCH (a)-[r]->(b) RETURN a, type(r) AS rel_type, b, properties(r) AS rel_props"


def get_full_graph() -> dict:
    """Return all nodes and edges formatted for Vis.js network visualisation."""
    graph = get_graph()

    nodes_result = graph.query(GRAPH_NODES_CYPHER)
    nodes = []
    seen_ids = set()
    if nodes_result and nodes_result.result_set:
        for row in nodes_result.result_set:
            node = row[0]
            labels_val = row[1] if len(row) > 1 else []
            if isinstance(labels_val, list):
                label_list = [
                    l.decode("utf-8") if isinstance(l, bytes) else str(l)
                    for l in labels_val
                ]
            else:
                label_list = [str(labels_val)] if labels_val else []

            if hasattr(node, "labels") and node.labels:
                label_list = [
                    l.decode("utf-8") if isinstance(l, bytes) else str(l)
                    for l in node.labels
                ]

            node_id = node.id
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            props = dict(node.properties)
            label = label_list[0] if label_list else "Unknown"
            display_name = (
                props.get("name")
                or props.get("handle")
                or (props.get("title", "")[:28] if props.get("title") else None)
                or props.get("id", str(node_id))
            )
            nodes.append({
                "id": node_id,
                "label": display_name,
                "group": label,
                "properties": props,
            })

    edges_result = graph.query(GRAPH_EDGES_CYPHER)
    edges = []
    if edges_result and edges_result.result_set:
        for row in edges_result.result_set:
            src = row[0]
            rel_type = row[1].decode("utf-8") if isinstance(row[1], bytes) else str(row[1])
            tgt = row[2]
            rel_props = row[3] if len(row) > 3 and row[3] is not None else {}
            edges.append({
                "from": src.id,
                "to": tgt.id,
                "label": rel_type,
                "properties": rel_props,
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "cypher_nodes": GRAPH_NODES_CYPHER,
        "cypher_edges": GRAPH_EDGES_CYPHER,
    }
