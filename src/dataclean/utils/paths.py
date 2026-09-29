"""Helpers for mapping input paths to output paths via wildcard templates."""

from collections.abc import Iterable

from dataclean.types import checked


@checked
def map_path(path: str, to: str, sep: str) -> str:
    """Map a single path onto a wildcard output template.

    ``to`` is a template split into segments by ``sep``, where each ``*``
    is filled in from the corresponding segment of ``path`` (aligned
    left-to-right for all but the last template segment). If ``to``
    contains no ``*``, it is returned unchanged (a fixed/literal target).
    Otherwise:

    - Every template segment before the last is left-aligned against
      ``path``'s segments one-for-one; a ``*`` in that segment is replaced
      by the matching path segment (or ``""`` if ``path`` is shorter).
    - The last template segment anchors to ``path``'s last segment: any
      leftover path segments between the consumed prefix and the last one
      pass through unchanged, and a bare ``*`` as the entire last segment
      consumes and joins all remaining path segments; a ``*`` within the
      last segment is otherwise replaced by ``path``'s last segment.

    Args:
        path: The input path being mapped.
        to: The output template, using ``*`` as a wildcard placeholder.
        sep: The path segment separator (e.g. ``"/"`` or ``"."``).

    Returns:
        The output path with wildcards filled in from ``path``.
    """
    if "*" not in to:
        return to

    path_parts = path.split(sep)
    map_parts = to.split(sep)

    prefix, last = map_parts[:-1], map_parts[-1]
    result = []

    # prefix: left-aligned, one path segment per prefix segment
    for i, part in enumerate(prefix):
        if "*" in part:
            value = path_parts[i] if i < len(path_parts) else ""
            result.append(part.replace("*", value))
        else:
            result.append(part)

    consumed = len(prefix)

    if last == "*":
        # pure wildcard -> consume everything remaining
        remaining = path_parts[consumed:]
        result.append(sep.join(remaining))
    else:
        # last segment anchors to path's LAST segment; anything in between passes through
        leftover_end = len(path_parts) - 1
        if leftover_end > consumed:
            result.extend(path_parts[consumed:leftover_end])
        if "*" in last:
            value = path_parts[-1] if path_parts else ""
            result.append(last.replace("*", value))
        else:
            result.append(last)

    return sep.join(result)


def map_paths(paths: Iterable[str], to: str) -> dict[str, str]:
    """Map each of ``paths`` onto the ``to`` wildcard template via :func:`map_path`.

    Infers the path separator from ``to`` (``"/"`` if present, else
    ``"."``); if ``to`` contains neither, every path is mapped to ``to``
    literally (no wildcard expansion is possible without a separator).

    Args:
        paths: Input paths to map.
        to: The output template, using ``*`` as a wildcard placeholder.

    Returns:
        Mapping of each input path to its mapped output path.
    """
    if "/" in to:
        sep = "/"
    elif "." in to:
        sep = "."
    else:
        return dict.fromkeys(paths, to)

    return {path: map_path(path, to, sep) for path in paths}
