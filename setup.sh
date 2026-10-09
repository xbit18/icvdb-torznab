
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== Checking prerequisites ==="
command -v npm >/dev/null || { echo "npm not found"; exit 1; }
command -v python3 >/dev/null || { echo "Python 3 not found"; exit 1; }

echo "=== Installing root dependencies ==="
npm ci --include=dev

echo "=== Installing frontend dependencies ==="
(cd frontend && npm ci --include=dev)

echo "=== Installing docs dependencies ==="
(cd docs && npm ci --include=dev)

echo "=== Setting up Python ==="
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt

echo "=== Configuring Git hooks ==="
git config --local core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/commit-msg

echo "=== Setup completed successfully! ==="
