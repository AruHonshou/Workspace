# Workspace security policy

Workspace is a local, single-user application. Run the UI on loopback and do not expose the API directly to the public Internet.

## Boundaries

- Credentials use the operating-system vault or runtime secret injection.
- Job search does not transmit a CV to the jobs provider.
- AI operations transmit their required professional context after the review and consent offered by the application.
- Documents and job descriptions are untrusted input.
- Private files, keys, databases and runtime logs must not be committed.
- File operations are restricted to the configured data and artifact locations.
- Tests use synthetic data and simulated providers.

The 3D desk and creator links are presentation features; they do not authenticate users or give external profiles access to local data.

## Reporting

Report vulnerabilities privately to the repository owner. Include a minimal synthetic reproduction and the affected version or commit. Do not include real CVs, credentials, candidate data or unredacted logs in public issues.

See the [privacy documentation](docs/privacy-threat-model.md) for implementation details.
