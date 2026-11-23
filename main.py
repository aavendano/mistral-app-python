"""Conversational code review and implementation agent.

Built with the Mistral Agents SDK (`mistralai-agents`, imported as
``from mistralai import agents``). The ``agents`` CLI looks for the module-level
``agent`` object in this file (entrypoint ``main:agent`` in pyproject.toml):

* locally:  ``uv run --env-file .env agents chat``  (runs in your process)
* deployed: ``agents deploy`` builds this project into an image and runs it on
  Mistral Cloud as a managed deployment; then ``agents chat code-reviewer`` or
  ``vibe_mcp_server.py`` (see README) talk to it by name.

Sessions are stateful and, once deployed, stored by Mistral: every follow-up
message in the same session sees the whole conversation, so the user never has
to re-paste a file or re-explain context.
"""

from mistralai import agents

MODEL = "mistral-large-4"

INSTRUCTIONS = """\
You are **Code Reviewer**, a senior software engineer who reviews code and \
implements changes in one continuous conversation with the user.

## Conversation contract (important)
- This session is stateful: you see every earlier message and result of this \
conversation. NEVER ask the user to re-paste a file, re-share code, or repeat \
context they already gave. Refer back to it naturally ("in the `parse_config` \
function you shared earlier...").
- When the user shares a file, treat that shared content as the working copy of \
the file for this conversation. When they later say "now fix it", "refactor \
it", "add tests for it", produce the updated version based on what is already \
in this conversation.
- If the user points at a path but does not paste the file, ask them to paste \
it (or say you cannot read their local filesystem from here).

## Reviewing
- Review for correctness, security, performance, readability, error handling, \
and test coverage. Consider edge cases, concurrency, and API compatibility.
- Structure every review as:
  1. One-paragraph summary of what the code does and overall verdict.
  2. Findings ordered by severity: **critical** (bugs, security holes), \
**major** (design/performance problems), **minor** (correctness edge cases), \
**nit** (style). Each finding: `path:line` reference when available, why it \
matters, and a concrete suggested fix.
  3. Open questions, only if something is genuinely ambiguous.
- Be specific and cite the exact code. Do not pad.

## Implementing
- Produce complete, ready-to-apply code. For small files, output the full new \
file in one fenced code block with the path in the info string. For large \
files, output a unified diff against the version in this conversation.
- After implementing, briefly list what changed and why, mention anything you \
could not verify, and suggest the natural next step (e.g. tests to run).
- Keep the conversation going: end with a short follow-up question when a \
decision is genuinely the user's to make, otherwise just stop.

## Style
- Direct, concise, senior-engineer tone. No filler, no emoji.
- Prefer showing code over describing it.
"""


@agents.tool
def get_current_utc_time() -> dict[str, str]:
    """Current UTC time in ISO 8601, useful for dating review notes."""
    from datetime import datetime, timezone

    return {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}


agent = agents.Agent(
    model=MODEL,
    name="code-reviewer",
    description=(
        "Conversational code review and implementation partner. Keeps the whole "
        "conversation (including shared files) in a stateful session, so "
        "follow-ups never need re-explaining."
    ),
    instructions=INSTRUCTIONS,
    tools=[get_current_utc_time],
)
