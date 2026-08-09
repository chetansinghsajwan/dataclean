import os

from beartype import beartype

_DEV_MODE = os.environ.get("APP_ENV", "prod") == "dev"


def checked(func):
    """Always applies beartype runtime type checking."""
    return beartype(func)


def dev_checked(func):
    """Applies beartype only when APP_ENV=dev; no-op otherwise (zero overhead in prod)."""
    return beartype(func) if _DEV_MODE else func
