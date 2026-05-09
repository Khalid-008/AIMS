# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Survey AI is a full-stack analytics platform that wraps existing survey data with an AI chat assistant. The backend exposes survey dashboards and a streaming chat endpoint; the frontend renders per-question charts alongside a chat panel. The LLM (Qwen3-27B) receives tool results from a set of survey-scoped MCP tools and streams responses back via Server-Sent Events.

## Commands

### Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows
pip install -e ".[dev]"

# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # Vite dev server on :5173, proxies /api to backend
npm run build    # vue-tsc type check + vite build
```

## Architecture

### Request flow

```
Browser → FastAPI routers → agent/chat.py (LangGraph ReAct loop)
                          → mcp/tools.py  (survey-scoped SQL)
                          → MySQL (smp_user_service)
                          ← SSE stream (token / tool_call / tool_result / done)
```

### Backend layers

| Layer | Path | Purpose |
|---|---|---|
| Routers | `app/routers/` | `surveys.py` (dashboard), `chat.py` (SSE stream + history) |
| Agent | `app/agent/` | `chat.py` — LangGraph loop + SSE streaming; `llm.py` — Qwen3 client; `tools.py` — wraps MCP tools for LangChain; `prompt.py` — bilingual system prompts |
| MCP tools | `app/mcp/tools.py` | 10 SQL-backed tools pre-bound to a survey scope, exposed to the LLM |
| Services | `app/services/` | `dashboard.py` — builds chart data per question type; `language.py` — EN/AR detection |
| DB | `app/db.py` | Two async SQLAlchemy engines: RO (survey tables) and RW (chat tables) |

### Frontend layers

- `src/views/SurveyWorkspaceView.vue` — main page: left dashboard pane + right chat pane
- `src/components/ChatPanel.vue` — SSE consumer, session management, renders tool results inline
- `src/components/charts/` — ECharts wrappers per question type (bar, pie, doughnut, emoji histogram, text themes, file gallery)
- `src/api/client.ts` — Axios instance, base URL set by Vite proxy

### Database

Two logical roles against a single MySQL database (`smp_user_service`):

- **RO user** — reads survey data (survey, survey_question, survey_answer, survey_answer_option, question_option, question_dropdown)
- **RW user** — owns ai_chat_session and ai_chat_message

Migration: `backend/migrations/001_ai_chat_tables.sql` must be run manually before first boot.

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

```
DB_HOST / DB_PORT / DB_NAME
DB_RO_USER / DB_RO_PASSWORD
DB_RW_USER / DB_RW_PASSWORD
QWEN3_LLM_MUX_URL           # OpenAI-compatible endpoint
QWEN3_LLM_MUX_API_KEY
QWEN3_MODEL_ID
# Optional Langfuse tracing
LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
```

## Key Design Decisions

**Survey scope isolation** — every MCP tool receives the `survey_number` at bind time and validates it on every call; cross-survey data leaks are prevented at the tool layer, not the agent layer.

**SSE streaming protocol** — `app/agent/chat.py` emits typed events (`token`, `tool_call`, `tool_result`, `error`, `done`); `ChatPanel.vue` parses these to render live thinking steps alongside streamed text.

**Bilingual support** — language is detected per user message in `services/language.py`; the agent switches between `SYSTEM_EN` / `SYSTEM_AR` prompts and all DB columns have `_en` / `_ar` variants.

**Dual LLM usage** — Qwen3 drives the ReAct agent; a separate GPT-OSS call in `mcp/tools.py` extracts keywords from free-text answers for the themes tool.

## Adding New Agent Tools

1. Implement the SQL logic in `app/mcp/tools.py` (keep survey scope as first param).
2. Wrap it with a LangChain `StructuredTool` in `app/agent/tools.py`.
3. Add the tool to the list returned by `build_tools()`.
4. The tool will automatically appear in the LLM's tool roster on the next request.

## Known Issues / TODOs

- External survey list API token is hardcoded in `app/routers/surveys.py`; should be moved to `.env`.
- No authentication on the chat endpoint (uses anonymous user ID); JWT middleware is stubbed but not enforced.
- No frontend test framework configured.
