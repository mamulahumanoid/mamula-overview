"""Declarative module load-order constraints (dependency graph, v1).

Kural: ``dependent`` yüklenmeden önce ``any_preceding`` listesinden *load_order içinde
bulunan* en az bir modül daha önce gelmiş olmalı (perception → world_model gibi).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class LoadOrderRule:
    dependent: str
    any_preceding: Tuple[str, ...]


# Minimum policy set; profiller büyüdükçe genişletilir.
DEFAULT_RULES: Tuple[LoadOrderRule, ...] = (
    LoadOrderRule(
        "world_model",
        (
            "perception_hardware_bridge",
            "perception_world_state_bridge",
            "fake_perception",
            "sim_perception_seed",
            "scene_understanding",
        ),
    ),
    LoadOrderRule(
        "locomotion_bringup",
        ("hardware_bridge", "hal_runtime_bridge"),
    ),
    LoadOrderRule(
        "local_motion_planner",
        ("hardware_bridge", "hal_runtime_bridge"),
    ),
    LoadOrderRule("base_state_ekf", ("canonical_robot_model",)),
    LoadOrderRule("real_qp_solver", ("canonical_robot_model",)),
    LoadOrderRule("whole_body_inverse_kinematics", ("canonical_robot_model",)),
    LoadOrderRule("whole_body_inverse_dynamics", ("canonical_robot_model",)),
)


def validate_load_order(load_order: Sequence[str], rules: Sequence[LoadOrderRule] = DEFAULT_RULES) -> List[str]:
    """Return human-readable violation messages (empty if ok)."""
    order = [str(x).strip() for x in load_order if str(x).strip()]
    idx = {name: i for i, name in enumerate(order)}
    violations: List[str] = []
    for rule in rules:
        dep = rule.dependent
        if dep not in idx:
            continue
        present = [p for p in rule.any_preceding if p in idx]
        if not present:
            continue
        dep_i = idx[dep]
        last_prereq = max(idx[p] for p in present)
        if last_prereq >= dep_i:
            violations.append(
                f"load_order: {dep} must load after at least one of {present} "
                f"(got indices prereq_max={last_prereq} dep={dep_i})"
            )
    return violations
