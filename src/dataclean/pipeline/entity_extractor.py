"""Entity extraction for disambiguating column roles."""

from collections.abc import Callable
from dataclasses import dataclass

from dataclean.types import checked


@checked
@dataclass(kw_only=True)
class EntityExtractor:
    """
    Extracts entity tokens from column names to disambiguate between
    multiple producer candidates (e.g., client_phone vs manager_phone).
    """

    WordFn = Callable[[str], tuple[str, ...]]

    words_fn: WordFn

    def extract(self, column: str, role: str) -> tuple[str, ...]:
        """
        Extract entity tokens from a column name by removing role tokens.

        Args:
            column: The column name to analyze (e.g., "client_phone").
            role: The semantic role (e.g., "phone").

        Returns:
            Tuple of entity tokens (e.g., ("client",)).
        """

        role_tokens = set(self.words_fn(role))
        return tuple(
            word for word in self.words_fn(column) if word.lower() not in role_tokens
        )

    def overlap(
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
