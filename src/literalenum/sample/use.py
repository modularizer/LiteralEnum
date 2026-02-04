# Values are true strings
from sample.http import HttpMethod

assert isinstance(HttpMethod.GET, str)
assert HttpMethod.GET == "GET"
assert type(HttpMethod.GET) is str

# isinstance works for membership
assert isinstance("GET", HttpMethod)
assert isinstance(HttpMethod.GET, HttpMethod)
assert not isinstance("git", HttpMethod)

# Iterable + dict-able
options: list[HttpMethod] = list(HttpMethod)
options_by_name: dict[str, HttpMethod] = HttpMethod.mapping

# Constructor / validator
assert HttpMethod("GET") == "GET"

# HttpMethod is treated as Literal["GET", "POST", "DELETE"]
def handle(method: HttpMethod) -> None:
    pass

handle("GET")            # OK
handle(HttpMethod.GET)   # OK
handle("git")            # type error
# handle(HttpMethod.git)   # type error + AttributeError