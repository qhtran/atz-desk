# CI workflow staging

GitHub rejected pushing `.github/workflows/*.yml` with the current token (missing `workflow` scope).

**To enable CI:** copy this file into the canonical Actions path:

```bash
mkdir -p .github/workflows
cp docs/ci/github-actions-ci.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "ci: enable GitHub Actions workflow"
git push
```

(Use a credential with the `workflow` OAuth/PAT scope.)
