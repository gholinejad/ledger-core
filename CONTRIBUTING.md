# Contributing

These rules apply to every change, whether a person or an agent makes it. GitHub enforces the ones it can; review enforces the rest.

## 1. How a change reaches `main`

- `main` is protected. **No direct commits and no force pushes.** This applies to admins too (`enforce_admins` is on).
- Every change starts on a short-lived branch and reaches `main` through a pull request. Name the branch after the change: `feat/…`, `fix/…`, `docs/…`, `test/…` or `chore/…`.
- A PR covers **one concern**. If the description needs the word "and", it is probably two PRs.
- Two checks must pass on the PR's head commit:
  - `tests`: CI (`.github/workflows/ci.yml`).
  - `agent-review`: one independent agent review (§4).

  The branch must also be up to date with `main` (strict mode). A new push needs both checks again.
- Merge with **merge commits only**. Squash and rebase merges are disabled, because the brief requires an intact commit history. The branch is deleted after the merge.
- All PR conversations must be resolved before merging.

## 2. Commits

- Subject in the imperative mood, at most 72 characters. The body explains *why*, not *what*.
- One logical step per commit, so the history shows how the work was actually built.
- AI-assisted commits carry a `Co-Authored-By:` trailer.

## 3. Definition of done (every PR)

- [ ] `python3 -m unittest tests.test_ledger` passes.
- [ ] `tests/test_known_failure.py` still fails, for the reason written in it.
- [ ] A behaviour change comes with a test that fails before the change and passes after it.
- [ ] If a number in `python3 replay.py` output changes, `NUMBERS.md` is updated to match.
- [ ] Every claim in README, NUMBERS, AMBIGUITIES, REJECTED and the architecture document is still true of the code.
- [ ] A new ambiguity goes in `AMBIGUITIES.md`. A dropped approach goes in `REJECTED.md`.
- [ ] `WORKLOG.md` gets one new timestamped entry for the PR.
  - The worklog is append-only.
  - Earlier entries are never edited. A correction is a new entry that says what was wrong.
- [ ] If `docs/architecture.html` changed, `docs/architecture.pdf` is regenerated, and it is still 2–4 pages.

## 4. Review protocol: one unbiased agent review per PR

- Each PR head commit gets **exactly one** review from an agent that **did not write the change**. The reviewer starts with a fresh context and sees only:
  - the repository at the PR head;
  - the PR description;
  - this file.

  It never sees the author's conversation, reasoning or notes.
- The reviewer follows `.claude/skills/agent-pr-review/SKILL.md`:
  1. Run the checks.
  2. Read the diff against §3 and §5.
  3. Post its findings as a PR review comment.
  4. Set the `agent-review` commit status on the head SHA to `success` (no blocking findings) or `failure`.
- **The author never sets `agent-review`.** GitHub does not let an account approve its own PR, so the agent's approval is recorded as a required status check. GitHub enforces that a successful `agent-review` status exists on the head commit. It cannot enforce who set it, because the reviewer posts with the same account, so that part is a rule of this repository. The `tests` check, by contrast, is pinned to GitHub Actions, so it cannot be set by hand.
- A push after the review produces a new head SHA, which carries no `agent-review` status, so the PR needs a new review. To disagree with a finding, reply in the PR and request a new review. Never override the reviewer.

## 5. Ledger invariants no PR may break

- Money is integer minor units. A rate is applied, and rounded, in exactly one place: `apply_rate`. `split_evenly` divides exactly and gives the remainder to the last part.
- Append-only:
  - No entry, accrual, authorization transition or notice is ever changed or removed.
  - A correction is a new compensating record.
- Restatement is idempotent: running the close logic again over the same knowledge posts nothing.
- The rounded daily accruals sum exactly to the capitalised interest.
- Standard library only. No dependency without a written reason in `REJECTED.md`.

## 6. Secrets

No token, key or password goes in the repository, a commit message, a PR or CI logs. Local GitHub access resolves a token by name from the macOS keychain, never as a literal value.
