from typing import Literal, Callable

HttpMethod = Literal["GET", "POST"]

HttpMethod.GET: Literal["GET"] = "GET"
HttpMethod.POST: Literal["POST"] = "POST"
HttpMethod.__new__: Callable[[HttpMethod], HttpMethod]

def handle(method: HttpMethod) -> None:
    print(f"{method=}")

if __name__ == "__main__":
    # works well for type checking, but gross
   handle("GET")
   handle(HttpMethod.GET)
   handle(HttpMethod.POST)
   x = HttpMethod("GET")
   handle(HttpMethod("GET"))
   handle("git")