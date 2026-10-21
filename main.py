"""
main.py
=======
FastAPI server for BusFactor Zero.

Endpoints:
  GET  /                     → serves static/index.html
  GET  /api/graph            → all nodes + edges (Vis.js format)
  GET  /api/bottlenecks      → Q1 bus-factor detection
  POST /api/simulate-leave   → Q2+Q3+GraphRAG full agent pipeline
  POST /api/agent/mitigate   → Q4 commit AgentMemory to FalkorDB
  POST /api/seed             → reset + re-seed graph
  POST /api/ingest-github    → optional GitHub repo ingestion
  GET  /api/health           → health check
"""

import os
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from graph_queries import (
    detect_bus_factor_bottlenecks,
    recommend_backup_engineer,
    commit_agent_handoff_memory,
    get_full_graph,
)
from agent import run_mitigation_agent, run_audit_agent
import seed_graph as seeder

load_dotenv()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BusFactor Zero — Company Brain Agent",
    description=(
        "Autonomous engineering bottleneck detection and GraphRAG-powered "
        "knowledge handoff using FalkorDB."
    ),
    version="1.0.0",
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SimulateLeaveRequest(BaseModel):
    dev_handle: str  # e.g. "@priya"


class MitigateRequest(BaseModel):
    module_name: str
    backup_dev_handle: str
    handoff_summary: str
    confidence: float = 0.92


class GitHubIngestRequest(BaseModel):
    owner: str
    repo: str
    max_prs: int = 20


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the interactive SPA dashboard."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(str(index_file))


@app.get("/api/health")
async def health_check():
    """Quick health check — verifies FalkorDB connectivity."""
    try:
        from falkordb import FalkorDB
        db = FalkorDB(
            host=os.getenv("FALKORDB_HOST", "localhost"),
            port=int(os.getenv("FALKORDB_PORT", 6379)),
            password=os.getenv("FALKORDB_PASSWORD") or None,
        )
        graph = db.select_graph("CompanyBrain")
        result = graph.query("MATCH (n) RETURN count(n) AS total LIMIT 1")
        total = result.result_set[0][0] if result.result_set else 0
        return {
            "status": "healthy",
            "falkordb": "connected",
            "graph": "CompanyBrain",
            "node_count": total,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)},
        )


@app.get("/api/graph")
async def api_get_graph():
    """
    Return all graph nodes and edges in Vis.js-compatible format.
    Nodes are colour-coded by label group; edges show relationship types.
    """
    try:
        data = get_full_graph()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bottlenecks")
async def api_bottlenecks():
    """
    Q1 — Detect all bus-factor bottlenecks.
    Returns modules where exactly 1 developer has authored PRs,
    blocking active client features.
    """
    try:
        data = detect_bus_factor_bottlenecks()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulate-leave")
async def api_simulate_leave(req: SimulateLeaveRequest):
    """
    Full autonomous agent pipeline:
    Q2 (blast radius) + Q3 (backup recommendation) + GraphRAG handoff generation.
    
    The graph is NOT mutated here — call /api/agent/mitigate to commit.
    """
    try:
        result = run_mitigation_agent(req.dev_handle)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/mitigate")
async def api_agent_mitigate(req: MitigateRequest):
    """
    Q4 — Commit AgentMemory to FalkorDB (live graph mutation).
    Creates an AgentMemory node with the handoff briefing and a
    SHADOW_ASSIGNED_TO edge from the backup developer to the module.
    """
    try:
        result = commit_agent_handoff_memory(
            module_name=req.module_name,
            backup_dev_handle=req.backup_dev_handle,
            handoff_summary=req.handoff_summary,
            confidence=req.confidence,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/seed")
async def api_seed():
    """
    Reset the FalkorDB CompanyBrain graph and re-seed with the full
    synthetic engineering organisation dataset.  Safe to call from the UI.
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, seeder.seed_graph)
        return {
            "status": "seeded",
            "developers": len(seeder.DEVELOPERS),
            "modules": len(seeder.MODULES),
            "pull_requests": len(seeder.PULL_REQUESTS),
            "features": len(seeder.FEATURES),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest-github")
async def api_ingest_github(req: GitHubIngestRequest):
    """
    Optional: ingest real PR data from any public GitHub repository into FalkorDB.
    Adds a new Module node for the repo and AUTHORED/MODIFIES edges for each PR.
    """
    try:
        result = await seeder.ingest_github_repo(req.owner, req.repo, req.max_prs)
        return {"status": "ingested", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit")
async def api_audit():
    """
    Run a company-wide bus-factor audit and generate an executive risk summary.
    """
    try:
        result = run_audit_agent()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/developers")
async def api_developers():
    """Return the list of all active developers for the UI selector."""
    try:
        from graph_queries import get_graph
        graph = get_graph()
        result = graph.query(
            "MATCH (d:Developer) RETURN d.handle AS handle, d.name AS name, "
            "d.role AS role, d.status AS status ORDER BY d.name"
        )
        devs = []
        if result and result.result_set:
            for row in result.result_set:
                devs.append({
                    "handle": row[0],
                    "name": row[1],
                    "role": row[2],
                    "status": row[3],
                })
        return {"developers": devs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
