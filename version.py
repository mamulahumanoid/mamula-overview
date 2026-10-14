from __future__ import annotations

import re

VERSION = "0.5.4"
__version__ = VERSION
RELEASE_TAG_PREFIX = "v"
SOURCE_RELEASE_ARCHIVE_PREFIX = "humanoid_core_source"

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def is_valid_semver(value: str) -> bool:
    return bool(_SEMVER_RE.match(str(value or "").strip()))


def version_info(value: str = VERSION) -> tuple[int, int, int]:
    match = _SEMVER_RE.match(str(value or "").strip())
    if not match:
        raise ValueError(f"invalid semantic version: {value!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def release_tag(value: str = VERSION) -> str:
    """Return the canonical git release tag for a semantic version."""
    version = str(value or "").strip()
    if not is_valid_semver(version) or "+" in version:
        raise ValueError(f"invalid release version for tag: {value!r}")
    return f"{RELEASE_TAG_PREFIX}{version}"


def is_valid_release_tag(value: str) -> bool:
    tag = str(value or "").strip()
    if not tag.startswith(RELEASE_TAG_PREFIX):
        return False
    version = tag[len(RELEASE_TAG_PREFIX) :]
    return bool(version) and "+" not in version and is_valid_semver(version)


def source_release_archive_name(value: str = VERSION) -> str:
    """Return the recommended source-only release archive name."""
    return f"{SOURCE_RELEASE_ARCHIVE_PREFIX}-{release_tag(value)}.tar.gz"


VERSION_INFO = version_info(VERSION)

__all__ = [
    "RELEASE_TAG_PREFIX",
    "SOURCE_RELEASE_ARCHIVE_PREFIX",
    "VERSION",
    "VERSION_INFO",
    "__version__",
    "is_valid_release_tag",
    "is_valid_semver",
    "release_tag",
    "source_release_archive_name",
    "version_info",
]
