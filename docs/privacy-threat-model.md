# Privacy and threat model

[Español](privacy-threat-model.es.md)

- The API and UI bind only to loopback and use an HTTP-only session cookie.
- The API key is stored exclusively in Windows Credential Manager.
- The original PDF, contact data, and source documents never leave the computer.
- DeepSeek receives confirmed professional facts without contact data and minimum job text.
- Job text is untrusted data and cannot change instructions or activate tools.
- Logs, SSE, and errors are sanitized; remote tracing remains disabled.
- The app never signs into portals, fills forms, sends email, or applies.
