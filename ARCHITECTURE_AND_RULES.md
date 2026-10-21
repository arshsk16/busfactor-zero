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

```cypher
MATCH (f:Feature {status: 'in_progress'})-[:REQUIRES_MODULE]->(m:Module)
MATCH (d:Developer)-[:AUTHORED]->(pr:PullRequest)-[:MODIFIES]->(m)
WITH m, f, collect(DISTINCT d.handle) AS experts
WHERE size(experts) = 1
RETURN m.name AS module,
       m.criticality AS criticality,
       experts[0] AS sole_expert,
       f.name AS blocking_feature,
       f.deadline_days AS deadline_days,
       f.revenue_impact AS revenue_impact
ORDER BY m.criticality DESC
```

### Q2 — Simulate Developer Unavailable (Blast Radius)

```cypher
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
       [m IN direct_modules | m.name] AS directly_compromised,
       [m IN downstream_modules | m.name] AS cascade_compromised,
       [feat IN blocked_features | {name: feat.name, revenue: feat.revenue_impact, deadline: feat.deadline_days}] AS blocked_features,
       size(direct_modules) + size(downstream_modules) AS blast_radius_score
```

### Q3 — Recommend Backup Engineer

```cypher
MATCH (m:Module {name: $module_name})
OPTIONAL MATCH (reviewer:Developer)-[:REVIEWED]->(pr:PullRequest)-[:MODIFIES]->(m)
  WHERE reviewer.handle <> $unavailable_dev AND reviewer.status = 'active'
WITH m, collect(DISTINCT {dev: reviewer, score: 3, reason: 'Reviewed PRs on this module'}) AS review_candidates
OPTIONAL MATCH (m)-[:DEPENDS_ON*1..2]-(adjacent:Module)
OPTIONAL MATCH (adjacent_author:Developer)-[:AUTHORED]->(apr:PullRequest)-[:MODIFIES]->(adjacent)
  WHERE adjacent_author.handle <> $unavailable_dev AND adjacent_author.status = 'active'
WITH m, review_candidates, collect(DISTINCT {dev: adjacent_author, score: 1, reason: 'Authors adjacent modules'}) AS adjacent_candidates
WITH m, review_candidates + adjacent_candidates AS all_candidates
UNWIND all_candidates AS candidate
WITH candidate.dev AS dev, sum(candidate.score) AS proximity_score, collect(candidate.reason) AS reasons
WHERE dev IS NOT NULL
RETURN dev.name AS recommended_dev,
       dev.handle AS handle,
       dev.role AS role,
       proximity_score,
       reasons
ORDER BY proximity_score DESC
LIMIT 3
```

### Q4 — Commit Agent Handoff Memory (Graph Mutation)

```cypher
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
RETURN mem.id AS memory_id, d.name AS backup_dev, m.name AS module
```

---

## 6. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves static/index.html dashboard |
| GET | `/api/graph` | Returns all nodes + edges for Vis.js |
| GET | `/api/bottlenecks` | Runs Q1 — Bus Factor detection |
| POST | `/api/simulate-leave` | Runs Q2 + Q3 + GraphRAG handoff |
| POST | `/api/agent/mitigate` | Runs Q4 — commits AgentMemory |
| POST | `/api/seed` | Resets and re-seeds FalkorDB graph |
| POST | `/api/ingest-github` | Optional GitHub repo ingestion |

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
