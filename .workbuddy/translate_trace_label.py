# -*- coding: utf-8 -*-
"""Translate English UI labels in viewer.py to Chinese.

Reads viewer.py, applies 17 string replacements in the specified order, prints a
per-rule hit/miss report, prints the total substitution count, then writes the
file back unconditionally as UTF-8 with LF (\n) newlines.

Order matters: more specific patterns (e.g. "LLM Call (templated)") are applied
before their prefixes (e.g. "LLM Call") so they do not get clobbered.
"""

from pathlib import Path

VIEWER_PATH = Path(r"D:\my-projects\agent-monitor\viewer.py")

RULES = [
    ("Tool Agent", "工具型智能体"),
    ("Retrieval Chain", "检索链"),
    ("LLM Chain", "LLM 调用链"),
    ("LLM Call (templated)", "大模型调用（带模板）"),
    ("Parallel Search ({n})", "多任务并行（{n}）"),
    ("Parallel: {_short_purpose(tools[0]) or tools[0]}", "多任务并行：{_short_purpose(tools[0]) or tools[0]}"),
    ("Parallel: {a} + {b}", "多任务并行：{a} + {b}"),
    ("Parallel Search (", "多任务并行（"),
    ("Parallel: ", "多任务并行："),
    ("Parallel Branches", "多任务并行"),
    ("Chain Step", "链路步骤"),
    ("LLM Call", "大模型调用"),
    ("(unnamed)", "（未命名）"),
    ("(empty trace)", "（空 trace）"),
    ("  # red cross", "  # 红色叉（错误）"),
    ("  # green tick", "  # 绿色勾（成功）"),
    ("  # hourglass (UNSET / in-progress)", "  # 沙漏（未完成）"),
]


def main() -> None:
    VIEWER_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = VIEWER_PATH.read_text(encoding="utf-8")

    total = 0
    for old, new in RULES:
        count = text.count(old)
        if count:
            text = text.replace(old, new)
            print(f"HIT n={count} {old}")
        else:
            print(f"miss     {old}")
        total += count

    with VIEWER_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    print(f"Total substitutions: {total}")


if __name__ == "__main__":
    main()