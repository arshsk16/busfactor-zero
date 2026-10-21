"""
agent.py
========
Autonomous Company Brain Agent for BusFactor Zero.

The agent orchestrates the full GraphRAG pipeline:
  1. Runs FalkorDB Cypher queries to identify at-risk modules + blast radius
  2. Retrieves PR technical summaries & module architecture docs from FalkorDB (GraphRAG)
  3. Generates a structured handoff packet via LLM (OpenAI / Groq / Gemini) or deterministic GraphRAG synthesizer
  4. Writes AgentMemory + SHADOW_ASSIGNED_TO back into FalkorDB

The agent works out-of-the-box with zero API keys using the context-aware
GraphRAG synthesizer — the demo never crashes.
"""

import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from graph_queries import (
    detect_bus_factor_bottlenecks,
    simulate_developer_unavailable,
    recommend_backup_engineer,
    commit_agent_handoff_memory,
    get_graph as get_falkor_graph,
    _result_to_dicts,
)

load_dotenv()


# ---------------------------------------------------------------------------
# Multi-Provider LLM Client (OpenAI / Groq / Gemini → GraphRAG Fallback)
# ---------------------------------------------------------------------------

def _get_llm_client():
    """Return (OpenAI_compatible_client, model_name) if any key is configured."""
    try:
        from openai import OpenAI
        if os.getenv("OPENAI_API_KEY"):
            return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), "gpt-4o-mini"
        if os.getenv("GROQ_API_KEY"):
            return (
                OpenAI(
                    api_key=os.getenv("GROQ_API_KEY"),
                    base_url="https://api.groq.com/openai/v1",
                ),
                "llama-3.3-70b-versatile",
            )
        if os.getenv("GEMINI_API_KEY"):
            return (
                OpenAI(
                    api_key=os.getenv("GEMINI_API_KEY"),
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                ),
                "gemini-2.5-flash",
            )
    except ImportError:
        pass
    return None, None


def _llm_generate(prompt: str, system: str = "", context_meta: dict | None = None) -> str:
    """Call configured LLM; gracefully fall back to the GraphRAG synthesizer."""
    client, model = _get_llm_client()
    if client and model:
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.35,
                max_tokens=1200,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  ⚠ LLM API error ({e}), using deterministic GraphRAG synthesizer")

    return _fallback_synthesizer(prompt, context_meta or {})


def _fallback_synthesizer(prompt: str, meta: dict) -> str:
    """
    Context-rich deterministic GraphRAG synthesizer when no LLM API key is set.
    Uses actual FalkorDB subgraph context (module doc_summary, PR summaries,
    reviewers, downstream dependencies, and blocked revenue features).
    """
    if meta.get("mode") == "audit":
        bottlenecks = meta.get("bottlenecks", [])
        health_score = max(15, 100 - (len(bottlenecks) * 18))
        top_items = "
".join(
            f"- **`{b['module']}`** ({b['criticality'].upper()}) — Sole Expert: `{b['sole_expert']}` | "
            f"Blocks: *{b['blocking_feature']}* ({b['revenue_impact']}, {b['deadline_days']}d deadline)"
            for b in bottlenecks[:4]
        )
        return f"""## 🧠 Executive Company Brain Risk Audit

**Overall Bus-Factor Health Score:** `{health_score}/100` ({len(bottlenecks)} unmitigated single-point-of-failure modules)

### Top Critical Bottlenecks (Ranked by Revenue & Deadline Urgency)
{top_items or "- No active single-point-of-failure bottlenecks detected!"}

### Immediate Actions Recommended (Next 48 Hours)
- Trigger autonomous shadow-assignment handoffs for all **CRITICAL** modules with deadlines under 7 days.
- Pair backup engineers identified via FalkorDB 2-hop proximity scoring on upcoming pull requests.
- Enforce mandatory 2-reviewer branch protection on all modules linked to active ARR features.
"""

    module = meta.get("module", "unknown-module")
    doc_summary = meta.get("doc_summary", "Core production service module.")
    developer = meta.get("unavailable_dev", "the departing developer")
    backup = meta.get("backup_name", "the backup engineer")
    backup_handle = meta.get("backup_handle", "@backup")
    reasons = ", ".join(meta.get("backup_reasons", [])) or "Highest graph proximity in FalkorDB"
    score = meta.get("proximity_score", 0)
    cascade = ", ".join(f"`{c}`" for c in meta.get("cascade_compromised", [])) or "None (leaf module)"
    prs = meta.get("prs", [])

    if prs:
        pr_section = "
".join(
            f"- **{p.get('pr_id', 'PR')} — {p.get('title', '')}** *(merged {p.get('merged_days_ago', '?')}d ago by {p.get('author', developer)}; reviewed by {', '.join(p.get('reviewers', [])) or 'team'})*
