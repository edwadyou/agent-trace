"""LangChain agent that can delete core files; sensitive files are refused.

Demonstrates that the local agent monitor can capture dangerous deletion
attempts: when the delete_file tool refuses to remove a protected file, the
trace tree marks the [TOOL] span as ERROR with the refusal message.

Prerequisites:
    .env supplies OPENAI_API_KEY (and optionally OPENAI_BASE_URL, LLM_MODEL).

Run:
    python dangerous_delete_agent.py agent_monitor/monitor.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from agent_monitor import monitor

PROTECTED_NAMES = {"pyproject.toml", "README.md", ".env"}
PROTECTED_DIRS = {"agent_monitor"}


def _resolve_target(user_path: str) -> tuple[Path, Path]:
    cwd = Path.cwd().resolve()
    target = (cwd / user_path).resolve()
    try:
        relative = target.relative_to(cwd)
    except ValueError:
        raise RuntimeError(f"Refusing to operate outside project root: {target}")
    return relative, target


@tool
def delete_file(file_path: str) -> str:
    """Delete a single file inside the current project root.

    The function refuses to delete files under agent_monitor/ or the project
    configuration files (pyproject.toml, README.md, .env). Any such attempt
    raises an error so that callers can see the refusal.
    """
    relative, target = _resolve_target(file_path)
    if relative.parts and relative.parts[0] in PROTECTED_DIRS:
        raise RuntimeError(
            f"Refusing to delete sensitive core file: {relative.as_posix()}"
        )
    if relative.name in PROTECTED_NAMES:
        raise RuntimeError(
            f"Refusing to delete sensitive core file: {relative.as_posix()}"
        )
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {relative.as_posix()}")
    target.unlink()
    return f"Deleted {relative.as_posix()}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Dangerous delete agent")
    parser.add_argument(
        "path",
        help="Path of the file to delete, relative to the project root",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "sk-...":
        sys.exit(1)

    base_url = os.environ.get("OPENAI_BASE_URL") or None
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    sys.stdout.reconfigure(encoding="utf-8")

    llm = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0,
        max_tokens=600,
    )

    system_prompt = (
        "You are a file-management assistant with a delete_file tool.\n"
        "- The tool deletes a single file inside the current project root.\n"
        "- You must always call the delete_file tool to attempt the deletion, "
        "even if the user asks to delete a sensitive core file.\n"
        "- After the tool returns or raises an error, explain the outcome to the "
        "user and warn that the requested operation was refused because it is "
        "dangerous."
    )

    agent = create_agent(
        model=llm,
        tools=[delete_file],
        system_prompt=system_prompt,
    )

    user_request = f"Please delete the file at {args.path}."

    with monitor(
        service_name="dangerous-delete-agent",
        auto_instrument=True,
        instrumentors=["langchain"],
        verbose=True,
    ):
        try:
            result = agent.invoke({"messages": [{"role": "user", "content": user_request}]})
            final = result["messages"][-1]
            content = getattr(final, "content", final)
            print("\nAgent response:")
            print(content)
        except Exception as exc:
            print(f"\nAgent aborted: {type(exc).__name__}: {exc}")

    print("\nDone.\n")


if __name__ == "__main__":
    main()