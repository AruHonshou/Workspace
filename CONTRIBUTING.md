# Contributing

Use synthetic candidate and job data in code, issues, screenshots, fixtures, and
tests. Never commit real CVs, LinkedIn exports, application packages, model
weights, or third-party 3D files without a completed license record.

Before opening a pull request:

1. Run backend tests from `backend/`.
2. Run `pnpm test`, `pnpm typecheck`, and `pnpm build`.
3. Run the asset manifest validator.
4. Confirm replay mode works without a DeepSeek key or network access.
5. Review generated files and `git diff` for personal information.

Ame is the only visible orchestration scene. Internal agent prompts and behavior
must remain role-based; contributors must not add imitation of a real
entertainer's voice, identity, or personality.
