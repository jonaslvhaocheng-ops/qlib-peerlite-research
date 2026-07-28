# CSI800 universe source decision

## Decision

`datayes.idx_cons_core` is the selected candidate for membership announcement
and effective intervals:

- CSI300: `SECURITY_ID=1782`, `TICKER_SYMBOL=000300`, `EXCHANGE_CD=XSHG`,
  `ASSET_CLASS=IDX`.
- CSI500: `SECURITY_ID=2103`, `TICKER_SYMBOL=000905`, `EXCHANGE_CD=XSHG`,
  `ASSET_CLASS=IDX`.
- Membership validity is interpreted as `[INTO_EFF_DATE, OUT_EFF_DATE)`.
- Availability is constrained by `INTO_PUB_DATE` and `OUT_PUB_DATE`.

Ticker-only joins are forbidden because the same ticker values also identify
fund/equity records on other exchanges.

## Evidence ceiling

The live verification found zero missing or late inclusion publication dates,
zero missing or late completed-exclusion publication dates, zero duplicate
membership keys, and exact interval agreement with all 3,694 corresponding
`datayes.idx_cons` rows.

This is still a source-clock candidate rather than a PIT pass and does not
qualify a training matrix. Current database comments are not a versioned vendor
dictionary, and `UPDATE_TIME` is a database maintenance field rather than
historical market availability.

## Required before contract freeze

1. Bind the observed field semantics to a versioned DataYes/CSI dictionary.
2. Preserve the exact source extract as an immutable snapshot with hashes.
3. Demonstrate that membership known at each prediction time is reconstructed
   without using later revisions.
