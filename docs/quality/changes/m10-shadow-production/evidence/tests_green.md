# Green-test evidence

The controller must independently execute:

- Ruff over `src`, `tests` and `scripts`;
- the complete repository pytest suite;
- the protected `m10-core` coverage profile.

The protected profile enumerates the complete
`src/qlib_peerlite/production` source root and requires exact 100% line and
branch coverage.
