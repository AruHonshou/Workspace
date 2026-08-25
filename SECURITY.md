# Security policy

## Supported version

Only the latest tagged release is supported. This is a local, single-user
application and is not designed to be exposed to a LAN or the public internet.

## Safe defaults

- The API binds to `127.0.0.1`.
- Cloud model fallback and remote tracing are disabled.
- CVs, profile data, databases, logs, exports, and unverified 3D assets are
  ignored by Git.
- External job descriptions and portfolio pages are treated as untrusted data,
  never as agent instructions.
- The browser receives a sanitized event projection, not prompts, raw documents,
  secrets, or hidden reasoning.

## Reporting

Do not open a public issue containing a real CV, job application, token, or log.
Report vulnerabilities privately to the repository owner and include a minimal
synthetic reproduction.
