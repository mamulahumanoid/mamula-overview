from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ModuleSpec:
    """Runtime module wiring.

    Maturity fields are optional; when unset, :mod:`core.runtime.module_maturity` infers
    metadata from the registry and import-path heuristics (production gate uses the result).
    """

    name: str
    import_path: str
    kwargs: Dict[str, Any]
    module_maturity: Optional[str] = None  # stub | experimental | sim_ready | hil_ready | hardware_ready | production
    safety_class: Optional[str] = None  # non_motion | low_risk | high_risk | critical
    realtime_safe: Optional[bool] = None
    hardware_allowed: Optional[bool] = None
