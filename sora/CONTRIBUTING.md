# Contributing

Rules for agents working in this repo. Less, but better.

## Picking up a task

1. Take tasks only from the manager or Assistant Manager.
2. Confirm which files you own before you start.
3. Unclear? Ask one clear question. Don't guess.
4. When you're done, report back. Don't merge your own work.

## Branches

Name branches `<agent>/<topic>`, lowercase, with hyphens:

```
sora/contributing
juniper/fix-login-redirect
```

Branch from `main`. One topic per branch.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.

Keep commits small and focused. Write the description in the imperative ("add", not "added").

## One writer per file

- Only one agent edits a file at a time.
- Touch only the files your task assigns to you.
- Need a file someone else owns? Ask them, don't edit it.
- Hit a merge conflict? Say so right away. Don't force it.

## Stay inside the repo

- Create, edit, and delete files only inside this repository.
- Never work around that limit. If a task needs changes elsewhere, ask the manager.
- Never commit secrets, credentials, or personal data.
