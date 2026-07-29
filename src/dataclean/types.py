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

    def __init_subclass__(cls, frozen: bool | None = None, **kwargs: Any) -> None:
        """
        Intercepts subclass creation and merges frozen state into model_config.
        Inherits parent's frozen value if not explicitly overridden.
        """
        super().__init_subclass__(**kwargs)

        if frozen is None:
            # Inherit whatever the nearest parent already resolved to
            frozen = cls.model_config.get("frozen", False)

        # Merge instead of overwrite, so subclass-defined model_config keys survive
        cls.model_config = {
            **cls.model_config,
            "strict": True,
            "extra": "forbid",
            "frozen": frozen,
            "arbitrary_types_allowed": True,
        }


# Create a reusable strict validation decorator shortcut
strict_validate = validate_call(
    config=ConfigDict(
        strict=True,
        arbitrary_types_allowed=True,
    )
)
