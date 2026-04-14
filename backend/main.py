"""
AgentOS Backend — Multi-Agent Orchestration Platform
FastAPI + OpenAI Agents SDK + Server-Sent Events for live log streaming
"""

import os
import json
import asyncio
import uuid
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# ── OpenAI client ──────────────────────────────────────────────────────────────
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── In-memory state (replace with Redis for production) ───────────────────────
agent_registry: dict = {}
task_queue: list = []
run_logs: list = []


# ── Agent definitions ──────────────────────────────────────────────────────────
AGENT_DEFINITIONS = {
    "ResearchBot": {
        "role": "WEB_RESEARCHER",
        "emoji": "🔍",
        "system_prompt": (
            "You are ResearchBot, a web research specialist. "
            "Given a task, break it into clear findings. "
            "Be factual, cite patterns you observe, and summarise concisely. "
            "Respond in plain text unless JSON is explicitly requested."
        ),
    },
    "CodeSmith": {
        "role": "CODE_GENERATOR",
        "emoji": "💻",
        "system_prompt": (
            "You are CodeSmith, an expert software engineer. "
            "Write clean, production-ready code with brief inline comments. "
            "Always include a usage example at the end."
        ),
    },
    "DataMind": {
        "role": "DATA_ANALYST",
        "emoji": "📊",
        "system_prompt": (
            "You are DataMind, a data analyst. "
            "Analyse data, identify trends, surface key insights, and recommend actions. "
            "Be quantitative where possible."
        ),
    },
    "WriteBot": {
        "role": "CONTENT_WRITER",
        "emoji": "✍️",
        "system_prompt": (
            "You are WriteBot, a professional content writer. "
            "Create compelling, well-structured content. "
            "Adapt tone to context — formal for reports, engaging for marketing."
        ),
    },
    "Orchestrator": {
        "role": "ORCHESTRATOR",
        "emoji": "🧠",
        "system_prompt": (
            "You are the Orchestrator — the central intelligence of AgentOS. "
            "When a user gives you a task:\n"
            "1. Analyse what is needed.\n"
            "2. Decide which agents to involve (ResearchBot, CodeSmith, DataMind, WriteBot).\n"
            "3. Describe your plan clearly.\n"
            "4. Execute the first step yourself.\n\n"
            "Available agents: ResearchBot (research/scraping), CodeSmith (code), "
            "DataMind (data analysis), WriteBot (writing/emails).\n\n"
            "Be decisive and action-oriented. Do not ask clarifying questions unless "
            "the task is genuinely ambiguous."
        ),
    },
}


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(agent: str, msg: str, level: str = "info"):
    entry = {"time": _ts(), "agent": agent, "msg": msg, "level": level}
    run_logs.append(entry)
    if len(run_logs) > 200:
        run_logs.pop(0)
    return entry


# ── Lifespan: seed agents on startup ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    for name, cfg in AGENT_DEFINITIONS.items():
        agent_registry[name] = {
            "name": name,
            "role": cfg["role"],
            "emoji": cfg["emoji"],
            "status": "idle",
            "tasks_completed": 0,
            "success_rate": 100.0,
            "current_task": None,
        }
    _log("System", "AgentOS initialised · 5 agents online", "info")
    yield
    _log("System", "AgentOS shutting down", "info")


