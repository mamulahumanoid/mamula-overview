"""Module lifecycle contract (humanoid OS roadmap).

Modüller isteğe bağlı aşağıdaki faz hook'larını uygular; yoksa atlanır.
Faz isimleri: configure, start, ready, tick, pause, stop, fault, recover

``tick`` zaten yaygın; diğerleri kademeli taşıma için rezerve edilir.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Tuple

# Canonical phase names (string stable API)
CONFIGURE = "configure"
START = "start"
READY = "ready"
TICK = "tick"
PAUSE = "pause"
STOP = "stop"
FAULT = "fault"
RECOVER = "recover"

STARTUP_PHASES: Tuple[str, ...] = (CONFIGURE, START, READY)


def _resolve_callable(module: Any, phase: str) -> Callable[..., Any] | None:
    fn = getattr(module, phase, None)
    if callable(fn):
        return fn
    if phase == READY:
        alt = getattr(module, "on_ready", None)
        if callable(alt):
            return alt
    return None


def apply_phase(module: Any, phase: str) -> bool:
    """Call a single lifecycle hook if present. Returns True if invoked."""
    fn = _resolve_callable(module, phase)
    if fn is None:
        return False
    fn()
    return True


def apply_startup_phases(
    modules: Iterable[Any],
    *,
    on_error: Callable[[str, str, BaseException], None],
) -> None:
    """Run configure → start → ready in order for each module."""
    for m in modules:
        for phase in STARTUP_PHASES:
            fn = _resolve_callable(m, phase)
            if fn is None:
                continue
            try:
                fn()
            except Exception as exc:
                name = getattr(m, "name", m.__class__.__name__)
                on_error(phase, str(name), exc)
