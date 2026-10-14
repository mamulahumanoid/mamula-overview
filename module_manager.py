"""Module manager — lifecycle orchestration (v1).

Tam süpervizör + çok proses yönetimi ayrı bileşenlerde (health endpoint, cgroups, …)
ileride genişler; bu sınıf tek süreç içi yaşam döngüsü ve tick politikası köprüsüdür.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional, Tuple


class ModuleManager:
    def __init__(self, modules: Iterable[Any]):
        self._modules: List[Any] = list(modules)

    def modules(self) -> List[Any]:
        return list(self._modules)

    def apply_startup(self, on_error: Callable[[str, str, BaseException], None]) -> None:
        from core.runtime.module_lifecycle_v1 import STARTUP_PHASES, _resolve_callable

        for m in self._modules:
            for phase in STARTUP_PHASES:
                fn = _resolve_callable(m, phase)
                if fn is None:
                    continue
                try:
                    fn()
                except Exception as exc:
                    name = getattr(m, "name", m.__class__.__name__)
                    on_error(phase, str(name), exc)

    @staticmethod
    def tick_supervised(
        modules: Iterable[Any],
        *,
        timeout_s: float,
        on_timeout: Callable[[str], None],
        on_tick_error: Callable[[str, BaseException], None],
        executor: Optional[Any] = None,
    ) -> None:
        """Run each module ``tick`` under a per-call timeout (single worker thread).

        Not: ``concurrent.futures`` zaman aşımında çalışan işi iptal etmez; gerçek izolasyon
        için proses sınırı gerekir. Bu mod yine de bloklanmış tick'leri tespit edip raporlar.
        """
        from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, TimeoutError as FUTimeout
        from concurrent.futures import wait

        from core.runtime.module_lifecycle_v1 import TICK

        exec_close = False
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mamula-mod-tick")
            exec_close = True
        try:
            for m in modules:
                tick = getattr(m, TICK, None)
                if not callable(tick):
                    continue
                name = str(getattr(m, "name", m.__class__.__name__))
                fut = executor.submit(tick)
                done, _pending = wait([fut], timeout=timeout_s, return_when=FIRST_COMPLETED)
                if not done:
                    on_timeout(name)
                    continue
                f = next(iter(done))
                try:
                    f.result()
                except Exception as exc:
                    on_tick_error(name, exc)
        finally:
            if exec_close:
                executor.shutdown(wait=False, cancel_futures=True)
