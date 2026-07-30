# M8 Architecture Confirmation

M8 does not add a new model family, feature source, portfolio rule, data
boundary, or production surface. It closes one interrupted confirmation run
inside the existing governance architecture:

```text
retained v1 journal
  -> narrow canonicalization
  -> atomic authoritative-ledger reconciliation
  -> independent retained-failure verification
  -> HOLD gate and decision package
```

The recovery policy remains in `qlib_peerlite.governance`; server scripts are
composition roots. The authoritative append-only ledger and final-OOS access
log remain the two external state boundaries. Model training is not resumed.

Risk is R3 because the change governs model decisions and research trial
accounting. The narrow recovery module is appropriate: it accepts only the
exact observed incident shape and cannot authorize a new experiment.
