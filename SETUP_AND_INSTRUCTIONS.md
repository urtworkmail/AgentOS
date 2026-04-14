# 🚀 Setup & Running Instructions
## AgentOS + FlowMind — Full Stack AI Portfolio Projects

---

## WHAT THESE PROJECTS ARE

### 🤖 Project 1: AgentOS — Multi-Agent Orchestration Platform

**In plain English:**
AgentOS is like a "control room" for multiple AI agents. Instead of talking to one AI,
you have a *fleet* of specialised agents — each one an expert at a specific job.
You talk to the Orchestrator, it decides which agent(s) to use, dispatches the work,
and streams results back to you in real-time.

**The 5 agents:**
| Agent | What it does |
|-------|-------------|
| Orchestrator | Boss agent — receives tasks, makes decisions, routes to others |
| ResearchBot | Researches topics, summarises findings |
| CodeSmith | Writes, debugs, and explains code |
| DataMind | Analyses data, finds patterns, recommends actions |
| WriteBot | Writes emails, reports, marketing copy |

**How it works technically:**
1. You type a task in the chat (e.g., "Research the top 5 AI tools of 2024")
2. The frontend sends it to FastAPI backend via HTTP POST
3. The backend calls the Orchestrator's system prompt via OpenAI streaming API
4. Tokens stream back via Server-Sent Events (SSE) — you see the response word-by-word
5. You can also "Dispatch Task" to a specific agent, or run a multi-step Pipeline
6. The live log panel shows real-time activity from all agents via a separate SSE stream
7. Agent statuses (idle/running/thinking) update every 5 seconds via polling

**What to show a client:**
→ Open the chat, type: *"Write me a cold outreach email for an AI automation agency"*
→ Watch WriteBot respond with a real, streaming response
→ Dispatch Task → CodeSmith → "Write a Python web scraper for product prices"
→ Show the live log updating in real-time
→ Deploy a custom agent with a system prompt you define

---

### 🧠 Project 2: FlowMind — LangGraph Research Agent

**In plain English:**
FlowMind is an *autonomous research agent* that doesn't just ask GPT a question —
it goes through a multi-step reasoning process modelled on LangGraph's graph architecture.
When you give it a topic, it: plans the research, searches the web, fetches & chunks content,
grades which chunks are relevant, reflects on whether it has enough information
(and re-searches if not), then writes a comprehensive answer.

**The 6-node graph:**
```
Plan → Search → Retrieve → Grade → Reflect → Write
                  ↑                   ↓
                  └──── if gaps ───────┘
```

**How each node works:**
| Node | What it actually does |
|------|-----------------------|
| **Planner** | Calls GPT-4o to break the query into 3 focused sub-questions |
| **Searcher** | Calls Tavily API to search the web (or uses mock data without a key) |
| **Retriever** | Takes the raw web content, splits it into ~300-char sentence chunks |
| **Grader** | Calls GPT-4o for each chunk to score it 0–1 for relevance. Drops low-scored chunks |
| **Reflector** | Calls GPT-4o to judge whether the kept chunks are sufficient to answer the question |
| **Writer** | Calls GPT-4o with a streaming response to write a comprehensive Markdown answer |

**The reflection loop:**
If the Reflector says "not sufficient", it generates a follow-up search query and sends
the graph back to Search. This can happen up to 2 times before forcing the write step.
This is the core of what makes it "agentic" — it self-corrects.

**What to show a client:**
→ Type: *"What are the best practices for RAG systems in production?"*
→ Watch each node light up one by one in the sidebar and graph
→ See real sources appear in the Sources panel
→ Watch the answer stream in word-by-word
→ Show the thought chain — the agent's reasoning is transparent

---

## PREREQUISITES

