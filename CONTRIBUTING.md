# Contributing to Trade Republic PAC

Thank you for considering contributing to Trade Republic PAC! This guide will help you get started.

If you find a bug or have a feature idea, please [open an issue](https://github.com/enea-scaccabarozzi/trade-republic-pac/issues) first to discuss it.

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:

   ```bash
   git clone git@github.com:<your-user>/trade-republic-pac.git
   cd trade-republic-pac
   ```

3. **Create a branch** for your change:

   ```bash
   git checkout -b feat/short-desc
   ```

   Branch naming convention: `feat/short-desc`, `fix/short-desc`, `docs/short-desc`.

## Development Setup

### Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- [just](https://github.com/casey/just) — command runner

### Setup

```bash
uv sync                 # install dependencies
cp .env.example .env    # configure environment variables
just validate           # confirm everything works
```

### Using a Dev Container

Alternatively, open this repository in VS Code with the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension or in [GitHub Codespaces](https://github.com/features/codespaces) — the dev container handles all tooling setup automatically.

## Git Hooks

This project uses [pre-commit](https://pre-commit.com/) to run checks automatically before commits and pushes.

### Setup

```bash
just hooks-install
```

### What the hooks do

| Hook Stage   | Check                 | Command          |
| ------------ | --------------------- | ---------------- |
| `pre-commit` | Auto-format code      | `just format`    |
| `pre-commit` | Lint                  | `just lint`      |
| `pre-commit` | Type check            | `just typecheck` |
| `commit-msg` | Conventional commit   | `commitizen`     |
| `pre-push`   | Full validation suite | `just validate`  |

### Skipping hooks

If you need to bypass hooks temporarily (e.g., WIP commit):

```bash
git commit --no-verify -m "wip: work in progress"
git push --no-verify
```

Use sparingly — CI will still enforce all checks.

> **Note:** If the format hook auto-fixes files, your commit will be rejected. Stage the fixes with `git add -u` and commit again.

## Code Style

This project enforces consistent style through automated tooling.

| Tool   | Purpose           | Command             |
| ------ | ----------------- | ------------------- |
| `ruff` | Formatting        | `just format`       |
| `ruff` | Format check (CI) | `just format-check` |
| `ruff` | Linting           | `just lint`         |
| `mypy` | Type checking     | `just typecheck`    |

- Line length: **88** characters
- All code must pass `just validate` (runs lint + typecheck + test).
- **Run `just format` before committing** to auto-fix formatting issues.

## Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/) to drive semantic versioning and changelog generation.

### Format

```
type(scope): description
```

Scope is optional but encouraged.

### Types

| Type       | Purpose                          | Changelog  |
| ---------- | -------------------------------- | ---------- |
| `feat`     | New feature                      | Minor bump |
| `fix`      | Bug fix                          | Patch bump |
| `docs`     | Documentation only               | _Excluded_ |
| `chore`    | Maintenance / tooling            | _Excluded_ |
| `ci`       | CI/CD changes                    | _Excluded_ |
| `style`    | Code style (no logic change)     | _Excluded_ |
| `refactor` | Code change (no new feature/fix) | Included   |
| `test`     | Adding or updating tests         | Included   |
| `perf`     | Performance improvement          | Included   |

A `BREAKING CHANGE` footer triggers a **major** version bump.

### Examples

Good:

```
feat(signals): add RSI signal rule
fix(tr): handle expired session token
docs: update development setup instructions
```

Bad:

```
updated stuff          # no type, vague description
feat: Fix bug          # wrong type for a bug fix
```

## Extending the System

### Adding a Signal Rule

1. Run: `just new-rule my_rule_name`
2. Edit `src/pac/rules/builtin/my_rule_name.py` — add params fields, implement `evaluate()`
3. Edit the template at `src/pac/templates/builtin/my_rule_name.j2`
4. Add a signal entry to `pac.yaml`:
   ```yaml
   signals:
     - name: my_signal
       rule: my_rule_name
       schedule: "0 * * * *"
       channels: [telegram]
       params: {}
       template: my_rule_name
   ```
5. Run: `just validate` — ensure lint + typecheck + tests pass
6. Run: `just validate-config` — ensure pac.yaml references are valid

### Adding a Delivery Channel

1. Run: `just new-channel my_channel`
2. Edit `src/pac/delivery/channels/my_channel/channel.py` — add config fields, implement `send()`
3. Add channel config to `pac.yaml`:
   ```yaml
   channels:
     my_channel:
       type: my_channel
       # your config fields
   ```
4. If your channel needs a custom format:
   - Create a `FormatAdapter` subclass in `src/pac/templates/adapters/`
   - Set `supported_formats` to return your adapter's name
5. Run: `just validate` then `just validate-config`

### Validating Configuration

```bash
just validate-config                       # validate pac.yaml
just validate-config --config custom.yaml  # validate a specific file
```

## Testing

- Write tests for all new behavior. Tests live in `tests/`.
- Run the test suite:

  ```bash
  just test                      # all tests
  just test -k test_deviation    # single test by name
  ```

- Full validation (lint + typecheck + test):

  ```bash
  just validate
  ```

## Pull Request Guidelines

- Fill out the PR template when opening a pull request.
- **PR title must follow conventional commit format** (e.g., `feat(signals): add RSI rule`).
- Keep PRs small and focused — one concern per PR.
- Link related issues with `Closes #N` or `Refs #N`.
- All CI checks must pass before merging.

## Reporting Issues

- **Search existing issues** before opening a new one.
- Use the **Bug Report** or **Feature Request** templates.
- Be specific: include reproduction steps, environment details, and expected vs actual behavior.
