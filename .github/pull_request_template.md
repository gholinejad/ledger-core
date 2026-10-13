## What and why

<!-- One concern. What changes, and why it is needed. -->

## Evidence

<!-- Commands run and their result, e.g. test counts, changed replay figures. -->

## Definition of done (CONTRIBUTING.md §3)

- [ ] `python3 -m unittest tests.test_ledger` passes
- [ ] `tests/test_known_failure.py` still fails, for its documented reason
- [ ] Behaviour change has a test that fails before and passes after
- [ ] NUMBERS.md updated if any printed figure changed
- [ ] README / NUMBERS / AMBIGUITIES / REJECTED / architecture still true
- [ ] One new WORKLOG entry; no earlier entry edited
- [ ] architecture.pdf regenerated if the HTML changed (2–4 pages)

Merge needs `tests` and `agent-review` green on the head commit. The author never sets `agent-review`.
