"""Shared type-checking decorators used throughout the dataclean codebase.

Provides the ``checked`` and ``dev_checked`` decorators, both backed by
``beartype``, which validate function arguments, return values, and
dataclass fields against their type hints at runtime.
"""

import os

from beartype import beartype

_DEV_MODE = os.environ.get("APP_ENV", "prod") == "dev"


def checked(func):
    """Wrap a function, method, or class with beartype runtime type checking.

    Applied unconditionally (regardless of the ``APP_ENV`` environment
    variable), so any mismatch between an argument, return value, or
    (for a ``@dataclass``) a field's declared type and its actual value
    raises a ``beartype.roar.BeartypeCallHintViolation`` at call/construction
    time. Used as a decorator across the codebase on public functions,
    dataclasses, and ABCs to enforce their type hints at runtime.

    Args:
        func: The function or class to instrument. When applied to a
            dataclass, decorate it after ``@dataclass`` (i.e. place
            ``@checked`` above ``@dataclass``) so beartype wraps the
            generated ``__init__``.

    Returns:
        The same function or class, wrapped with beartype's runtime checks.
    """
    return beartype(func)


def dev_checked(func):
    """Wrap a function with beartype checking only in development.

    Reads the ``APP_ENV`` environment variable at import time: when it is
    ``"dev"``, behaves exactly like :func:`checked`. Otherwise, returns
    ``func`` unmodified so there is zero runtime-checking overhead in
    production.

    Args:
        func: The function or class to conditionally instrument.

    Returns:
        The beartype-wrapped function/class in dev mode, or the original
        object unchanged otherwise.
    """
    return beartype(func) if _DEV_MODE else func
