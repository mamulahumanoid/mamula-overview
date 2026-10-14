# core/skills/skill_base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


Step = Dict[str, Any]


@dataclass
class SkillMatch:
    matched: bool
    confidence: float = 0.0
    reason: str = ""


class Skill(Protocol):
    name: str

    def match(self, text: str) -> SkillMatch: ...
    def build_steps(self, text: str) -> List[Step]: ...


def _norm(s: str) -> str:
    return (s or "").strip()
