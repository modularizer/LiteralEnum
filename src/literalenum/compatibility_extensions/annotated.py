from typing import Any


def annotated(cls, *metadata: Any):
    from typing import Annotated
    return Annotated[cls.runtime_literal, *metadata]