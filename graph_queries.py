"""
graph_queries.py
================
The 4 core FalkorDB Cypher query functions for BusFactor Zero.

Each function returns a dict with:
  - 'result'  : the query result (list of dicts)
  - 'cypher'  : the exact Cypher string executed (for the UI inspector)
  - 'params'  : parameters passed to the query
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional
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
        password=os.getenv("FALKORDB_PASSWORD") or None,
    )
    return db.select_graph("CompanyBrain")


def _result_to_dicts(result) -> list[dict]:
    """Convert FalkorDB QueryResult to a list of plain dicts.
    
    In falkordb >= 1.8.0 the header is a list of [column_type, column_name] pairs
    coming straight from the Redis RESP wire protocol, so we extract the name
    from index 1 when the item is a list/tuple.
    """
    rows = []
    if not result or not result.result_set:
        return rows
    # Normalise header: each item is either a string or a [type, name] pair
    headers = []
    for h in result.header:
        if isinstance(h, (list, tuple)) and len(h) >= 2:
            headers.append(h[1])  # [column_type, column_name]
        else:
            headers.append(str(h))
    for row in result.result_set:
        record = {}
        for i, header in enumerate(headers):
            val = row[i]
            # FalkorDB Node objects → plain dict
            if hasattr(val, 'properties'):
                val = dict(val.properties)
            # Lists may contain Node objects
            elif isinstance(val, list):
                cleaned = []
                for item in val:
                    if hasattr(item, 'properties'):
                        cleaned.append(dict(item.properties))
                    elif isinstance(item, dict):
                        cleaned.append(item)
                    else:
                        cleaned.append(item)
                val = cleaned
            record[header] = val
        rows.append(record)
    return rows


# ---------------------------------------------------------------------------
# Q1: detect_bus_factor_bottlenecks
# ---------------------------------------------------------------------------

BUS_FACTOR_CYPHER = """
MATCH (f:Feature {status: 'in_progress'})-[:REQUIRES_MODULE]->(m:Module)
MATCH (d:Developer)-[:AUTHORED]->(pr:PullRequest)-[:MODIFIES]->(m)
WITH m, f, collect(DISTINCT d.handle) AS experts
WHERE size(experts) = 1
RETURN m.name AS module,
       m.criticality AS criticality,
       m.doc_summary AS doc_summary,
       experts[0] AS sole_expert,
       f.name AS blocking_feature,
       f.deadline_days AS deadline_days,
       f.revenue_impact AS revenue_impact
ORDER BY
  CASE m.criticality
    WHEN 'critical' THEN 0
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    ELSE 3
  END ASC
""".strip()


def detect_bus_factor_bottlenecks() -> dict:
    """
    Q1 — Find every active Feature whose required Module has exactly one developer
    who has ever authored a PR touching it.  Bus Factor = 1 → single point of failure.
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

BLAST_RADIUS_CYPHER = """
MATCH (d:Developer {handle: $dev_handle})
MATCH (d)-[:AUTHORED]->(pr:PullRequest)-[:MODIFIES]->(direct_module:Module)
WITH d, collect(DISTINCT direct_module) AS direct_modules
UNWIND direct_modules AS dm
OPTIONAL MATCH (dm)-[:DEPENDS_ON*1..3]->(downstream:Module)
WITH d, direct_modules, collect(DISTINCT downstream) AS downstream_modules
UNWIND direct_modules AS dm2
OPTIONAL MATCH (f:Feature)-[:REQUIRES_MODULE]->(dm2)
WITH d, direct_modules, downstream_modules, collect(DISTINCT f) AS blocked_features
RETURN d.name AS developer,
       d.handle AS handle,
       [m IN direct_modules | m.name] AS directly_compromised,
       [m IN downstream_modules | m.name] AS cascade_compromised,
       [feat IN blocked_features | {
           name: feat.name,
           revenue: feat.revenue_impact,
           deadline: feat.deadline_days,
           status: feat.status
       }] AS blocked_features,
       size(direct_modules) + size(downstream_modules) AS blast_radius_score
""".strip()


