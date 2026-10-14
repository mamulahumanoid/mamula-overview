from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class JointFrame:
    names: List[str]
    positions: List[float]


class PrintJointSink:
    """
    ROS'suz debug için joint log sink'i.

    - max_pairs: logda en fazla kaç eklemi yazalım
    - every_n: her N frame'de bir log bas (tick tabanlı throttle)
    - every_sec: en az kaç saniyede bir log bas (zaman tabanlı throttle)
    - prefix: log prefix

    Notlar:
    - every_sec > 0 ise zaman tabanlı throttle devreye girer.
    - every_n > 0 ise frame sayacı da uygulanır.
    - İkisi birlikte verilirse, ikisi de sağlanınca log basılır (AND).
    """

    def __init__(
        self,
        max_pairs: int = 8,
        every_n: int = 1,
        every_sec: float = 0.0,
        prefix: str = "[joint_sink]",
    ):
        self.max_pairs = int(max_pairs) if max_pairs and max_pairs > 0 else 8
        self.every_n = int(every_n) if every_n and every_n > 0 else 1
        self.every_sec = float(every_sec) if every_sec and every_sec > 0 else 0.0
        self.prefix = str(prefix or "[joint_sink]")

        self._counter = 0
        self._last_ts = 0.0

    def send(self, frame: JointFrame):
        self._counter += 1

        # Frame-tabanlı throttle
        if (self._counter % self.every_n) != 0:
            return

        # Zaman-tabanlı throttle
        if self.every_sec > 0.0:
            now = time.monotonic()
            if self._last_ts > 0.0 and (now - self._last_ts) < self.every_sec:
                return
            self._last_ts = now

        names = frame.names or []
        pos = frame.positions or []
        n = min(len(names), len(pos), self.max_pairs)

        pairs = ", ".join(f"{names[i]}:{pos[i]:.2f}" for i in range(n))
        suffix = " ..." if len(names) > n else ""
        print(f"{self.prefix} {pairs}{suffix}")
