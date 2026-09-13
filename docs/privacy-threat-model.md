# Privacy and threat model

[Español](privacy-threat-model.es.md)

- The API and UI bind only to loopback and use an HTTP-only session cookie.
- Keys use Windows Credential Manager, macOS Keychain or Linux Secret Service;
  containers may receive read-only runtime secrets.
- Original PDFs and private contact data remain local. Only the exact redacted
  professional preview shown to and approved by the user may reach DeepSeek.
- Search providers receive role/geography only and never candidate records.
- DeepSeek receives minimum confirmed professional records and job text only
  after purpose-specific consent.
- Job text is untrusted data and cannot change instructions or activate tools.
- Logs and errors are sanitized; remote tracing remains disabled.
- Deleting a profile or Favorite also removes its recorded generated PDF/DOCX
  files, but only when their resolved paths remain inside Workspace's configured
  artifact directory.
- The app never signs into portals, fills forms, sends email, or applies.
