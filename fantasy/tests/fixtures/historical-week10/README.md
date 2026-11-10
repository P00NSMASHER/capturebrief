# Frozen historical engine fixture

These three artifacts are exact copies of `fantasy/data.json`, `fantasy/edge.json`,
and `fantasy/intelligence.json` at commit `2dc063e`.

They form an internally aligned Week 9 Yahoo baseline / Week 10 model evidence
bundle and exist only to keep
deterministic engine tests stable. They are not current publication data and must
never be presented by the dashboard as live or current evidence.

Current publication behavior is tested separately by
`publication-contract.test.mjs`, which reads the three files from `fantasy/`.
