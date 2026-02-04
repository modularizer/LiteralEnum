def bare_class(cls):
    return type(cls.__name__, (), dict(cls._members_))