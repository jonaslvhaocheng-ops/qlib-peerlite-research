# M6.5 external CI gate v2 — green-test declaration

The controller must execute all declared commands against source digest
`sha256:6d60dec06440bc120ebf6c0195d91a6aa502229a1348040088f5776992383289`.

Required outcomes:

- complete suite: 86 tests pass;
- M6 archival evidence and replay mechanics: 7 tests pass;
- self-authored project Ruff: pass;
- workflow contract: immutable action/controller pins, canonical pre-merge
  quality command, and clean-runner M6 evidence command are present;
- source digest unchanged before and after every command.

This green gate performs no M7 execution or external write.

