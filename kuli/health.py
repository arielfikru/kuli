"""kuli.health — persistent intern health (advisory circuit-breaker).

KULI has no central dispatcher: Claude is the orchestrator and calls each
`ask-<intern>` itself. So this module is *advisory*, not an auto-router. Each
adapter reports the outcome of its backend call here; Claude reads `kuli health`
(or the skill consults it) before delegating, and decides the fallback. The
ladder helpers below just tell Claude which rungs are currently alive — they
never silently re-route, so the orchestrator always knows who ran.

Failure kinds, handled differently:
  - rate_limited : heals over TIME. Store `until` (epoch); past it = healthy.
    No reset time from the backend -> conservative default cooldown.
  - auth_failed  : does NOT heal over time. Only a later success (auto) or
    `health_reset()` (manual, after re-login) clears it.
  - generic      : ambiguous. Needs N consecutive fails before benching, so a
    single network blip doesn't kill a healthy intern. Heals on next success.

Stdlib only. Writes are atomic + flock-guarded so parallel `-batch` workers
don't clobber each other.
"""
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

HEALTH_PATH = Path(os.environ.get(
    "KULI_HEALTH_PATH", Path.home() / ".claude" / "kuli" / "health.json"))

DEFAULT_RATE_COOLDOWN_S = 20 * 60   # used when the backend gives no reset time
GENERIC_FAIL_THRESHOLD = 3          # consecutive generic fails before benching

HEALTHY, RATE_LIMITED, AUTH_FAILED, DEGRADED, DOWN = (
    "healthy", "rate_limited", "auth_failed", "degraded", "down")

# Fallback ladders: cheapest-preserving order. (intern, model_override|None).
# Advisory only — Claude reads the alive rungs and chooses; Claude itself is the
# implicit last rung beyond these.
FALLBACK_LADDERS = {
    "codex": [("codex", None), ("gemini", None), ("deepseek", None)],
    "gemini": [("gemini", None), ("codex", None), ("deepseek", None)],
    "deepseek": [("deepseek", None), ("or", None)],
    "or": [("or", None), ("deepseek", None)],
    "recraft": [("recraft", None)],
}

RATE_MARKERS = ("usage limit", "rate limit", "rate_limit", "quota",
                "resource_exhausted", "429", "too many requests", "exceeded your current")
AUTH_MARKERS = ("unauthorized", "401", "authentication", "not logged in", "please login",
                "please log in", "invalid api key", "no api key", "token_invalidated",
                "expired", "credentials", "login required")


def classify_error(stderr, exit_code):
    """Map a failed call to RATE_LIMITED | AUTH_FAILED | 'generic' by phrasing."""
    s = (stderr or "").lower()
    if any(m in s for m in RATE_MARKERS):
        return RATE_LIMITED
    if any(m in s for m in AUTH_MARKERS):
        return AUTH_FAILED
    return "generic"


def parse_reset_epoch(stderr):
    """Best-effort rate-limit reset time (epoch) from stderr, else None.
    Only explicit signals — never guess a duration from vague wording."""
    s = stderr or ""
    m = re.search(r"retry[-_ ]after[:=]?\s*(\d+)", s, re.IGNORECASE)
    if m:
        return time.time() + int(m.group(1))
    m = re.search(r"try again in\s+(\d+)\s*(second|minute|hour)", s, re.IGNORECASE)
    if m:
        mult = {"second": 1, "minute": 60, "hour": 3600}[m.group(2).lower()]
        return time.time() + int(m.group(1)) * mult
    return None


@contextmanager
def _locked_state():
    """Yield (state, save) holding an exclusive lock for the whole block."""
    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(HEALTH_PATH.with_suffix(".lock"), "w")
    try:
        try:
            import fcntl
            fcntl.flock(lock_file, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        state = _read()
        yield state, lambda: _atomic_write(state)
    finally:
        lock_file.close()


def _read():
    try:
        with open(HEALTH_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _atomic_write(state):
    fd, tmp = tempfile.mkstemp(dir=str(HEALTH_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
        os.replace(tmp, HEALTH_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def is_available(intern):
    """(available, reason). Self-heals an elapsed rate-limit window in place."""
    with _locked_state() as (state, save):
        entry = state.get(intern)
        if not entry:
            return True, "healthy"
        status = entry.get("status", HEALTHY)
        if status in (HEALTHY, DEGRADED):
            return True, status
        if status == RATE_LIMITED:
            until = entry.get("until", 0)
            if time.time() >= until:
                state[intern] = {"status": HEALTHY}
                save()
                return True, "recovered_from_rate_limit"
            return False, f"rate_limited (~{max(1, int((until - time.time()) / 60))} min left)"
        if status == AUTH_FAILED:
            return False, "auth_failed (needs re-login)"
        if status == DOWN:
            return False, "down (repeated failures)"
        return True, "unknown"


def record_success(intern):
    """A call succeeded -> clear any failure flag (auto-recovery, incl. auth)."""
    with _locked_state() as (state, save):
        if state.get(intern, {}).get("status", HEALTHY) != HEALTHY:
            state[intern] = {"status": HEALTHY}
            save()


def record_failure(intern, stderr, exit_code):
    """Record a failed call; return the classified kind."""
    kind = classify_error(stderr, exit_code)
    with _locked_state() as (state, save):
        if kind == RATE_LIMITED:
            until = parse_reset_epoch(stderr) or (time.time() + DEFAULT_RATE_COOLDOWN_S)
            state[intern] = {"status": RATE_LIMITED, "until": until}
        elif kind == AUTH_FAILED:
            state[intern] = {"status": AUTH_FAILED}
        else:
            prev = state.get(intern, {})
            count = (prev.get("fail_count", 0) + 1
                     if prev.get("status") in (DEGRADED, DOWN) else 1)
            state[intern] = {"status": DOWN if count >= GENERIC_FAIL_THRESHOLD else DEGRADED,
                             "fail_count": count}
        save()
    return kind


def health_reset(intern=None):
    """Manual reset: one intern, or all when intern is None (after re-login)."""
    with _locked_state() as (state, save):
        state.clear() if intern is None else state.pop(intern, None)
        save()


def health_status():
    """Snapshot for `kuli health`, annotated with minutes left on rate limits."""
    now, out = time.time(), {}
    for intern, entry in _read().items():
        e = dict(entry)
        if e.get("status") == RATE_LIMITED and "until" in e:
            e["minutes_left"] = max(0, int((e["until"] - now) / 60))
        out[intern] = e
    return out


def resolve_fallback(intern):
    """Alive rungs of intern's ladder, in priority order (advisory).

    Empty => every rung is dead; Claude escalates to itself. Skipped rungs and
    their reasons land in `resolve_fallback.last_skips` for transparent logging.
    """
    alive, skips = [], []
    for rung_intern, model in FALLBACK_LADDERS.get(intern, [(intern, None)]):
        ok, reason = is_available(rung_intern)
        (alive.append((rung_intern, model)) if ok
         else skips.append(f"{rung_intern}: {reason}"))
    resolve_fallback.last_skips = skips
    return alive
