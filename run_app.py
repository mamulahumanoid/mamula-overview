from __future__ import annotations

import os
import sys

from core.app import main as app_main
from core.utils.optional_deps import MissingExtraError


def _print_production_gate_hint(exc: RuntimeError) -> None:
    print(str(exc), file=sys.stderr)
    print("", file=sys.stderr)
    print("Local voice/smoke test icin production profili yerine guvenli bir profil secin:", file=sys.stderr)
    print("  HUMANOID_RUNTIME_PROFILE=embodied_interactive python -m core.run_app", file=sys.stderr)
    print("  # veya sadece cekirdek/router smoke:", file=sys.stderr)
    print("  HUMANOID_RUNTIME_PROFILE=minimal python -m core.run_app", file=sys.stderr)
    print("", file=sys.stderr)
    print("Production shadow bring-up icin once shadow komut gunlugunu acin:", file=sys.stderr)
    print("  MAMULA_HARDWARE_SHADOW_COMMANDS=1 HUMANOID_RUNTIME_PROFILE=production python -m core.run_app", file=sys.stderr)
    print("", file=sys.stderr)
    print("Ses HTTP router'i icin gerekirse:", file=sys.stderr)
    print('  pip install -e ".[web]"', file=sys.stderr)


def _print_missing_extra_hint(exc: MissingExtraError) -> None:
    print(f"core.run_app: missing optional dependency for {exc.capability}.", file=sys.stderr)
    print(f"  {exc}", file=sys.stderr)
    print(f'  Bu repo icin: pip install -e ".[{exc.extra}]"', file=sys.stderr)


def main() -> int:
    prof = (
        os.getenv("HUMANOID_RUNTIME_PROFILE", "").strip()
        or os.getenv("CORE_RUNTIME_PROFILE", "").strip()
        or "production"
    )
    try:
        return app_main(["--profile", prof])
    except MissingExtraError as exc:
        _print_missing_extra_hint(exc)
        return 2
    except RuntimeError as exc:
        if "production maturity gate failed" in str(exc):
            _print_production_gate_hint(exc)
            return 2
        raise


if __name__ == "__main__":
    raise SystemExit(main())
