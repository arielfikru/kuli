#!/usr/bin/env python3
"""KULI MCP server — one server exposing every intern CLI as a typed tool.

Optional adapter so MCP-native agents can delegate to the KULI interns without
spawning a shell. All real work (caching, voting, batch fan-out, sandboxing)
lives in the CLIs — this just exposes them as tools.

Run:    python3 server.py
Register (Claude Code):
  claude mcp add kuli -- python3 /abs/path/to/mcp/server.py
"""
import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kuli")


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


def _model_flags(model):
    """Map the shared model arg to CLI flags (deepseek-style: flash/auto/pro)."""
    if model == "flash":
        return ["--flash"]
    if model == "auto":
        return ["--auto"]
    if model not in ("", "pro"):
        return ["-m", model]
    return []


# --- deepseek: text/bulk intern ---------------------------------------------

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
    """Delegate one task to the DeepSeek (text/bulk) intern.

    model: 'auto' | 'flash' | 'pro' | explicit slug. reasoning: '' | 'high' |
    'xhigh' (thinking mode). consistency: N>1 samples+majority-votes (short
    factual answers). context_file: absolute path bundled as cached prefix —
    for "is X implemented?" feed CODE (schema/routers), not docs.
    """
    cmd = [_cli("ask-deepseek"), *_model_flags(model)]
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
    """Fan out many prompts to DeepSeek in parallel (shared cached prefix).

    Returns JSON array of {index, prompt, output, ok}.
    """
    cmd = [_cli("ask-deepseek-batch"), "--json", "-j", str(jobs), *_model_flags(model)]
    if reasoning:
        cmd += ["-r", reasoning]
    if system:
        cmd += ["-s", system]
    if context_file:
        cmd += ["-c", context_file]
    return _run(cmd, stdin="\n".join(prompts) + "\n")


# --- or: generic OpenRouter intern (any model) ------------------------------

@mcp.tool()
def ask_or(
    prompt: str,
    model: str = "",
    reasoning: str = "",
    system: str = "",
    consistency: int = 0,
    context_file: str = "",
    max_tokens: int = 0,
) -> str:
    """Call ANY OpenRouter model — you pick the slug.

    model: REQUIRED OpenRouter slug (e.g. 'openai/gpt-5', 'anthropic/claude-
    opus-4', 'google/gemini-3-pro') or set OPENROUTER_MODEL env; no silent
    default. reasoning: '' | 'high' | 'xhigh'. consistency: N>1 votes (short
    answers). context_file: absolute path bundled as cached prefix.
    """
    cmd = [_cli("ask-or")]
    if model:
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
def ask_or_batch(
    prompts: list[str],
    model: str = "",
    reasoning: str = "",
    system: str = "",
    context_file: str = "",
    jobs: int = 4,
) -> str:
    """Fan out many prompts to one OpenRouter model in parallel.

    Returns JSON array of {index, prompt, output, ok}.
    """
    cmd = [_cli("ask-or-batch"), "--json", "-j", str(jobs)]
    if model:
        cmd += ["-m", model]
    if reasoning:
        cmd += ["-r", reasoning]
    if system:
        cmd += ["-s", system]
    if context_file:
        cmd += ["-c", context_file]
    return _run(cmd, stdin="\n".join(prompts) + "\n")


# --- gemini: vision intern --------------------------------------------------

@mcp.tool()
def ask_gemini(
    prompt: str,
    files: list[str] | None = None,
    model: str = "",
    consistency: int = 0,
) -> str:
    """Delegate visual analysis to the Gemini (vision) intern.

    files: absolute paths to image/video/doc to look at (repeatable). model:
    '' (default) | 'flash' (cheap) | 'pro' (most capable) | explicit name.
    consistency: N>1 votes — only for discrete answers (counts, yes/no, OCR).
    """
    cmd = [_cli("ask-gemini")]
    if model == "flash":
        cmd.append("--flash")
    elif model == "pro":
        cmd.append("--pro")
    elif model:
        cmd += ["-m", model]
    for f in files or []:
        cmd += ["-f", f]
    if consistency and consistency > 1:
        cmd += ["-c", str(consistency)]
    cmd.append(prompt)
    return _run(cmd)