def simulate_developer_unavailable(dev_handle: str) -> dict:
    """
    Q2 — Multi-hop blast-radius traversal.  Calculates which modules lose their
    sole maintainer AND which 1-to-3 hop downstream dependent modules cascade
    into risk when a developer becomes unavailable.
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

BACKUP_ENGINEER_CYPHER = """
MATCH (m:Module {name: $module_name})
OPTIONAL MATCH (reviewer:Developer)-[:REVIEWED]->(rpr:PullRequest)-[:MODIFIES]->(m)
  WHERE reviewer.handle <> $unavailable_dev AND reviewer.status = 'active'
WITH m, collect(DISTINCT {dev: reviewer, score: 3, reason: 'Reviewed PRs on this module'}) AS review_candidates
OPTIONAL MATCH (m)-[:DEPENDS_ON*1..2]-(adjacent:Module)
OPTIONAL MATCH (adjacent_author:Developer)-[:AUTHORED]->(apr:PullRequest)-[:MODIFIES]->(adjacent)
  WHERE adjacent_author.handle <> $unavailable_dev AND adjacent_author.status = 'active'
WITH m, review_candidates,
     collect(DISTINCT {dev: adjacent_author, score: 1, reason: 'Authors adjacent modules'}) AS adjacent_candidates
WITH m, review_candidates + adjacent_candidates AS all_candidates
UNWIND all_candidates AS candidate
WITH candidate.dev AS dev, sum(candidate.score) AS proximity_score,
     collect(DISTINCT candidate.reason) AS reasons
WHERE dev IS NOT NULL
RETURN dev.name AS recommended_dev,
       dev.handle AS handle,
       dev.role AS role,
       proximity_score,
       reasons
ORDER BY proximity_score DESC
LIMIT 3
""".strip()


def recommend_backup_engineer(module_name: str, unavailable_dev_handle: str) -> dict:
    """
    Q3 — Graph collaborative filtering.  Finds the best backup engineers ranked
    by graph proximity: reviewers of PRs on the module score highest, followed
    by authors of adjacent (1-2 hop DEPENDS_ON) modules.
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
CREATE (mem:AgentMemory {
    id: $memory_id,
    timestamp: $timestamp,
    action_type: 'handoff_briefing',
    summary: $handoff_summary,
    confidence: $confidence
})
WITH mem
MATCH (m:Module {name: $module_name})
CREATE (mem)-[:MITIGATES_RISK_ON]->(m)
WITH mem, m
MATCH (d:Developer {handle: $backup_dev_handle})
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
    Q4 — Mutates FalkorDB live.  Creates an AgentMemory node containing the
    GraphRAG-generated onboarding briefing and writes a SHADOW_ASSIGNED_TO edge
    between the backup developer and the at-risk module, encoding the agent's
    coordination decision permanently in the graph.
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

    # Nodes
    nodes_result = graph.query(GRAPH_NODES_CYPHER)
    nodes = []
    seen_ids = set()
    if nodes_result and nodes_result.result_set:
        for row in nodes_result.result_set:
            node = row[0]  # Node object
            # row[1] is the labels list from labels(n)
            labels_val = row[1] if len(row) > 1 else []
            if isinstance(labels_val, list):
                label_list = [str(l) for l in labels_val]
            else:
                label_list = [str(labels_val)] if labels_val else []

            # Prefer labels from the Node object itself
            if hasattr(node, 'labels') and node.labels:
                label_list = node.labels

            node_id = node.id
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            props = dict(node.properties)
            label = label_list[0] if label_list else "Unknown"
            display_name = (
                props.get("name")
                or props.get("handle")
                or (props.get("title", "")[:30] if props.get("title") else None)
                or props.get("id", str(node_id))
            )
            nodes.append({
                "id": node_id,
                "label": display_name,
                "group": label,
                "properties": props,
            })

    # Edges
    edges_result = graph.query(GRAPH_EDGES_CYPHER)
    edges = []
    if edges_result and edges_result.result_set:
        for row in edges_result.result_set:
            src = row[0]   # Node
            rel_type = row[1]  # string from type(r)
            tgt = row[2]   # Node
            rel_props = row[3] if len(row) > 3 else {}
            if rel_props is None:
                rel_props = {}
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