You need:
- Python 3.11+ (check: `python3 --version`)
- An OpenAI API key (get one at https://platform.openai.com)
- Optional: Tavily API key for FlowMind real search (https://tavily.com — free tier available)

---

## INSTALLATION

### Step 1 — Clone / download the projects

Your folder structure should look like this:
```
projects/
├── 01_AgentOS/
│   ├── backend/
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── .env.example
│   └── frontend/
│       └── index.html
└── 02_FlowMind/
    ├── backend/
    │   ├── main.py
    │   ├── requirements.txt
    │   └── .env.example
    └── frontend/
        └── index.html
```

### Step 2 — Set up AgentOS

```bash
# Enter the AgentOS backend folder
cd projects/01_AgentOS/backend

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env

# Open .env and paste your OpenAI key:
# OPENAI_API_KEY=sk-...your-key...
nano .env     # or open in any text editor
```

### Step 3 — Set up FlowMind

```bash
# Open a NEW terminal tab
cd projects/02_FlowMind/backend

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
nano .env
# Add: OPENAI_API_KEY=sk-...your-key...
# Add: TAVILY_API_KEY=tvly-...  (optional but recommended)
```

---

## RUNNING THE SERVERS

### Run AgentOS backend (Terminal 1)
```bash
cd projects/01_AgentOS/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```
You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Run FlowMind backend (Terminal 2)
```bash
cd projects/02_FlowMind/backend
source venv/bin/activate
uvicorn main:app --reload --port 8001
```

### Open the frontends (Terminal 3 — optional, or just double-click)
```bash
# Serve both frontends with Python's built-in server:
cd projects
python3 -m http.server 3000
```
Then open in your browser:
- **AgentOS:**  http://localhost:3000/01_AgentOS/frontend/index.html
- **FlowMind:** http://localhost:3000/02_FlowMind/frontend/index.html

**Or simply double-click** the HTML files directly — they work fine opened from the filesystem.

---

## TESTING THE APIS DIRECTLY

### AgentOS API (port 8000)
```bash
# Check health
curl http://localhost:8000/health

# List agents
curl http://localhost:8000/agents

# Send a task directly to CodeSmith
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{"agent": "CodeSmith", "task": "Write a Python function to parse JSON from a URL"}'

# Chat with Orchestrator (non-streaming)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Research the top AI tools of 2024", "history": []}'

# Deploy a custom agent
curl -X POST http://localhost:8000/agents/deploy \
  -H "Content-Type: application/json" \
  -d '{"name": "SEOAgent", "system_prompt": "You are an SEO expert. Analyse content and suggest keyword improvements."}'
```

### FlowMind API (port 8001)
```bash
# Check health (shows if Tavily is connected)
curl http://localhost:8001/health

# Run a synchronous research query (waits for full result)
curl -X POST http://localhost:8001/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG and how is it used in production?"}'
```

### View auto-generated API docs
- AgentOS:  http://localhost:8000/docs
- FlowMind: http://localhost:8001/docs

---

## INTERACTIVE API DOCS (Swagger UI)

Both backends have **automatic Swagger documentation** at `/docs`.
This is perfect to show clients — they can test every endpoint in the browser.

---

## COMMON ISSUES

| Problem | Fix |
|---------|-----|
| `CORS error` in browser console | Backend not running. Start uvicorn first. |
| `Connection refused` | Check the port — AgentOS=8000, FlowMind=8001 |
| `401 Unauthorized` | Wrong or missing OpenAI key in `.env` |
| `RateLimitError` | You've hit OpenAI rate limits. Wait 60s or upgrade plan. |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` with venv active |
| FlowMind shows mock results | Normal — add `TAVILY_API_KEY` to `.env` for real search |
| Browser can't open HTML | Use `python3 -m http.server 3000` and use localhost URL |

---

## PRODUCTION DEPLOYMENT

### Option A: Simple VPS (DigitalOcean, Vultr, Hetzner)
```bash
# On your server:
git clone your-repo
cd 01_AgentOS/backend
pip install -r requirements.txt
# Create .env with your keys

# Run with Gunicorn for production
pip install gunicorn
gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Repeat for FlowMind on port 8001
# Use nginx as reverse proxy for HTTPS
```

### Option B: Railway / Render (one-click)
1. Push to GitHub
2. Connect repo to Railway or Render
3. Add environment variables in dashboard
4. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Option C: Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## API KEYS — WHERE TO GET THEM

| Key | Where to get | Cost |
|-----|-------------|------|
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys | Pay per token (~$0.002/1k tokens for gpt-4o) |
| `TAVILY_API_KEY` | https://tavily.com | Free: 1,000 searches/month |

**Estimated cost per demo session:**
- AgentOS (5-10 chat messages): ~$0.05–0.15
- FlowMind (1 research query): ~$0.08–0.25 depending on iterations

---

## PROJECT STRUCTURE EXPLAINED

```
backend/
  main.py           ← All the logic: agents, API routes, streaming
  requirements.txt  ← Python packages to install
  .env.example      ← Template for your secret keys
  .env              ← Your actual keys (never commit this!)

frontend/
  index.html        ← Complete UI: HTML + CSS + JavaScript in one file
                       No build step needed. Just open it.
```

---

*Built with FastAPI + OpenAI API + Server-Sent Events (SSE)*
*Portfolio projects for AI/automation freelance work*