app = FastAPI(title="AgentOS API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []   # [{role: "user"|"assistant", content: "..."}]


class TaskRequest(BaseModel):
    agent: str
    task: str


class DeployRequest(BaseModel):
    name: str
    model: str = "gpt-4o"
    system_prompt: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _call_agent(agent_name: str, messages: list[dict]) -> str:
    """Call OpenAI with a specific agent's system prompt."""
    cfg = AGENT_DEFINITIONS.get(agent_name)
    if not cfg:
        raise ValueError(f"Unknown agent: {agent_name}")

    system = cfg["system_prompt"]
    full_messages = [{"role": "system", "content": system}] + messages

    response = await client.chat.completions.create(
        model=MODEL,
        messages=full_messages,
        max_tokens=1200,
        temperature=0.7,
    )
    return response.choices[0].message.content


async def _stream_agent(agent_name: str, messages: list[dict]):
    """Stream tokens from an agent via SSE."""
    cfg = AGENT_DEFINITIONS.get(agent_name)
    system = cfg["system_prompt"] if cfg else "You are a helpful assistant."
    full_messages = [{"role": "system", "content": system}] + messages

    stream = await client.chat.completions.create(
        model=MODEL,
        messages=full_messages,
        max_tokens=1200,
        temperature=0.7,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "agents": len(agent_registry), "model": MODEL}


# ── Agents ────────────────────────────────────────────────────────────────────
@app.get("/agents")
async def get_agents():
    """Return current state of all registered agents."""
    return {"agents": list(agent_registry.values())}


@app.post("/agents/deploy")
async def deploy_agent(req: DeployRequest):
    """Dynamically register a new agent."""
    if req.name in agent_registry:
        raise HTTPException(400, f"Agent '{req.name}' already exists")

    AGENT_DEFINITIONS[req.name] = {
        "role": "CUSTOM_AGENT",
        "emoji": "🤖",
        "system_prompt": req.system_prompt or f"You are {req.name}, a helpful AI agent.",
    }
    agent_registry[req.name] = {
        "name": req.name,
        "role": "CUSTOM_AGENT",
        "emoji": "🤖",
        "status": "idle",
        "tasks_completed": 0,
        "success_rate": 100.0,
        "current_task": None,
    }
    _log("System", f"Deployed new agent: {req.name}", "info")
    return {"success": True, "agent": agent_registry[req.name]}


@app.delete("/agents/{name}")
async def remove_agent(name: str):
    if name not in agent_registry:
        raise HTTPException(404, "Agent not found")
    del agent_registry[name]
    if name in AGENT_DEFINITIONS:
        del AGENT_DEFINITIONS[name]
    _log("System", f"Removed agent: {name}", "warn")
    return {"success": True}


# ── Orchestrator Chat (streaming SSE) ─────────────────────────────────────────
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Stream the Orchestrator's response token-by-token via Server-Sent Events.
    The frontend connects with EventSource and renders tokens as they arrive.
    """
    _log("Orchestrator", f"Received task: {req.message[:80]}...", "info")

    # Mark orchestrator as thinking
    if "Orchestrator" in agent_registry:
        agent_registry["Orchestrator"]["status"] = "thinking"

    messages = req.history + [{"role": "user", "content": req.message}]

    async def event_generator():
        full_response = []
        try:
            async for token in _stream_agent("Orchestrator", messages):
                full_response.append(token)
                # SSE format: data: <payload>\n\n
                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"
            # Signal done
            yield f"data: {json.dumps({'done': True, 'full': ''.join(full_response)})}\n\n"
            _log("Orchestrator", "Response complete", "success")
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            _log("Orchestrator", f"Error: {e}", "error")
        finally:
            if "Orchestrator" in agent_registry:
                agent_registry["Orchestrator"]["status"] = "idle"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Non-streaming chat (for simple integrations) ──────────────────────────────
@app.post("/chat")
async def chat(req: ChatRequest):
    messages = req.history + [{"role": "user", "content": req.message}]
    if "Orchestrator" in agent_registry:
        agent_registry["Orchestrator"]["status"] = "thinking"
    try:
        reply = await _call_agent("Orchestrator", messages)
        _log("Orchestrator", "Response sent", "success")
        return {"reply": reply}
    except Exception as e:
        _log("Orchestrator", f"Error: {e}", "error")
        raise HTTPException(500, str(e))
    finally:
        if "Orchestrator" in agent_registry:
            agent_registry["Orchestrator"]["status"] = "idle"


# ── Direct agent task dispatch ────────────────────────────────────────────────
@app.post("/task")
async def run_task(req: TaskRequest):
    """
    Send a task directly to a specific agent.
    Returns the agent's response.
    """
    if req.agent not in agent_registry:
        raise HTTPException(404, f"Agent '{req.agent}' not found")

    agent = agent_registry[req.agent]
    task_id = str(uuid.uuid4())[:8]

    agent["status"] = "running"
    agent["current_task"] = req.task[:60]
    _log(req.agent, f"Starting task [{task_id}]: {req.task[:60]}", "info")

    try:
        result = await _call_agent(req.agent, [{"role": "user", "content": req.task}])
        agent["tasks_completed"] += 1
        agent["status"] = "idle"
        agent["current_task"] = None
        _log(req.agent, f"Task [{task_id}] complete", "success")

        task_queue.append({
            "id": task_id,
            "agent": req.agent,
            "task": req.task[:80],
            "status": "done",
            "result": result,
            "time": _ts(),
        })
        return {"task_id": task_id, "agent": req.agent, "result": result}

    except Exception as e:
        agent["status"] = "error"
        agent["current_task"] = None
        _log(req.agent, f"Task [{task_id}] failed: {e}", "error")
        raise HTTPException(500, str(e))


# ── Pipeline execution ────────────────────────────────────────────────────────
@app.post("/pipeline")
async def run_pipeline(req: ChatRequest):
    """
    Multi-step pipeline: Orchestrator plans → ResearchBot researches → WriteBot writes.
    Returns streaming SSE with step-by-step progress.
    """
    topic = req.message

    async def pipeline_stream():
        steps = [
            ("Orchestrator", f"Create a research plan for: {topic}. List 3 key questions to investigate."),
            ("ResearchBot", f"Research this topic and provide key findings: {topic}"),
            ("DataMind",    f"Analyse the following topic and extract actionable insights: {topic}"),
            ("WriteBot",    f"Write a concise professional summary about: {topic}. Use the insights from the research."),
        ]

        results = {}

        for agent_name, task in steps:
            if agent_name in agent_registry:
                agent_registry[agent_name]["status"] = "running"

            _log(agent_name, f"Pipeline step: {task[:50]}", "info")
            yield f"data: {json.dumps({'step': agent_name, 'status': 'started'})}\n\n"

            full = []
            try:
                async for token in _stream_agent(agent_name, [{"role": "user", "content": task}]):
                    full.append(token)
                    yield f"data: {json.dumps({'step': agent_name, 'token': token})}\n\n"

                results[agent_name] = "".join(full)
                yield f"data: {json.dumps({'step': agent_name, 'status': 'done', 'result': results[agent_name]})}\n\n"
                _log(agent_name, "Pipeline step complete", "success")

            except Exception as e:
                _log(agent_name, f"Pipeline step error: {e}", "error")
                yield f"data: {json.dumps({'step': agent_name, 'status': 'error', 'error': str(e)})}\n\n"
            finally:
                if agent_name in agent_registry:
                    agent_registry[agent_name]["status"] = "idle"

            await asyncio.sleep(0.1)

        yield f"data: {json.dumps({'pipeline': 'complete', 'results': results})}\n\n"

    return StreamingResponse(
        pipeline_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Task queue ────────────────────────────────────────────────────────────────
@app.get("/tasks")
async def get_tasks():
    return {"tasks": task_queue[-20:]}


# ── Live log ──────────────────────────────────────────────────────────────────
@app.get("/logs")
async def get_logs():
    return {"logs": run_logs[-50:]}


@app.get("/logs/stream")
async def stream_logs():
    """SSE stream: pushes new log entries to the frontend in real-time."""
    last_idx = [len(run_logs)]

    async def log_generator():
        while True:
            current_len = len(run_logs)
            if current_len > last_idx[0]:
                new_entries = run_logs[last_idx[0]:current_len]
                last_idx[0] = current_len
                for entry in new_entries:
                    yield f"data: {json.dumps(entry)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Stats ─────────────────────────────────────────────────────────────────────
@app.get("/stats")
async def get_stats():
    total_tasks = sum(a["tasks_completed"] for a in agent_registry.values())
    active = sum(1 for a in agent_registry.values() if a["status"] in ("running", "thinking"))
    return {
        "active_agents": active,
        "total_agents": len(agent_registry),
        "tasks_completed": total_tasks,
        "queue_length": len(task_queue),
        "log_entries": len(run_logs),
    }
