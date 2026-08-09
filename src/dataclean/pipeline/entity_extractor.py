"""Entity extraction for disambiguating column roles."""

from collections.abc import Callable


class EntityExtractor:
    """
    Extracts entity tokens from column names to disambiguate between
    multiple producer candidates (e.g., client_phone vs manager_phone).
    """

    def __init__(self, words_fn: Callable[[str], tuple[str, ...]]) -> None:
        """
        Initialize with a word tokenizer function.

        Args:
            words_fn: Function that splits a string into word tokens.
        """
        self._words = words_fn

    def extract(self, column: str, role: str) -> tuple[str, ...]:
        """
        Extract entity tokens from a column name by removing role tokens.

        Args:
            column: The column name to analyze (e.g., "client_phone").
            role: The semantic role (e.g., "phone").

        Returns:
            Tuple of entity tokens (e.g., ("client",)).
        """
        role_tokens = set(self._words(role))
        return tuple(t for t in self._words(column) if t.lower() not in role_tokens)

    def entity_overlap(
        self,
        column_entities: tuple[str, ...],
        producer_column_entities: tuple[str, ...],
    ) -> float:
        """
        Compute entity token overlap between two sets of tokens.

        Args:
            column_entities: Entity tokens from the consumer column.
            producer_column_entities: Entity tokens from a producer column.

        Returns:
            Overlap score (0.0 to 1.0).
        """
        if not column_entities:
            return 1.0 if not producer_column_entities else 0.0

        col_set = {t.lower() for t in column_entities}
        prod_set = {t.lower() for t in producer_column_entities}

        intersection = len(col_set & prod_set)
        union = len(col_set | prod_set)

        return intersection / union if union > 0 else 0.0
