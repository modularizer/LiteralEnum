### Why basedpyright is the best base

* It’s a Pyright fork that explicitly aims to re-implement Pylance-exclusive UX like **semantic highlighting**. ([PyPI][1])
* It already has “Pylance-like” features baked in, so you’re not starting from scratch.

Also, the official Pyright extension disables itself if Pylance is installed. ([Visual Studio Marketplace][2]) (basedpyright similarly avoids conflicts / can disable pylance). ([docs.basedpyright.com][3])

---

## Plan: ship a “Pylance-like” VS Code experience + your 0.1% LiteralEnum logic

### Phase 0 — Decide the distribution strategy

You have two realistic choices:

**A) Fork basedpyright and ship your own VS Code extension** (best for your goal)
Users install **your extension instead of Pylance** → they still get a rich Pyright-style LS + semantic highlighting + your LiteralEnum edge-case.

**B) Contribute upstream to basedpyright**
Best for adoption, but slower + you’ll need to make the feature general/acceptable.

(Using stock Pylance and “stacking” is not really feasible for *type engine* changes.)

---

## Phase 1 — Implement LiteralEnum in the type engine (small, surgical)

You want to touch as few places as possible.

What you need Pyright/basedpyright to understand:

1. **Type position rewrite**
   When an annotation references a `LiteralEnum` subclass, treat it as `Literal[...] | Literal[...] | ...` (i.e., an exhaustive literal union).

2. **Assignable rules**
   Allow `Literal["GET"]` (and `"GET"` in some contexts depending on strictness) to be compatible with `HttpMethod` as an annotation.

3. **Member types**
   `HttpMethod.GET` should be `Literal["GET"]`, not `str`.

Where to implement (Pyright architecture terms):

* The annotation evaluation path (where it resolves `Colors` inside `A | B`)
* The assignability checker (expected vs actual)
* Member access type (class attribute type)

This is basically what you already did in JetBrains land, but in Pyright you do it **once** in the core engine and the rest of the editor features fall out “for free”.

**Design tip:** gate everything behind a cheap check:

* “Is this class a subclass of `literalenum.LiteralEnum` (plus your FQNs)?”
* if not, bail immediately

So performance impact stays tiny.

---

## Phase 2 — Make VS Code feel “Pylance-like”

Basedpyright already brings semantic highlighting and other Pylance-ish stuff. ([PyPI][1])

What you ship:

* A VS Code extension that runs **your forked basedpyright language server**
* (Optionally) also publish the CLI package so CI can run the same checker

Users do:

* disable/uninstall Pylance
* install your extension

This is necessary because Pylance is not configurable to use a fork, and Pyright-family extensions generally avoid running alongside Pylance. ([Visual Studio Marketplace][2])

---

## Phase 3 — Packaging so users don’t suffer

Goal: “install extension, done”.

* Fork basedpyright
* Add your LiteralEnum changes
* Build/publish:

  * npm package (language server) under your scope/name
  * VS Code extension that bundles/depends on that package
* Release on:

  * VS Code Marketplace (if you want)
  * Open VSX (nice for Cursor/VSCodium users)

basedpyright already ships to multiple channels; mirror that model.

---

## Phase 4 — Compatibility & escape hatches

* Keep your LiteralEnum behavior behind a config flag like:

  * `literalEnum.enable: true`
  * `literalEnum.fqns: [...]`
* If something breaks for a user, they can disable just *your* feature without losing the whole language server.

---

### Reality check

If you want “full Pylance experience” *and* your custom typing, you can’t do it **inside** Pylance. You do it by providing an alternative language server that feels similar — and basedpyright is explicitly aimed at that niche. ([docs.basedpyright.com][4])


[1]: https://pypi.org/project/basedpyright/1.17.5/?utm_source=chatgpt.com "basedpyright"
[2]: https://marketplace.visualstudio.com/items?itemName=ms-pyright.pyright&utm_source=chatgpt.com "Pyright"
[3]: https://docs.basedpyright.com/latest/installation/ides/?utm_source=chatgpt.com "IDEs - basedpyright"
[4]: https://docs.basedpyright.com/v1.37.1/benefits-over-pyright/pylance-features/?utm_source=chatgpt.com "pylance features"
