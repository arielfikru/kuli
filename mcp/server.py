#!/usr/bin/env python3
"""Thin MCP wrapper over the ask-deepseek CLI.

Optional adapter so MCP-native agents can delegate to the DeepSeek "intern"
without spawning a shell themselves. All real work (caching, reasoning,
self-consistency, batch fan-out) lives in the CLI — this just exposes it as
typed MCP tools.

Run:  OPENROUTER_API_KEY=sk-or-... python3 server.py
Register (Claude Code):
  claude mcp add deepseek -- python3 /abs/path/to/mcp/server.py
"""
import os
import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("deepseek")


def _cli(name):
    """Locate an installed CLI binary (PATH, then ~/.claude/bin)."""
    found = shutil.which(name)
    if found:
        return found
    fallback = Path.home() / ".claude" / "bin" / name
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError(f"{name} not found on PATH or ~/.claude/bin — run install.sh")


def _run(cmd, stdin=None):
    proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    out = proc.stdout.rstrip("\n")
    if proc.returncode != 0:
        return f"ERROR ({proc.returncode}): {proc.stderr.strip()}"
    return f"{out}\n\n[{proc.stderr.strip()}]" if proc.stderr.strip() else out


@mcp.tool()
def ask_deepseek(
    prompt: str,
    model: str = "auto",
    reasoning: str = "",
    system: str = "",
    consistency: int = 0,
    context_file: str = "",
    max_tokens: int = 0,
) -> str:
    """Delegate one task to the DeepSeek intern.

    model: 'auto' (route by size), 'flash' (cheap), 'pro' (default), or an
      explicit OpenRouter slug. reasoning: '' | 'high' | 'xhigh' (thinking mode,
      for hard reasoning). consistency: N>1 samples N and majority-votes (good
      for short/factual answers). context_file: absolute path bundled as the
      cached prefix (the intern has no repo memory — give it the material).
    Returns the answer; the trailing [..] line carries usage / agreement stats.
    """
    cmd = [_cli("ask-deepseek")]
    if model == "flash":
        cmd.append("--flash")
    elif model == "auto":
        cmd.append("--auto")
    elif model not in ("", "pro"):
        cmd += ["-m", model]
    if reasoning:
        cmd += ["-r", reasoning]
    if system:
        cmd += ["-s", system]
    if context_file:
        cmd += ["-f", context_file]
    if consistency and consistency > 1:
        cmd += ["-c", str(consistency)]
    if max_tokens:
        cmd += ["--max-tokens", str(max_tokens)]
    cmd.append(prompt)
    return _run(cmd)


@mcp.tool()
def ask_deepseek_batch(
    prompts: list[str],
    model: str = "auto",
    reasoning: str = "",
    system: str = "",
    context_file: str = "",
    jobs: int = 4,
) -> str:
    """Fan out many prompts to the intern in parallel (shared cached prefix).

    Pass a shared `system`/`context_file` so the prefix is cached after the
    first call. Returns JSON array of {index, prompt, output, ok}.
    """
    cmd = [_cli("ask-deepseek-batch"), "--json", "-j", str(jobs)]
    if model == "flash":
        cmd.append("--flash")
    elif model == "auto":
        cmd.append("--auto")
    elif model not in ("", "pro"):
        cmd += ["-m", model]
    if reasoning:
        cmd += ["-r", reasoning]
    if system:
        cmd += ["-s", system]
    if context_file:
        cmd += ["-c", context_file]
    return _run(cmd, stdin="\n".join(prompts) + "\n")


if __name__ == "__main__":
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("warning: OPENROUTER_API_KEY not set", flush=True)
    mcp.run()
