def regex_str(cls) -> str:
    if not all(isinstance(v, str) for v in cls._ordered_values_ if v is not None):
        raise TypeError("regex is only valid for string-valued LiteralEnum")
    import re
    vals = [v for v in cls._ordered_values_ if isinstance(v, str)]
    return "^(?:" + "|".join(re.escape(v) for v in vals) + ")$"

def regex_pattern(cls, flags=0) -> "re.Pattern":
    import re
    return re.compile(cls.regex_str(), flags)