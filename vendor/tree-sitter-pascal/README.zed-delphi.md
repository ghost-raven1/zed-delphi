# Vendored Pascal grammar

Source: https://github.com/Isopod/tree-sitter-pascal

Pinned upstream commit: `042119eca2e18a60e56317fb06ee3ba5c32cb447` (crate version 0.10.2).
License: MIT, retained in `LICENSE`.

Local patches in `grammar.js`:

- Accept Delphi `uses UnitName in 'UnitName.pas'` clauses without changing the existing unit-name AST.
- Parse Delphi packages with `package`, optional `requires` and `contains` sections, and `end.`.

The Rust binding and build script are from upstream. Generated C parser, grammar JSON and node types are checked in so normal builds need no Node.js or parser-generation downloads.

Regenerate from this directory:

```sh
npm exec --yes --package=tree-sitter-cli@0.24.7 -- tree-sitter generate
npm exec --yes --package=tree-sitter-cli@0.24.7 -- tree-sitter test
```

The upstream corpus is retained in `test/corpus`; Delphi project/package fixtures and query capture regressions are in `../../crates/grammars/tests` and run with:

```sh
cargo test -p grammars --features load-grammars --test delphi
```
