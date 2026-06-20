from abc import ABC
from typing import Any

from pydantic import BaseModel, ConfigDict, validate_call


class StrictBaseModel(BaseModel, ABC):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=False,
        arbitrary_types_allowed=True,
    )

    def __init_subclass__(cls, frozen: bool = False, **kwargs: Any) -> None:
        """
        Intercepts subclass creation and dynamically mutates its model_config.
        """
        super().__init_subclass__(**kwargs)

        cls.model_config = ConfigDict(
            strict=True,
            extra="forbid",
            frozen=frozen,
            arbitrary_types_allowed=True,
        )


# Create a reusable strict validation decorator shortcut
strict_validate = validate_call(
    config=ConfigDict(
        strict=True,
        arbitrary_types_allowed=True,
    )
)
