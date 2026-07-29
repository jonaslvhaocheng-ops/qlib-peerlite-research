# M6.5 external CI gate — green-test evidence

The router-controlled green run covers:

1. the complete repository test suite;
2. Ruff across self-authored source, tests and scripts;
3. Ruff for the read-only CI evidence verifier;
4. the GitHub Actions workflow's required trigger, job and gate commands.

`scripts/vendor/` is a frozen third-party PIT-audit snapshot.  It is excluded
only from project-style Ruff; repository source binding, evidence hashes and
the full test suite continue to cover it.

Expected result: all commands exit `0`, with the source digest unchanged.