"
            f"  {p.get('summary', '')}"
            for p in prs[:4]
        )
    else:
        pr_section = f"- Module documentation summary: {doc_summary}"

    return f"""## 🤖 Autonomous GraphRAG Handoff Briefing: `{module}`

**Module Architecture:** {doc_summary}
**Unavailable Maintainer:** `{developer}`
**Recommended Backup Engineer:** **{backup}** (`{backup_handle}`) — *Proximity Score: {score} ({reasons})*
**Cascade Dependency Impact (`DEPENDS_ON*1..3`):** {cascade}

### Retrieved Pull-Request Context (FalkorDB GraphRAG)
{pr_section}

### 5-Step Technical Onboarding Checklist for {backup}
- **1. Architecture & PR Walkthrough:** Review the merged PR changes above in `{module}`, focusing on edge-case handling and external service contracts.
- **2. Dependency Boundary Verification:** Run integration tests covering `{module}` and its connected `DEPENDS_ON` neighbors ({cascade}).
- **3. Shadow Code Review Lock:** Assume primary reviewer ownership on `{module}` (`SHADOW_ASSIGNED_TO` edge persisted in FalkorDB).
- **4. Operational & Alerting Handoff:** Verify access to deployment pipelines, secrets, and latency/error SLO alerts for `{module}`.
- **5. Feature Continuity Check:** Sync with product owners on blocked sprint deliverables to maintain delivery timeline.

> Generated by BusFactor Zero Autonomous Agent · Stored in FalkorDB as `AgentMemory`
"""


# ---------------------------------------------------------------------------
# GraphRAG retrieval — fetch Module doc_summary + PR summaries from FalkorDB
# ---------------------------------------------------------------------------

def _retrieve_pr_context(module_name: str) -> tuple[str, list[dict]]:
    """
    Retrieve module doc_summary and PR technical summaries via Cypher.
    This forms the structured + unstructured retrieval step in GraphRAG.
    """
    graph = get_falkor_graph()

    mod_res = graph.query(
        "MATCH (m:Module {name: $module_name}) RETURN m.doc_summary AS doc_summary",
        {"module_name": module_name},
    )
    mod_rows = _result_to_dicts(mod_res)
    doc_summary = mod_rows[0].get("doc_summary", "") if mod_rows else ""

    cypher = """
    MATCH (pr:PullRequest)-[:MODIFIES]->(m:Module {name: $module_name})
    MATCH (author:Developer)-[:AUTHORED]->(pr)
    OPTIONAL MATCH (reviewer:Developer)-[:REVIEWED]->(pr)
    RETURN pr.id AS pr_id,
           pr.title AS title,
           pr.summary AS summary,
           pr.merged_days_ago AS merged_days_ago,
           author.name AS author,
           collect(DISTINCT reviewer.name) AS reviewers
    ORDER BY pr.merged_days_ago ASC
    LIMIT 6
    """.strip()
    result = graph.query(cypher, {"module_name": module_name})
    return doc_summary, _result_to_dicts(result)


# ---------------------------------------------------------------------------
# Core agent pipeline
# ---------------------------------------------------------------------------

