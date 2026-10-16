# Parked EVC implementation

This branch preserves EVC from the #122 reference branch, including the local
recovery fixes. It is not part of the merged PR series. The GUI and analysis
CLI still use CSVs; ADR 0002 describes that current behavior.

Do not propose merging EVC until an application consumer is implemented and
its integration tests pass (issue #129). Core object/store/repository/bridge
and API tests are retained here. The hook and analysis-CLI integration tests
also remain as requirements for future adoption; those frontend changes have
not been imported into main or this branch.
