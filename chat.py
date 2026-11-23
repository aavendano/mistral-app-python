#!/usr/bin/env python3
"""Terminal chat with the deployed ``code-reviewer`` agent on Mistral Cloud.

The current session id is persisted in ``$VIBE_HOME/code-reviewer-state.json``
(default ``~/.vibe/code-reviewer-state.json``), so every invocation continues the
SAME conversation: the agent (whose session is stored by Mistral) remembers the
files and everything you discussed -- no re-explaining.

Usage:
  python chat.py "review this file: <paste code>"   send a message
  python chat.py --new "start a new topic"          start a fresh session
  python chat.py --session <id> "message"           switch to another session
  python chat.py --sessions                         list sessions
  python chat.py --status                           show current session id

Env:
  MISTRAL_API_KEY        workspace API key (or put it in .env next to this file)
  CODE_REVIEWER_AGENT    deployed agent name (default: code-reviewer)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


def _load_env() -> None:
    if os.environ.get("MISTRAL_API_KEY"):
        return
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def _state_path() -> Path:
    vibe_home = Path(os.environ.get("VIBE_HOME", Path.home() / ".vibe"))
    return vibe_home / "code-reviewer-state.json"


def _load_state() -> dict:
    path = _state_path()
    if path.is_file():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _save_state(state: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def _result_text(result) -> str:
    text = getattr(result, "text", None)
    if text:
        return text
    output = getattr(result, "output", None)
    if output is not None:
        return str(output)
    return str(result)


async def _send(agent_name: str, message: str, session_id: str | None) -> tuple[str, str]:
    from mistralai import agents

    client = agents.Client()
    try:
        handle = agents.Agent.load_from(agent_name=agent_name, client=client)
        if session_id:
            session = handle.session(session_id)
        else:
            session = await handle.start_session()
        result = await session.run(message)
        return session.id, _result_text(result)
    finally:
        await client.aclose()


async def _list_sessions(agent_name: str) -> str:
    from mistralai import agents

    client = agents.Client()
    lines = []
    try:
        handle = agents.Agent.load_from(agent_name=agent_name, client=client)
        async for info in client.list_sessions():
            lines.append(str(info))
    finally:
        await client.aclose()
    return "\n".join(lines) if lines else "(no sessions found)"


async def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", nargs="?", help="message to send")
    parser.add_argument("--new", metavar="MSG", help="start a fresh session with this first message")
    parser.add_argument("--session", metavar="ID", help="use this session id")
    parser.add_argument("--sessions", action="store_true", help="list sessions and exit")
    parser.add_argument("--status", action="store_true", help="show current session id and exit")
    args = parser.parse_args()

    agent_name = os.environ.get("CODE_REVIEWER_AGENT", "code-reviewer")
    state = _load_state()

    if args.status:
        print(json.dumps({"agent": agent_name, **state}, indent=2))
        return 0
    if args.sessions:
        print(await _list_sessions(agent_name))
        return 0

    if args.new is not None:
        state.pop("session_id", None)
        _save_state(state)
        message = args.new
    else:
        message = args.message
    if not message:
        parser.error("pass a message, --new MSG, --sessions or --status")

    session_id = args.session or state.get("session_id")
    sid, reply = await _send(agent_name, message, session_id)
    state["agent"] = agent_name
    state["session_id"] = sid
    _save_state(state)
    print(f"[session {sid}]\n")
    print(reply)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
