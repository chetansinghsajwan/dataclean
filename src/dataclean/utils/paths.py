from collections.abc import Iterable

from dataclean.types import checked


@checked
def map_path(path: str, to: str, sep: str) -> str:
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


def map_paths(paths: Iterable[str], to: str) -> list[str]:
    if "/" in to:
        sep = "/"
    elif "." in to:
        sep = "."
    else:
        return [to for _ in paths]

    return [map_path(path, to, sep) for path in paths]
