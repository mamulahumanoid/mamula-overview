# core/modules/base_module.py
from __future__ import annotations

from typing import Any, Optional


class BaseModule:
    """Minimal base class for modules.

    This repository historically referenced `core.modules.base_module.BaseModule`.
    Some modules only need a shared place to store `bus`, `runtime`, and `name`.

    Methods are intentionally no-ops so each module can implement what it needs.
    """

    name: str = "base_module"

    def __init__(self, bus: Any, runtime: Any, name: Optional[str] = None, **kwargs: Any) -> None:
        self.bus = bus
        self.runtime = runtime
        if name:
            self.name = name

    def start(self) -> None:
        """Optional lifecycle hook."""
        return None

    def stop(self) -> None:
        """Optional lifecycle hook."""
        return None

    def beat(self) -> None:
        """Best-effort heartbeat helper."""
        try:
            if getattr(self, "runtime", None) is not None:
                self.runtime.beat(getattr(self, "name", self.__class__.__name__))
        except Exception:
            pass
