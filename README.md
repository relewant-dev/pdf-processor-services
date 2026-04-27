# smart-ide-services

[![Build](https://img.shields.io/github/actions/workflow/status/OWNER/REPO/ci.yaml?branch=main&label=build)](https://github.com/OWNER/REPO/actions/workflows/ci.yaml)
[![Version](https://img.shields.io/github/v/release/OWNER/REPO?sort=semver)](https://github.com/OWNER/REPO/releases)
[![License](https://img.shields.io/github/license/OWNER/REPO)](./LICENSE)

> Replace `OWNER/REPO` in the badge URLs above with your GitHub repository slug (for example, `acme/smart-ide-services`).

Backend for Smart IDE App.

This project uses a GitHub Actions release pipeline (`.github/workflows/ci.yaml`) with Conventional Commit linting and semantic-release to automate tagging and release notes on pushes to `main`.

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
