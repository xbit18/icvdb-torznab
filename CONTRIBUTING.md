# Contributing to Violarr

Thank you for helping improve Violarr. This guide covers the local setup, repository workflow, and checks used before submitting a change.

## Getting started

You need Git, Node.js with npm, and Python 3. Python 3.12 is recommended to match CI; the setup scripts use the available Python 3 installation. No single Node.js version is shared across the frontend and documentation CI jobs.

Clone the repository and run the setup script from its root:

```bash
git clone https://github.com/xbit18/violarr.git
cd violarr
bash setup.sh       # macOS and Linux
```

On Windows, run `setup.bat` from the repository root.

Both scripts install the root, frontend, and documentation npm dependencies, create a `.venv` virtual environment, install `requirements.txt` and `requirements-dev.txt`, and configure Git to use `.githooks/`. The scripts do not activate the virtual environment; activate it before running Python checks if needed (`source .venv/bin/activate` on macOS/Linux or `.\.venv\Scripts\Activate.ps1` in PowerShell).

## Development workflow

`develop` is the integration branch. `main` is the stable release branch. Start new `feat/*`, `fix/*`, or `chore/*` branches from the latest `develop` branch:

```bash
git switch --track origin/develop  # once, for a fresh clone
git switch -c feat/short-description
```

For later work, update your local `develop` before creating a branch. By repository convention, feature and fix pull requests target `develop`; prefer **Squash and merge** for those pull requests. Changes move from `develop` to `main` through the established release flow, using a merge commit, then `main` is synced back into `develop`. These branch and merge choices are conventions, not CI-enforced rules.

## Code quality

Run checks from the repository root. Activate the Python virtual environment first if it is not already active.

Backend:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Frontend:

```bash
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
```

Documentation:

```bash
npm --prefix docs run format:check
npm --prefix docs run docs:build
```

## Commit conventions

Use Conventional Commits. Examples:

```text
feat: add result ranking preset
fix: handle empty search queries
docs: clarify local development setup
chore: update development tooling
refactor: simplify settings normalization
```

The setup scripts configure the repository's Git hooks. The pre-commit hook runs the relevant Ruff, ESLint, and Prettier checks and fixes for staged files, then re-stages formatted files. The commit-msg hook validates messages with Commitlint and the Conventional Commits configuration.

## Pull requests

Open focused pull requests against `develop`. Explain the motivation and user-visible impact, link related issues, and list the checks you ran. Keep unrelated changes out of the pull request; include screenshots for UI changes when they help reviewers. Follow the release flow for changes moving from `develop` to `main`.

## Reporting issues

Before opening an [issue](https://github.com/xbit18/violarr/issues), search existing issues to see whether it has already been reported. Include clear reproduction steps, expected and actual behavior, and relevant logs with secrets removed.
