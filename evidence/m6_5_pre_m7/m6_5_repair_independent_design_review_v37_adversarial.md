# M6.5 v37 adversarial R3 design review

- Reviewer: `/root/m65_v24_adversarial_review`
- Subject: `sha256:ab3d455f308d108b86a9ced8dd6b4db27eba354d6ace94d5d438e2126ff74bb5`
- Verdict: `NEEDS_CHANGES`
- Severity: `P0=0 / P1=6 / P2=4 / P3=0`
- M7 v15: `NEEDS_CHANGES / NOT_AUTHORIZED`

Findings: capacity must be one-device or per-device with all target roots scanned; bootstrap needs
one activation marker; execution needs a fixed exclusive event lease; issuer trust policy SHA must
come from parent governance outside the request; process spawn/dynamic code must be denied and
runtime I/O attested; historical clocks must be field-specific and include snapshot time; hardlink
blocks must dedupe inode and logical paths need unique staging inodes; new receipts/issuer/evidence
objects need full schemas; claim-before-START cancel must be removed or represented.

Confirmed: bijection, block formula framework, chmod durability, three-phase final inventory,
sibling completion, ledger head recurrence, STARTED-before-fit, result wrapper direction, event-key
collision prevention, permanent budget, registry hash DAG, field registry, replay preimages and
pointer composition. Review was read-only and executed nothing.
