def sqlalchemy_enum(cls):
    try:
        from sqlalchemy import Enum
    except ImportError as e:
        raise RuntimeError("Install sqlalchemy to use .sqlalchemy_enum") from e
    return Enum(*cls._ordered_values_, name=cls.__name__)