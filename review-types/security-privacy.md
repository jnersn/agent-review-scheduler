# Security and privacy review

**Purpose:** find ways that untrusted input, file access, network access or weak access control can harm users or expose their data.

**Scope:** the whole project, or the area named in the request. Run this type before each release.

**Look for:**
- **Untrusted input:** user input, uploads, file contents and metadata, API and webhook payloads, responses from other services, and output from subprocesses. Check size and parsing limits, crashes on malformed data, and values used as paths, queries, commands or templates without validation (injection).
- **Access control:** endpoints or actions missing an authentication or authorization check, checks done on the client only, and one user able to reach another user's data.
- **File access:** reads or writes outside the intended directories; path traversal or symlink following driven by names, metadata or remote data; files created with permissions that are too broad.
- **Secrets:** credentials, tokens or keys in the code, config files, logs or error messages.
- **Subprocesses and network:** how commands, arguments and the environment are built; TLS verification turned off; timeouts missing.
- **Downloads and updates:** integrity checks, where files land, and partial files that later get treated as complete.
- **Privacy:** personal data or user content in logs and analytics, and data sent over the network without the user's intent.
- **Permissions:** platform permissions, OAuth scopes, cloud roles or container privileges broader than the code needs, and debug-only settings that can reach production.

**Skip:** theoretical attacks with no entry point in this project; generic hardening advice.
