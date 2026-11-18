"""Column helpers shared by the model modules."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum


def enum_column(enum_cls: type[Enum], length: int = 64) -> SAEnum:
    """String-backed enum column storing the *value* of each member.

    Native PostgreSQL enums are avoided so migrations stay simple and reversible;
    a CHECK constraint is generated instead.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
        name=f"{enum_cls.__name__.lower()}_enum",
    )
