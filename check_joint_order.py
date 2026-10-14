from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from core.contract.joints import canonical_joint_names
from core.modules.motion_engine import MotionEngine


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUS_MAP_PATH = WORKSPACE_ROOT / "core" / "config" / "vendor_servo_bus_map.json"
CANONICAL_EXPECTED = canonical_joint_names()


def load_vendor_joint_entries(bus_map_path: str | Path = DEFAULT_BUS_MAP_PATH) -> List[Dict[str, Any]]:
    path = Path(bus_map_path)
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries: List[Dict[str, Any]] = []
    for joint_name, cfg in dict(payload.get("joints", {}) or {}).items():
        joint_cfg = dict(cfg or {})
        entries.append(
            {
                "joint": str(joint_name),
                "node_id": int(joint_cfg.get("node_id", 0) or 0),
                "bus": str(joint_cfg.get("bus", "unknown") or "unknown"),
            }
        )
    return sorted(entries, key=lambda item: (int(item.get("node_id", 0) or 0), str(item.get("joint", ""))))


def load_vendor_joint_order(bus_map_path: str | Path = DEFAULT_BUS_MAP_PATH) -> List[str]:
    return [str(entry.get("joint", "") or "") for entry in load_vendor_joint_entries(bus_map_path)]


SERVO_EXPECTED = load_vendor_joint_order()


def build_motion_engine_joint_order(joint_names: Iterable[str] | None = None) -> List[str]:
    engine = MotionEngine(list(joint_names or CANONICAL_EXPECTED))
    return list(engine.build_stand_pose().keys())


def compare_joint_orders(expected: Iterable[str], observed: Iterable[str]) -> Dict[str, Any]:
    expected_list = [str(name or "") for name in expected]
    observed_list = [str(name or "") for name in observed]
    missing = [name for name in expected_list if name not in observed_list]
    extra = [name for name in observed_list if name not in expected_list]
    first_mismatch: Dict[str, Any] | None = None
    for index, (exp_name, obs_name) in enumerate(zip(expected_list, observed_list)):
        if exp_name != obs_name:
            first_mismatch = {"index": index, "expected": exp_name, "observed": obs_name}
            break
    if first_mismatch is None and len(expected_list) != len(observed_list):
        first_mismatch = {
            "index": min(len(expected_list), len(observed_list)),
            "expected": expected_list[len(observed_list)] if len(expected_list) > len(observed_list) else "",
            "observed": observed_list[len(expected_list)] if len(observed_list) > len(expected_list) else "",
        }
    return {
        "matches": expected_list == observed_list,
        "expected_count": len(expected_list),
        "observed_count": len(observed_list),
        "missing": missing,
        "extra": extra,
        "first_mismatch": first_mismatch or {},
    }


def main() -> None:
    motion_names = build_motion_engine_joint_order()
    vendor_entries = load_vendor_joint_entries()
    vendor_names = [str(entry.get("joint", "") or "") for entry in vendor_entries]

    motion_vs_canonical = compare_joint_orders(CANONICAL_EXPECTED, motion_names)
    canonical_vs_vendor = compare_joint_orders(CANONICAL_EXPECTED, vendor_names)

    print("\n--- Canonical 28 DOF order ---")
    for index, name in enumerate(CANONICAL_EXPECTED, start=1):
        print(index, name)

    print("\n--- MotionEngine stand-pose order ---")
    for index, name in enumerate(motion_names, start=1):
        print(index, name)

    print("\n--- Vendor node order ---")
    for entry in vendor_entries:
        print(entry["node_id"], entry["joint"], entry["bus"])

    print("\nMotionEngine vs canonical:", motion_vs_canonical["matches"])
    print("Canonical vs vendor node order:", canonical_vs_vendor["matches"])
    if canonical_vs_vendor["first_mismatch"]:
        print("First canonical/vendor mismatch:", canonical_vs_vendor["first_mismatch"])
        print("Note: vendor transport is name-based, so legacy node IDs can differ from canonical joint order.")


if __name__ == "__main__":
    main()
