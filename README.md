# code-review-agent

A **conversational code review and implementation agent** built with Mistral's
Agent Python SDK (`mistralai-agents`, imported as `from mistralai import agents`),
deployed on **Mistral Cloud as a managed deployment** with `agents deploy`.

The key property: **sessions are stateful and stored by Mistral once deployed**.
You keep asking follow-ups in the same conversation and the agent remembers the
file(s) you shared and everything you discussed — no re-explaining.

## How it works

```
you (in Vibe) ──MCP tool / chat.py / `agents chat code-reviewer`
                    │  message + session id
                    ▼
        deployed agent "code-reviewer" on Mistral Cloud   ◄── `agents deploy`
        (harness + tools run on Mistral, session stored by Mistral)
                    │
                    ▼
              mistral-large-4 (model on Mistral API)
```

| Concept | Where it lives |
| --- | --- |
| model (`mistral-large-4`) | Mistral API |
| harness + tools | the managed deployment on Mistral Cloud |
| session (full conversation history) | stored by Mistral, resumable by id from any process |

A deployed session ends after 24 h active / 4 h idle by default; resume it any
time within that window with its session id.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | The agent: `agent = agents.Agent(...)` (entrypoint `main:agent`) |
| `chat.py` | Terminal chat with the deployed agent; persists the session id in `~/.vibe/code-reviewer-state.json` |
| `vibe_mcp_server.py` | stdio MCP server exposing the agent to Vibe as tools |
| `Dockerfile` | Image the managed deployment builds (from the SDK template) |
| `pyproject.toml` / `uv.lock` / `.python-version` | uv project the deploy builds |

## Setup

```bash
uv sync                 # create .venv (or use the existing one)
cp .env.example .env    # then put your workspace MISTRAL_API_KEY in .env
```

Try it locally first (runs in your own process, session in memory):

```bash
uv run --env-file .env agents chat                 # interactive, multi-turn
uv run --env-file .env agents chat -m "hello"      # one-shot
uv run --env-file .env python main.py              # programmatic: agent.run(...)
```

## Deploy to Mistral Cloud (managed deployment)

`agents deploy` builds the project into an image **from the pushed GitHub
commit**, so commit and push first (the repo's `origin` must be a GitHub URL
and the branch must have no unpushed commits):

```bash
git add -A && git commit -m "Code review agent"
git push
gents deploy --name code-reviewer        # or just: agents deploy
```

Notes:

* Managed deployments need **pay-as-you-go enabled** on the workspace
  (0 concurrent deployments on free plans, 3 with PAYG, 10 on higher tiers).
* The API key's user needs permission to create deployments in the workspace.
* `agents list` shows deployed/served agents, `agents logs <name>` their logs,
  `agents shutdown <name>` stops one permanently.
* Each turn of the deployed agent is a trace in Mistral Studio (Observe & evaluate).

## Interacting with it

### 1. From Vibe via MCP (recommended) — persistent conversation

Register the bridge once:

```bash
vibe mcp add code-reviewer --transport stdio \
    --command "$PWD/.venv/bin/python" \
    --arg "$PWD/vibe_mcp_server.py"
```

(`vibe mcp add` writes `~/.vibe/config.toml`; equivalent `[[mcp_servers]]` table
is in `vibe_mcp_server.py`'s docstring.)

Then in any Vibe session, just talk to it — Vibe calls the `code_review_chat`
tool, attach files with `@path/to/file.py` so their contents are included in
the message:

```
@src/app.py ask the code reviewer to review this file
now ask it to implement the critical findings
add tests for the parser it just rewrote      <- same conversation, it remembers
```

Tools exposed: `code_review_chat`, `code_review_new_session`,
`code_review_use_session`, `code_review_list_sessions`, `code_review_status`.
The current session id lives in `~/.vibe/code-reviewer-state.json`, so separate
Vibe turns continue the same conversation on the deployed agent.

To also manage the workspace itself (list agents/deployments, read traces,
libraries, secrets, ...) from Vibe, add Mistral's own MCP server:

```bash
vibe mcp add mistralai \
  --url https://api.mistral.ai/mcp \
  --transport streamable-http \
  --api-key-env MISTRAL_API_KEY
```

### 2. From a terminal

```bash
uv run --env-file .env agents chat code-reviewer        # interactive chat with the deployed agent
python chat.py "review this: ..."                       # scriptable, resumes stored session
python chat.py --new "fresh topic"                      # new conversation
python chat.py --sessions                               # list sessions
```

### 3. From Python (any app)

```python
import asyncio
from mistralai import agents

async def main():
    handle = agents.Agent.load_from(agent_name="code-reviewer")  # deployed agent by name
    session = await handle.start_session()                       # or handle.session("<id>") to resume
    result = await session.run("Review this file: ...")
    print(session.id, result.text)   # keep session.id to continue later

asyncio.run(main())
```

## Changing the agent

Edit `main.py`, commit, push, then `agents deploy` again — the platform
rebuilds the image from the new commit and rolls the deployment over.
