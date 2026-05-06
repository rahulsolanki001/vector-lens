# Release Checklist

Use this checklist before tagging a release.

1. Update `CHANGELOG.md` and replace `Unreleased` with the release date.
2. Confirm `pyproject.toml` has the intended version.
3. Run `make clean`.
4. Run `make check-all`.
5. Run `make test-unit`.
6. Run `make build`.
7. Install the wheel in a fresh Python 3.11+ venv.
8. Verify `vara --help` and `vara serve --help`.
9. Verify the wheel contains `vara/server/static/index.html`.
10. Push a signed tag in the form `vX.Y.Z`.

The `Publish` GitHub Action publishes tagged builds to PyPI using trusted
publishing, so PyPI must be configured to trust this repository and workflow.
