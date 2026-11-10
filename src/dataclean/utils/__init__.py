"""Miscellaneous internal utility helpers (debug logging, path mapping, text case)."""

from .debug import _log_args
from .markup import strip_html
from .null_tokens import COMMON_NULL_TOKENS, is_null_token, null_token_set
from .paths import file_extension, map_path, map_paths
from .patterns import expand_local_paths
from .words import split_words
