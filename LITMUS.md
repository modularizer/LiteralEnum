1. **Namespace** for member access, e.g. `FieldType.A`
    - ```python
      x = HttpMethod.GET  # automatically seen as having type of Literal["GET"] and value of "GET"
      ```
    - `Literal` fails this, and I see it as `Literal`'s biggest weakness
2. **Raw literals accepted**: `"A"` should be an acceptable input to a param typed as `t: FieldType`
    - ```python
      def handle(method: HttpMethod) -> None: ...
      handle("GET") # this should be considered OK, as though HttpMethod was synonymous with Literal["GET", "POST"]
      ```
    - `Enum/StrEnum` fail this and I see it as their biggest weakness for SOME use cases
    - NOTE: there are definitely times devs WANT to reject raw strings to avoid floating literals : I would not want to change `Enum/StrEnum` behavior here
3. **Named members accepted**: `FieldType.A` should be an acceptable input to a param typed as `t: FieldType`
    - ```python
      def handle(method: HttpMethod) -> None: ...
      handle(HttpMethod.GET) # this should be considered OK, because HttpMethod.GET is JUST a raw string literal exactly "GET", and HttpMethod is synonymous with Literal["GET", "POST"]
      ```
    - comparing an `Enum` member against a `Literal` type hint currently fails, and I think this is one thing @Randolf Sholz was trying to address with his PEP 586 amendment
4. **Iteration and containment**: `x in FieldType` and `for x in FieldType` should be first-class
    - ```python
      assert "GET" in HttpMethod   # True because HttpMethod acts as an iterable of the unique values, in first-seen order
      assert HttpMethod.GET in HttpMethod   # True because HttpMethod acts as an iterable of the unique values, in first-seen order
      ```
    - both `Literal` and `Enum` provide ways to do this, but it could be more natural (and as @beauxq suggested, even `Literal` could benefit from `in` support)
5. **Single source of truth**: if I have to write `"A"` more than once when defining my type, it fails this test
    - ```python
      class HttpMethod(LiteralEnum):
          GET = "GET"
          POST = "POST"
      ```
    - user experience and readability matters
    - single source of truth == easier to refactor/extend/edit == less error prone
6. **One type, not two**: most current solutions require separate variables for different parts of the functionality, which I find error-prone
    - ```python
      def handle(method: HttpMethod) -> None:
          assert method in HttpMethod
          if method == HttpMethod.GET:
            return
      ```
    - user experience and readability matters
    - minimizing number of imports improves user eperience
    - if there is one type for typehinting, another for iteration/validation, and a third for namespace, it is very easy to get confused and use the wrong one
7. **Serializable**: values should pass `json.`


Here's how the current approaches score:

| Approach                               | #1 Namespace | #2 Raw lit | #3 Member | #4 Iterate | #5 Single source | #6 One type that does it all |
|----------------------------------------|--------------|------------|-----------|------------|------------------|------------------------------|
| `Literal` alone                        | ❌            | ✅          | ❌         | ❌          | ✅                | ❌                            |
| `Literal` + `get_args` (@peter)        | ❌            | ✅          | ❌         | ✅          | ✅                | ❌                           |
| `StrEnum`                              | ✅            | ❌          | ✅         | ✅          | ✅                | ❌                            |
| `StrEnum` + PEP 586 amend (@Randolf)   | ✅            | ❌          | ✅         | ✅          | ✅                | ❌                            |
| `Enum` + `ParamOf` (@Tinche)           | ✅            | ✅          | ✅         | ✅          | ✅                | ❌                            |
| `Final` class + `Literal` alias (@tmk) | ✅            | ⚠️         | ✅         | ⚠️         | ❌                | ❌                           |
| Runtime `in` on `Literal` (@beauxq)    | ❌            | ✅          | ❌         | ⚠️         | ✅                | ❌                            |
| **LiteralEnum (proposed)**             | ✅            | ✅          | ✅         | ✅          | ✅                | ✅                            |

