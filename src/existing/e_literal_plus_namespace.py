from typing import Literal

HttpMethodType = Literal["GET", "POST"]

class HttpMethod:
    GET: HttpMethodType = "GET"
    POST: HttpMethodType = "POST"


def handle(method: HttpMethodType) -> None:
    print(f"{method=}")

if __name__ == "__main__":
    pass
    # CONS
    # no single source of truth
    # verbose to write