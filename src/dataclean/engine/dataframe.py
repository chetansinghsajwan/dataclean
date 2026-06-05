from abc import ABC, abstractmethod


class DataFrame(ABC):
    @abstractmethod
    def columns() -> list[str]:
        pass

    @abstractmethod
    def rename_cols(self, rename_map: dict[str, str]) -> None:
        pass

    @abstractmethod
    def read_columns(self, columns: dict[str, any]) -> None:
        pass

    @abstractmethod
    def add_columns(self, columns: dict[str, any]) -> None:
        pass

    @abstractmethod
    def remove_columns(self, columns: list[str]) -> None:
        pass
