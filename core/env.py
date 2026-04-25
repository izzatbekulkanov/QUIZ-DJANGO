import os
from pathlib import Path


TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return default if value is None else value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False

    raise ValueError(f"{name} must be one of: {', '.join(sorted(TRUE_VALUES | FALSE_VALUES))}")


def env_int(name: str, default: int = 0) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)

    if value is None:
        return list(default or [])

    return [item.strip() for item in value.split(",") if item.strip()]
