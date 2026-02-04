from typing import Literal

HttpMethod = Literal["GET", "POST"]


def handle(method: HttpMethod) -> None:
    print(f"{method=}")

if __name__ == "__main__":
    # CONS
    handle("GET") # warning => ❌ bad
    HttpMethod.GET # does not exist
    HttpMethod.__args__ # feels a bit gross to access
