"""KULI — Kana Unified LLM Interns.

A worker pool of cheap delegate "interns" you (Claude) orchestrate:
  - deepseek : text/bulk reasoning intern (OpenRouter)
  - gemini   : vision intern, sees images/video (Gemini CLI)
  - codex    : agentic coding intern, read-only Q&A or --apply edits (codex CLI)

Each ``ask-<intern>`` CLI is a thin adapter over the shared machinery in
``kuli.core`` (prompt assembly, self-consistency vote, stats line, batch
fan-out). Stdlib only — no third-party deps.
"""

__version__ = "2.5.0"
