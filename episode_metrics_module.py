from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.bus.event_bus import EventBus
from core.learning.policy_eval import (
    build_failure_taxonomy_dashboard,
    build_recovery_recommendations,
    evaluate_episode_dir,
)
from core.runtime.runtime import Runtime


def _now_ms() -> int:
    return int(time.time() * 1000)


class EpisodeMetricsModule:
    """Generate rolling runtime metrics and failure dashboard snapshots from episode files."""

    name = "episode_metrics"

    def __init__(
        self,
        bus: EventBus,
        rt: Runtime,
        episodes_dir: str = "./data/episodes/normalized",
        metrics_dir: str = "./data/metrics/daily",
        flush_interval_ms: int = 5000,
        write_latest: bool = True,
    ):
        self.bus = bus
        self.rt = rt
        self.episodes_dir = str(episodes_dir or "./data/episodes/normalized")
        self.metrics_dir = str(metrics_dir or "./data/metrics/daily")
        self.flush_interval_ms = max(1000, int(flush_interval_ms))
        self.write_latest = bool(write_latest)

        Path(self.episodes_dir).mkdir(parents=True, exist_ok=True)
        Path(self.metrics_dir).mkdir(parents=True, exist_ok=True)

        self._last_flush_ms = 0
        self._last_signature: Optional[str] = None
        self._last_report_path: str = ""
        self._last_dashboard_path: str = ""

        bus.subscribe("motion.status", self.on_activity)
        bus.subscribe("planner.plan_failed", self.on_activity)
        bus.subscribe("behavior.failed", self.on_activity)
        bus.subscribe("voice.task", self.on_activity)

        print(f"[episode.metrics] enabled -> episodes={self.episodes_dir} metrics={self.metrics_dir}")

    def tick(self):
        self.rt.beat(self.name)
        now = _now_ms()
        if (now - self._last_flush_ms) >= self.flush_interval_ms:
            self._flush_if_changed(force=False)

    def close(self):
        self._flush_if_changed(force=True)

    def on_activity(self, topic: str, msg: Any):
        del topic, msg
        now = _now_ms()
        if (now - self._last_flush_ms) >= self.flush_interval_ms:
            self._flush_if_changed(force=False)

    def _episode_files(self):
        return sorted(Path(self.episodes_dir).glob("ep_*.json"))

    def _compute_signature(self) -> str:
        parts = []
        for path in self._episode_files():
            try:
                st = path.stat()
                parts.append(f"{path.name}:{int(st.st_mtime_ns)}:{int(st.st_size)}")
            except FileNotFoundError:
                continue
        return "|".join(parts)

    def _write_json(self, path: str, payload: Dict[str, Any]):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _flush_if_changed(self, force: bool):
        self._last_flush_ms = _now_ms()
        signature = self._compute_signature()
        if (not force) and signature == self._last_signature:
            return

        report = evaluate_episode_dir(self.episodes_dir)
        dashboard = build_failure_taxonomy_dashboard(report)
        recovery_report = build_recovery_recommendations(report)
        generated_at_ms = _now_ms()
        report["runtime"] = {
            "generated_at_ms": generated_at_ms,
            "episodes_dir": self.episodes_dir,
            "metrics_dir": self.metrics_dir,
            "episode_file_count": len(self._episode_files()),
            "dashboard_enabled": True,
        }
        report["quality"] = {
            "avg_reward": float(report.get("summary", {}).get("avg_reward", 0.0) or 0.0),
            "quality_band_counts": dict(report.get("quality_band_counts", {})),
            "failure_family_counts": dict(report.get("failure_family_counts", {})),
            "recovery_counts": dict(report.get("recovery_counts", {})),
        }
        dashboard["runtime"] = {
            "generated_at_ms": generated_at_ms,
            "episodes_dir": self.episodes_dir,
            "metrics_dir": self.metrics_dir,
            "source_report": "episode_metrics",
        }
        recovery_report["runtime"] = {
            "generated_at_ms": generated_at_ms,
            "episodes_dir": self.episodes_dir,
            "metrics_dir": self.metrics_dir,
            "source_report": "episode_metrics",
        }

        date_tag = time.strftime("%Y%m%d")
        dated_path = os.path.join(self.metrics_dir, f"episode_metrics_{date_tag}.json")
        self._write_json(dated_path, report)

        dashboard_dated_path = os.path.join(self.metrics_dir, f"failure_taxonomy_{date_tag}.json")
        self._write_json(dashboard_dated_path, dashboard)

        recovery_dated_path = os.path.join(self.metrics_dir, f"recovery_recommendations_{date_tag}.json")
        self._write_json(recovery_dated_path, recovery_report)

        latest_path = ""
        latest_dashboard_path = ""
        latest_recovery_path = ""
        if self.write_latest:
            latest_path = os.path.join(self.metrics_dir, "episode_metrics_latest.json")
            self._write_json(latest_path, report)
            latest_dashboard_path = os.path.join(self.metrics_dir, "failure_taxonomy_latest.json")
            self._write_json(latest_dashboard_path, dashboard)
            latest_recovery_path = os.path.join(self.metrics_dir, "recovery_recommendations_latest.json")
            self._write_json(latest_recovery_path, recovery_report)

        payload = {
            "report_path": dated_path,
            "latest_path": latest_path,
            "dashboard_path": dashboard_dated_path,
            "dashboard_latest_path": latest_dashboard_path,
            "summary": report.get("summary", {}),
            "quality": report.get("quality", {}),
            "recovery": recovery_report.get("summary", {}),
            "generated_at_ms": generated_at_ms,
        }
        self.bus.publish("episode.metrics", payload)
        self.bus.publish("episode.metrics_written", payload)
        self.bus.publish(
            "episode.failure_dashboard",
            {
                "report_path": dashboard_dated_path,
                "latest_path": latest_dashboard_path,
                "summary": dashboard.get("summary", {}),
                "top_failure_families": dashboard.get("top_failure_families", []),
                "task_risk_ranking": dashboard.get("task_risk_ranking", []),
                "generated_at_ms": generated_at_ms,
            },
        )
        self.bus.publish(
            "episode.failure_dashboard_written",
            {
                "report_path": dashboard_dated_path,
                "latest_path": latest_dashboard_path,
                "generated_at_ms": generated_at_ms,
            },
        )
        self.bus.publish(
            "episode.recovery_recommendations",
            {
                "report_path": recovery_dated_path,
                "latest_path": latest_recovery_path,
                "summary": recovery_report.get("summary", {}),
                "recommendations": recovery_report.get("recommendations", []),
                "task_retry_suggestions": recovery_report.get("task_retry_suggestions", []),
                "generated_at_ms": generated_at_ms,
            },
        )
        self.bus.publish(
            "episode.recovery_recommendations_written",
            {
                "report_path": recovery_dated_path,
                "latest_path": latest_recovery_path,
                "generated_at_ms": generated_at_ms,
            },
        )

        self._last_signature = signature
        self._last_report_path = dated_path
        self._last_dashboard_path = dashboard_dated_path
