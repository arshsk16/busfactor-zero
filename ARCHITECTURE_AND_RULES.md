# BusFactor Zero — Architecture & Rules Reference

> **Source of Truth** for all developers and AI assistants contributing to this project.
> Read this file first. Every decision in the codebase flows from this document.

---

## 1. Hackathon Context

**Event:** WeMakeDevs × FalkorDB Hackathon
**Deadline:** October 18, 11:59 PM IST
**Project:** BusFactor Zero — Autonomous Company Brain & Engineering Bottleneck GraphRAG Agent
**Tracks:**
1. Company Brain (Primary)
2. Agents That Act on Connected Data
3. Agent Memory and Coordination

---

## 2. Critical Hackathon Rules

| Rule | Requirement |
|------|-------------|
| Rule 1 and 3 | FalkorDB MUST be the primary database. Multi-hop Cypher traversals, degree aggregations, and graph mutations must be core. |
| Rule 9 | Use only public GitHub repository data or synthetic engineering data. |
| Rule 17 | README must include: setup instructions, Mermaid graph schema, and exact Cypher queries used. |
| Rule 19 | README must have an explicit AI coding assistant disclosure section. |

---

## 3. Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | FalkorDB (Redis-based graph DB) |
| Python Client | falkordb (official Python client) |
| AI / LLM | OpenAI GPT-4o with fallback synthesizer |
| HTTP Client | httpx (GitHub API ingestion) |
| Validation | Pydantic |
| Frontend | Single-page HTML, Tailwind CSS (CDN), Vanilla JS, Vis.js |

---

## 4. FalkorDB Graph Schema

**Graph Name:** `CompanyBrain`

### 4.1 Node Labels and Properties

```
(:Developer {
    id: string,
    name: string,
    handle: string,
    role: string,
    status: string
})

(:Module {
    name: string,
    path: string,
    criticality: string,
    doc_summary: string
})

(:PullRequest {
    id: string,
    title: string,
    summary: string,
    merged_days_ago: int
})

(:Feature {
    id: string,
    name: string,
    deadline_days: int,
    status: string,
    revenue_impact: string
})

(:AgentMemory {
    id: string,
    timestamp: string,
    action_type: string,
    summary: string,
    confidence: float
})
```

### 4.2 Relationship Types

```
(:Developer)-[:AUTHORED]->(:PullRequest)
(:Developer)-[:REVIEWED]->(:PullRequest)
(:PullRequest)-[:MODIFIES]->(:Module)
(:Module)-[:DEPENDS_ON]->(:Module)
(:Feature)-[:REQUIRES_MODULE]->(:Module)
(:Developer)-[:SHADOW_ASSIGNED_TO {assigned_by_agent: true}]->(:Module)
(:AgentMemory)-[:MITIGATES_RISK_ON]->(:Module)
```

---

## 5. The 4 Core Cypher Queries

### Q1 — Detect Bus Factor Bottlenecks

Shadow-aware: requires `size(authors) = 1 AND size(shadows) = 0` so that a committed Q4 mitigation immediately clears the bottleneck.

```cypher
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
```

### Q2 — Simulate Developer Unavailable (Blast Radius)

Bidirectional cascade: finds services that depend on compromised modules (`<-[:DEPENDS_ON*1..3]-`) AND upstream modules the dev integrates with.

```cypher
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
```

### Q3 — Recommend Backup Engineer

Scalar projections with weighted proximity scoring: co-authored PRs on module (+4), reviewed PRs (+3), authored PRs on adjacent modules via DEPENDS_ON (+1).

```cypher
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
```

### Q4 — Commit Agent Handoff Memory (Graph Mutation)

Pre-MATCHes `Module` and `Developer` before `CREATE` to prevent dangling nodes. Stores the full handoff briefing as graph-native memory.

```cypher
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
```

---

## 6. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves static/index.html dashboard |
| GET | `/api/health` | FalkorDB connectivity + node count |
| GET | `/api/graph` | Returns all nodes + edges for Vis.js |
| GET | `/api/bottlenecks` | Runs Q1 — Bus Factor detection |
| GET | `/api/audit` | Company-wide risk audit + executive summary |
| GET | `/api/developers` | Developer list for UI selector |
| POST | `/api/simulate-leave` | Runs Q2 + Q3 + GraphRAG handoff |
| POST | `/api/agent/mitigate` | Runs Q4 — commits AgentMemory |
| POST | `/api/seed` | Resets and re-seeds FalkorDB graph |
| POST | `/api/ingest-github` | GitHub repo ingestion with sub-module partitioning (`clear_existing: bool`) |

---

## 7. Directory Structure

```
busfactor-zero/
├── ARCHITECTURE_AND_RULES.md
├── README.md
├── requirements.txt
├── .env.example
├── seed_graph.py
├── graph_queries.py
├── agent.py
├── main.py
└── static/
    └── index.html
```
