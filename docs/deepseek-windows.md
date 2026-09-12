# DeepSeek credentials

The configured DeepSeek model is validated through the official endpoint. Enter
the key in the UI; it is stored in Windows Credential Manager, macOS Keychain or
Linux Secret Service. A container may receive `DEEPSEEK_API_KEY` or a mounted
secret referenced by `DEEPSEEK_API_KEY_FILE`; injected secrets are read-only.
Never place a real key in `.env`, screenshots, issues or repositories.

Search does not require DeepSeek. Before analysis or generation, review the
redacted professional preview and grant consent. Deleting a vault credential in
Settings removes application access; provider-side revocation remains available.
