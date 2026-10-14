"""Compatibility re-exports.

Some modules historically imported contract types via `core.messages`.
The project now keeps these dataclasses under `core.contract`.

§6 öğrenme bus topic ve şema sabitleri: ``core.contract.learning_stack_v1``.
§7 çok modlu etkileşim: ``core.contract.multimodal_interaction_v1``.
§8 güvenlik (çarpışma / düşme / insan): ``core.contract.safety_system_v1``.
§9 simülasyon zekâsı (sentetik veri, kitlesel test): ``core.contract.simulation_intelligence_v1``.
§10 robot tanılama (batarya, sıcaklık, tork, sensör): ``core.contract.robot_diagnostics_v1``.
§11–§12 dil sistemi (çok dil, ASR/LLM/TTS boru hattı): ``core.contract.language_system_v1``.
§13–§14 entegrasyon referansı (Atlas/Pepper/NAO, yığın önerileri): ``core.contract.humanoid_integration_reference``.

Keep this module tiny and stable so older imports keep working.
"""

from __future__ import annotations

# Re-export commonly used message/contract dataclasses.

try:
    from core.contract.types import Meta  # type: ignore
except Exception:  # pragma: no cover
    Meta = None  # type: ignore

try:
    from core.contract.commands import CommandIssued, MotionStatus  # type: ignore
except Exception:  # pragma: no cover
    CommandIssued = None  # type: ignore
    MotionStatus = None  # type: ignore

__all__ = [
    "Meta",
    "CommandIssued",
    "MotionStatus",
]
