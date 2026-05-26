"""kuli.openrouter — shared OpenRouter chat-completions plumbing.

Both the `deepseek` preset and the generic `or` intern speak to the same
OpenRouter API; this module holds the HTTP call, payload assembly, response
extraction, and usage formatting so neither CLI duplicates it. Each caller
passes its own ``die`` (so errors carry the right tool name).
"""
import json
import urllib.error
import urllib.request

from . import health

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def build_messages(system, user):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return msgs


def build_payload(model, messages, temperature, max_tokens, json_mode=False, reasoning=None):
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "usage": {"include": True},
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if reasoning:
        payload["reasoning"] = {"effort": reasoning}
    return payload


def call_api(payload, key, timeout, die, title="kuli", intern=None):
    """POST to OpenRouter. On failure, record intern health (if given) then die."""
    def fail(msg):
        if intern:
            health.record_failure(intern, msg, 2)
        die(msg, 2)

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://claude-code.local/kuli",
            "X-Title": title,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        fail(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')}")
    except TimeoutError:
        fail(f"timed out after {timeout}s — raise --timeout or lower --reasoning effort")
    except urllib.error.URLError as e:
        fail(f"network error: {e.reason}")


def extract(data, die):
    """Return (final_answer, thinking, usage). thinking may be empty."""
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError):
        die(f"unexpected response: {json.dumps(data)[:500]}", 2)
    thinking = msg.get("reasoning") or msg.get("reasoning_content") or ""
    final = msg.get("content") or thinking
    if not final:
        die(f"empty content: {json.dumps(data)[:500]}", 2)
    return final, thinking, data.get("usage", {})


def format_usage(model, usage):
    pt = usage.get("prompt_tokens", "?")
    ct = usage.get("completion_tokens", "?")
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    line = f"[{model} | in {pt} out {ct} tok"
    if cached:
        line += f" | cached {cached} (~0.25x)"
    if usage.get("cache_discount") is not None:
        line += f" | discount ${usage['cache_discount']:.6f}"
    return line + "]"


def sum_usage(usages):
    total = {"prompt_tokens": 0, "completion_tokens": 0}
    for u in usages:
        total["prompt_tokens"] += u.get("prompt_tokens", 0)
        total["completion_tokens"] += u.get("completion_tokens", 0)
    return total
