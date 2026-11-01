## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default five triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Git workflow

このリポジトリは project-workflow に従う（`main` ＋ `feature/<作業名>` を no-ff マージ、日本語の Conventional Commits）。clone し直したら次を流す。

```bash
git config core.hooksPath .githooks
git config branch.main.mergeoptions --no-ff
git config pull.ff only
```

`.scratch/`（wayfinder の地図とチケット、調べた結果）は作業メモなので git に入れない。