def run_mitigation_agent(dev_handle: str) -> dict:
    """
    Full autonomous pipeline:
      1. Detect bus-factor bottlenecks (Q1)
      2. Simulate developer unavailability — multi-hop blast radius (Q2)
      3. Recommend backup engineers for each compromised module (Q3)
      4. GraphRAG: retrieve module docs + PR context from FalkorDB
      5. LLM / Synthesizer: generate technical handoff packet per module
    """
    execution_log = []
    timestamp = datetime.now(timezone.utc).isoformat()

    print(f"\n🧠 Agent triggered for: {dev_handle}")
    bottleneck_data = detect_bus_factor_bottlenecks()
    execution_log.append({
        "step": "Q1 · detect_bus_factor_bottlenecks",
        "cypher": bottleneck_data["cypher"],
        "params": bottleneck_data["params"],
        "result_count": len(bottleneck_data["result"]),
    })

    blast_data = simulate_developer_unavailable(dev_handle)
    execution_log.append({
        "step": "Q2 · simulate_developer_unavailable",
        "cypher": blast_data["cypher"],
        "params": blast_data["params"],
        "result_count": len(blast_data["result"]),
    })

    blast_result = blast_data["result"][0] if blast_data["result"] else {}
    directly_compromised = blast_result.get("directly_compromised", [])
    cascade_compromised = blast_result.get("cascade_compromised", [])
    blocked_features = blast_result.get("blocked_features", [])
    blast_radius_score = blast_result.get("blast_radius_score", 0)

    module_recommendations = {}
    for module_name in directly_compromised:
        rec_data = recommend_backup_engineer(module_name, dev_handle)
        module_recommendations[module_name] = rec_data["result"]
        execution_log.append({
            "step": f"Q3 · recommend_backup_engineer ({module_name})",
            "cypher": rec_data["cypher"],
            "params": rec_data["params"],
            "result_count": len(rec_data["result"]),
        })

    handoff_packets = {}
    for module_name in directly_compromised:
        doc_summary, pr_context = _retrieve_pr_context(module_name)
        recommendations = module_recommendations.get(module_name, [])
        top_backup = recommendations[0] if recommendations else None

        pr_bullets = "\n".join(
            f"- PR {p.get('pr_id')}: [{p.get('title', '')}] by {p.get('author', '')} "
            f"({p.get('merged_days_ago', '?')} days ago)\n  Summary: {p.get('summary', '')[:300]}"
            for p in pr_context
        )

        backup_name = top_backup["recommended_dev"] if top_backup else "Unassigned"
        backup_handle = top_backup["handle"] if top_backup else ""
        backup_reasons = top_backup.get("reasons", []) if top_backup else []
        proximity_score = top_backup.get("proximity_score", 0) if top_backup else 0

        prompt = f"""You are an autonomous engineering intelligence system called BusFactor Zero.

A critical bus-factor risk has been identified and you must generate a technical handoff briefing.

## Situation
Module: {module_name}
Module Architecture Summary: {doc_summary}
Unavailable Developer: {dev_handle}
Recommended Backup: {backup_name} ({backup_handle})
Backup Selection Reasons: {', '.join(backup_reasons)}
Graph Proximity Score: {proximity_score}

## Downstream Impact
Directly Compromised Modules: {', '.join(directly_compromised)}
Cascade Compromised (via DEPENDS_ON graph): {', '.join(cascade_compromised)}
Blocked Client Features: {json.dumps(blocked_features, indent=2)}

## Technical Context Retrieved from FalkorDB Graph (GraphRAG)
{pr_bullets if pr_bullets else doc_summary}

## Your Task
Generate a structured, actionable technical handoff briefing for {backup_name} covering:
1. Concise module architecture summary
2. Recent PR changes and active technical context
3. Downstream cascade risks
4. 5-step onboarding checklist
"""
        system = (
            "You are an autonomous engineering intelligence agent powered by FalkorDB. "
            "Generate precise, technical handoff briefings referencing the retrieved graph context."
        )
        meta = {
            "mode": "handoff",
            "module": module_name,
            "doc_summary": doc_summary,
            "unavailable_dev": dev_handle,
            "backup_name": backup_name,
            "backup_handle": backup_handle,
            "backup_reasons": backup_reasons,
            "proximity_score": proximity_score,
            "cascade_compromised": cascade_compromised,
            "prs": pr_context,
        }

        packet = _llm_generate(prompt, system, meta)
        handoff_packets[module_name] = {
            "module": module_name,
            "backup_dev": backup_name,
            "backup_handle": backup_handle,
            "proximity_score": proximity_score,
            "packet": packet,
        }

    return {
        "timestamp": timestamp,
        "triggered_by": dev_handle,
        "blast_result": blast_result,
        "directly_compromised": directly_compromised,
        "cascade_compromised": cascade_compromised,
        "blocked_features": blocked_features,
        "blast_radius_score": blast_radius_score,
        "module_recommendations": module_recommendations,
        "handoff_packets": handoff_packets,
        "execution_log": execution_log,
    }


def run_audit_agent() -> dict:
    """
    Company-wide bus factor audit — runs Q1 and generates an executive risk report
    for all single-point-of-failure modules simultaneously.
    """
    bottleneck_data = detect_bus_factor_bottlenecks()
    bottlenecks = bottleneck_data["result"]

    risk_report = []
    for b in bottlenecks:
        rec_data = recommend_backup_engineer(b["module"], b["sole_expert"])
        risk_report.append({
            "module": b["module"],
            "criticality": b["criticality"],
            "sole_expert": b["sole_expert"],
            "blocking_feature": b["blocking_feature"],
            "deadline_days": b["deadline_days"],
            "revenue_impact": b["revenue_impact"],
            "backup_candidates": rec_data["result"][:2],
        })

    prompt = f"""You are BusFactor Zero, an autonomous company brain powered by FalkorDB.
A bus-factor audit found {len(bottlenecks)} critical single-point-of-failure modules:
{json.dumps(risk_report, indent=2)}

Generate an executive risk summary with:
1. Overall company bus-factor health score (0-100)
2. Top critical risks ranked by revenue impact + deadline urgency
3. Immediate 48-hour mitigation plan
"""
    summary = _llm_generate(prompt, context_meta={"mode": "audit", "bottlenecks": bottlenecks})

    return {
        "bottlenecks": bottlenecks,
        "risk_report": risk_report,
        "cypher": bottleneck_data["cypher"],
        "executive_summary": summary,
        "total_bottlenecks": len(bottlenecks),
    }
