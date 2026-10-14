from __future__ import annotations

from core.app import main as app_main


def main() -> int:
    return app_main(["--profile", "dev"])


if __name__ == "__main__":
    raise SystemExit(main())
