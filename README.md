# Smart IDE App

[![Build](https://img.shields.io/github/actions/workflow/status/relewant-dev/smart-ide-services/ci.yaml?branch=main&label=build)](https://github.com/relewant-dev/smart-ide-services/actions/workflows/ci.yaml)
[![Version](https://img.shields.io/github/v/release/relewant-dev/smart-ide-services?sort=semver)](https://github.com/relewant-dev/smart-ide-services/releases)
[![License](https://img.shields.io/github/license/relewant-dev/smart-ide-services)](./LICENSE)

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
