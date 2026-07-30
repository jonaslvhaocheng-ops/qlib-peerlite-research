# M8 Expected-Red Evidence

The original M8 runner exposed the intended defect during real execution:
durable local starts existed while the authoritative ledger remained at 8/61.
The run was stopped before further fits.

The permanent regression oracle is the recovery parser's tamper test:
changing the third counted fold from `wf_2020` to `wf_2021` must raise
`legacy M8 fit identity mismatch`. A legacy implementation that merely copied
count flags without validating semantic identities would accept this input and
fail the required test.

The incident journal and frozen pre-reconciliation ledger hash are retained as
the historical red evidence. No training or final-OOS access is needed to
reproduce the test oracle.