@mcp.tool()
def ask_gemini_batch(
    prompts: list[str],
    context_file: str = "",
    model: str = "",
    jobs: int = 4,
) -> str:
    """Fan out many Gemini questions over one shared media file (mode 2).

    context_file: the shared image/video all prompts ask about. Returns JSON
    array of {index, label, output, ok}.
    """
    cmd = [_cli("ask-gemini-batch"), "--json", "-j", str(jobs)]
    if model == "flash":
        cmd.append("--flash")
    elif model == "pro":
        cmd.append("--pro")
    elif model:
        cmd += ["-m", model]
    if context_file:
        cmd += ["-c", context_file]
    return _run(cmd, stdin="\n".join(prompts) + "\n")


@mcp.tool()
def ask_gemini_code(prompt: str, apply: bool = False, worktree: bool = False,
                    cd: str = "", model: str = "") -> str:
    """Gemini as a coding intern — reads/edits a real repo (not vision).

    apply=False (default) = read-only review/understanding (plan mode).
    apply=True = edit files (auto_edit); caller should set worktree=True and
    review the diff, never merge blind. cd: working root. Good for high-volume
    or parallel coding, visual/frontend work, or a cross-family review of a diff.
    """
    cmd = [_cli("ask-gemini-code")]
    if apply:
        cmd.append("--apply")
    if worktree:
        cmd.append("--worktree")
    if cd:
        cmd += ["-C", cd]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)
    return _run(cmd)


# --- recraft: SVG vector image generation -----------------------------------

@mcp.tool()
def ask_recraft(prompt: str, out: str = "", image: str = "") -> str:
    """Generate an SVG vector graphic (Recraft V4.1 Vector via OpenRouter).

    Writes an .svg file and returns its absolute path. out: output path
    (default auto-named in cwd). image: optional single input image to guide
    the result. For icons/logos/illustrations — designed, not photographed.
    """
    cmd = [_cli("ask-recraft")]
    if out:
        cmd += ["-o", out]
    if image:
        cmd += ["-i", image]
    cmd.append(prompt)
    return _run(cmd)


# --- codex: agentic coding intern -------------------------------------------

@mcp.tool()
def ask_codex(
    prompt: str,
    apply: bool = False,
    cd: str = "",
    context_file: str = "",
    model: str = "",
    consistency: int = 0,
) -> str:
    """Delegate a coding task to the Codex intern.

    apply=False (default) = read-only Q&A / code review (safe, no writes).
    apply=True = AGENTIC file edits (sandbox=workspace-write) — caller MUST run
    in a throwaway git worktree (set `cd`) and review the diff; never merge
    blind. cd: working root. consistency rejected when apply=True.
    """
    cmd = [_cli("ask-codex")]
    if apply:
        cmd.append("--apply")
    if cd:
        cmd += ["-C", cd]
    if context_file:
        cmd += ["-f", context_file]
    if model:
        cmd += ["-m", model]
    if consistency and consistency > 1 and not apply:
        cmd += ["-c", str(consistency)]
    cmd.append(prompt)
    return _run(cmd)


@mcp.tool()
def ask_codex_batch(
    prompts: list[str],
    cd: str = "",
    model: str = "",
    jobs: int = 4,
) -> str:
    """Fan out many READ-ONLY codex questions in parallel.

    No agentic mode (batching mutations would race). cd: shared working root.
    Returns JSON array of {index, label, output, ok}.
    """
    cmd = [_cli("ask-codex-batch"), "--json", "-j", str(jobs)]
    if cd:
        cmd += ["-C", cd]
    if model:
        cmd += ["-m", model]
    return _run(cmd, stdin="\n".join(prompts) + "\n")


if __name__ == "__main__":
    mcp.run()
