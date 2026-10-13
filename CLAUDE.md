# ledger-core: rules for agents

Read `CONTRIBUTING.md` before you change anything. In short:

- **Never commit or push to `main`.** Work on a `feat/` `fix/` `docs/` `test/` `chore/` branch and open a PR. `main` is protected, including for admins.
- **One concern per PR.** Merge commits only; never squash or rebase, because the brief requires intact history.
- **Every PR needs a green `tests` check (CI) and one independent `agent-review`.** The reviewer must be a fresh agent that did not write the change. It follows `.claude/skills/agent-pr-review/SKILL.md`. The author never sets the `agent-review` status.
- `WORKLOG.md` is append-only, with real local timestamps (`date +%H:%M`). Corrections go in new entries.
- If a printed number changes, update `NUMBERS.md` in the same PR.
- GitHub access goes through the REST API with the `apollo-github` / `gholinejad` keychain token, resolved by name and never printed. `gh` is not installed.
