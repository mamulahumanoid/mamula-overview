from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from core.bus.event_bus import EventBus
from core.adapters.http_deployment_security import enforce_http_deployment_security, protected_http_deployment
from core.runtime.bootstrap import RuntimeBootstrap
from core.runtime.runtime import Runtime, RuntimeConfig
from core.runtime.deployment_status import (
    clear_runtime_context,
    mark_runtime_stopping,
    register_runtime_context,
)
from core.utils.optional_deps import import_optional


DEFAULT_PROFILE = "production"
_ENV_PROFILE_KEYS = ("HUMANOID_RUNTIME_PROFILE", "CORE_RUNTIME_PROFILE")


def profile_from_env(fallback: str = DEFAULT_PROFILE) -> str:
    for key in _ENV_PROFILE_KEYS:
        raw = os.getenv(key, "").strip()
        if raw:
            return raw.lower()
    return fallback


def _http_bind() -> tuple[str, int]:
    host = (os.getenv("CORE_HTTP_HOST", "0.0.0.0") or "0.0.0.0").strip()
    port_raw = (os.getenv("CORE_HTTP_PORT", "8777") or "8777").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 8777
    return host, port


@dataclass
class AppContext:
    bus: EventBus
    runtime: Runtime
    bootstrap: RuntimeBootstrap
    router_thread: Optional[threading.Thread] = None
    profile: str = DEFAULT_PROFILE
    _closed: bool = field(default=False, init=False, repr=False)
    _close_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def closed(self) -> bool:
        with self._close_lock:
            return self._closed

    def close(self) -> None:
        """Idempotently stop every resource owned by this application context."""

        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        mark_runtime_stopping()
        for close_fn in (
            self.runtime.request_shutdown,
            self.runtime.shutdown,
            self.bootstrap.close_all,
            self.bus.close,
        ):
            try:
                close_fn()
            except Exception:
                pass
        clear_runtime_context(expected_bootstrap=self.bootstrap)

    def __enter__(self) -> "AppContext":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()


def make_runtime_config(*, tick_hz: int = 200, watchdog_ms: int = 750) -> RuntimeConfig:
    return RuntimeConfig(tick_hz=tick_hz, watchdog_ms=watchdog_ms)


def _load_waitress_serve() -> Callable[..., Any]:
    waitress = import_optional(
        "waitress",
        capability="production HTTP WSGI server",
        extra="web",
    )
    serve = getattr(waitress, "serve", None)
    if not callable(serve):
        raise RuntimeError("production HTTP WSGI server is unavailable: waitress.serve is not callable")
    return serve


def _serve_http_app(http_app: Any, *, profile: str, host: str, port: int) -> None:
    if protected_http_deployment(profile):
        serve = _load_waitress_serve()
        print(f"[core.app] HTTP server=waitress bind={host}:{port}")
        serve(http_app, host=host, port=port)
        return
    print(f"[core.app] HTTP server=flask-development bind={host}:{port}")
    http_app.run(host=host, port=port, debug=False, use_reloader=False)


def start_http_router(*, host: str = "0.0.0.0", port: int = 8777, profile: str = DEFAULT_PROFILE) -> None:
    from core.adapters.http_voice_router import main as http_router_main

    try:
        http_router_main(host=host, port=port, profile=profile)
    except OSError as exc:
        print(
            f"[core.app] HTTP router could not bind {host}:{port}: {exc}. "
            "Set CORE_HTTP_HOST/CORE_HTTP_PORT or run with --no-http-router.",
            file=sys.stderr,
        )


def _ensure_http_router_dependencies(*, profile: str) -> None:
    import_optional("flask", capability="embedded HTTP voice router", extra="web")
    if protected_http_deployment(profile):
        _load_waitress_serve()


def _should_start_http_router(explicit: Optional[bool]) -> bool:
    if explicit is not None:
        return bool(explicit)
    raw = os.getenv("CORE_HTTP_ROUTER", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _mirror_runtime_security_to_global_bus_if_needed(bus: EventBus) -> None:
    try:
        status = bus.transport_status()
        enforced = bool(status.get("topic_security_enforced", False))
        envelope_mode = str(status.get("envelope_mode", "") or "").strip().lower()
    except Exception:
        enforced = False
        envelope_mode = ""
    if not enforced:
        return
    global_bus = EventBus.get_global()
    setter = getattr(global_bus, "set_topic_security_enforcement", None)
    if callable(setter):
        setter(True)
    envelope_setter = getattr(global_bus, "set_envelope_mode", None)
    if callable(envelope_setter) and envelope_mode in {"normalize", "strict"}:
        envelope_setter(envelope_mode)


def create_app(
    profile: Optional[str] = None,
    *,
    start_router: Optional[bool] = None,
    bus: Optional[EventBus] = None,
    runtime_config: Optional[RuntimeConfig] = None,
) -> AppContext:
    if profile is None:
        requested_profile = profile_from_env()
    else:
        requested_profile = str(profile or DEFAULT_PROFILE).strip().lower()
    bus = bus or EventBus.get_global()
    runtime = Runtime(bus, runtime_config or make_runtime_config())
    bootstrap = RuntimeBootstrap(bus, runtime)
    resolved_profile = bootstrap.normalize_profile(requested_profile)
    http_deployment_profile = (
        requested_profile if protected_http_deployment(requested_profile) else resolved_profile
    )
    router_enabled = _should_start_http_router(start_router)
    bind_host, bind_port = _http_bind()
    if router_enabled:
        enforce_http_deployment_security(profile=http_deployment_profile, host=bind_host)
        _ensure_http_router_dependencies(profile=http_deployment_profile)
    bootstrap.attach_profile(resolved_profile)
    _mirror_runtime_security_to_global_bus_if_needed(bus)
    register_runtime_context(profile=resolved_profile, bootstrap=bootstrap, bus=bus, runtime=runtime)

    router_thread = None
    if router_enabled:
        router_thread = threading.Thread(
            target=start_http_router,
            kwargs={"host": bind_host, "port": bind_port, "profile": http_deployment_profile},
            daemon=True,
            name="core-http-router",
        )
        router_thread.start()

    return AppContext(
        bus=bus,
        runtime=runtime,
        bootstrap=bootstrap,
        router_thread=router_thread,
        profile=resolved_profile,
    )


def run_app(profile: Optional[str] = None, *, start_router: Optional[bool] = None) -> AppContext:
    ctx = create_app(profile=profile, start_router=start_router)
    _h, bind_port = _http_bind()
    print(
        f"[core.app] profile={ctx.profile} modules={len(ctx.bootstrap.load_order)} "
        f"POST http://127.0.0.1:{bind_port}/stt/final {{text, lang?, confidence?}} "
        f"(varsayılan yerel ayar: CORE_DEFAULT_LOCALE)"
    )
    previous_handlers: dict[int, object] = {}

    def _request_shutdown(signum, _frame) -> None:
        print(f"[core.app] received signal={signum}; graceful shutdown requested")
        mark_runtime_stopping()
        ctx.runtime.request_shutdown()

    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, _request_shutdown)
    try:
        ctx.runtime.run_forever()
    finally:
        ctx.close()
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)
        print("[core.app] graceful shutdown complete")
    return ctx


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the consolidated core application entrypoint.")
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Runtime stack profile or alias to attach.",
    )
    parser.add_argument(
        "--no-http-router",
        action="store_true",
        help="Disable the embedded HTTP STT router thread.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    run_app(profile=args.profile, start_router=not args.no_http_router)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
