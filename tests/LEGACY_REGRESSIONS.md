# Parked legacy regressions

These synthetic checks were promoted from the historical review directory into
`tests/`; the review snapshot, images and transcripts are not included. This
branch is parked, not a PR in the ordered merge series. Failing checks document
legacy bugs that need separate fixes before proposing a PR. EVC snapshot guards
already have dedicated tests on `parked/evc` and are not duplicated here.

Run `MPLBACKEND=Agg python -m pytest tests/test_legacy_regressions.py` in the
scientific environment. Generated plot evidence goes into a test temporary
folder. No Box network connection or real recordings are used.

Validation on current main after the split: 10 controls pass and 9 checks fail
on the existing legacy defects: event-marker truncation (#115), legacy crop
cancel/close (#113), Box retry/recursive error/pagination/completeness, statistics
frequency overrides (#110), and all-drugs summary dispatch (#111). Those fixes
are separate follow-up work. No result here relies on an actual Box transfer.
