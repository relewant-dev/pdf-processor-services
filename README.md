# smart-ide-services

Backend for Smart IDE App

## Git commit hook (Conventional Commits)

This repository includes a `commit-msg` hook that validates commit messages against the Conventional Commits format.

### Enable the hook

Run this once after cloning:

```bash
git config core.hooksPath .githooks
```

### Accepted format

```text
<type>[optional scope][!]: <description>
```

Examples:

- `feat(auth): add OAuth callback handler`
- `fix: handle null API response`
- `refactor!: remove legacy settings endpoint`

Allowed types:

- `feat`
- `fix`
- `docs`
- `style`
- `refactor`
- `perf`
- `test`
- `build`
- `ci`
- `chore`
- `revert`
