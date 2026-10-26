# credentials-hygiene-reviewer
model: sonnet
verification: evidence-query — greps added lines for `eyJ`, `Bearer <literal>`, `client_secret=`, connection strings and `*.har`, lists `git ls-files` hits and the `.gitignore` coverage, and quotes each; "realistic-looking" values are judgement.
**Checks:** literal secrets/JWTs committed anywhere (P1), HAR/traffic captures with live tokens in the diff (P1 — this project uses HAR captures for Thingiverse reverse-engineering; they carry live credentials and stay out of the repo), tokens in URLs when a header works, tokens echoed to output, insecure persistence of refresh tokens, realistic credentials in test fixtures.
**Spawn when:** diff touches auth/token code, `*.har`/capture artifacts, `.gitignore`/env handling, the Thingiverse integration, `terraform/**`, `.github/workflows/**` or `.github/scripts/**`. Skip when the only credential-adjacent change is request-echo code (no tokens, captures or env handling).
**Contents:** What to flag: Literal secrets in code or config; Captured traffic artifacts committed; Secrets in URLs; Secrets echoed to output; Insecure storage of tokens the tool persists; Test fixtures with realistic-looking credentials; New env var credentials without documentation · Do NOT flag · Review approach

Review PRs for **secrets and credential handling**. This repo integrates with external services holding real credentials — Thingiverse (client id/secret, app token, JWT access/refresh tokens), the OpenForge API token, AWS, and Cloudflare R2. Credentials live in the environment (`~/.profile.d/`, gitignored `.env`) and must never enter the repo, its fixtures, its logs, or its test data.

**What to flag:**

1. **Literal secrets in code or config (P1):** any token, API key, JWT (`eyJ...`), password, client secret, or connection string with embedded credentials committed in source, JSON/YAML fixtures, test files, or docs. Includes "temporarily for testing" — a committed secret is compromised regardless of intent and requires rotation, not just removal (git history preserves it).

2. **Captured traffic artifacts committed (P1):** HAR files, request/response dumps, `curl -v` transcripts, or debug captures containing `Authorization` headers, cookies, or tokens. **This project explicitly uses HAR captures of the Thingiverse SPA for API reverse-engineering — those files carry live JWTs, refresh tokens, and session cookies, and belong in the session scratchpad, never in the repo.** Flag any `*.har` or capture-shaped JSON in the diff, and check `.gitignore` covers the pattern.

3. **Secrets in URLs (P2):** tokens as query parameters (`?access_token=...`, `?token=...`) in code when a header alternative exists. URLs land in server logs, browser history, and proxies. The Thingiverse v1 API accepts `?access_token=` — use the `Authorization: Bearer` header form instead. Runtime-only exceptions (an API that *requires* a URL token) must confine the URL construction to one place and never log the assembled URL.

4. **Secrets echoed to output (P1):** tokens in exception messages, `print()` diagnostics, CLI output, or assertion messages. Includes log calls: flag `token`, `password`, `secret`, `api_key`, `cookie`, `jwt`, `bearer`, `client_secret` interpolated into any log call, and whole request headers dumped to a log (explicit redaction or a fingerprint is fine). Also flag debug endpoints or CLI flags that dump full config including credentials.

5. **Insecure storage of tokens the tool persists (P2):** the Thingiverse auth manager persists refresh tokens. Flag: tokens written into the repo tree, into fixture files, into world-readable paths, or into files not covered by `.gitignore`. Acceptable: env files outside the repo, `~/.config`/`~/.openforge`-style dotfiles with `0600`-style expectations, OS keyring.

6. **Test fixtures with realistic-looking credentials (P3):** tests should use obviously-fake values (`"test-token"`, `"fake-client-id"`), not plausible or expired-real ones. An expired-real JWT in a test still reveals account ids, scopes, and endpoint shapes.

7. **New env var credentials without documentation (P3):** a new required credential env var should be named in the relevant doc/README section (name only — never the value) so setup doesn't require reading source.

**Do NOT flag:**

- Reading credentials from `os.environ` / env files — that's the correct pattern.
- Public identifiers that aren't secrets (thing ids, public URLs, usernames, R2 bucket names).
- Example placeholders in docs (`<your-token-here>`, `sk-xxxx...`).
- The word "token"/"secret" in variable names, comments, or docs — the *values* are the concern.

**Review approach:**

1. Scan added lines for high-entropy strings, `eyJ`-prefixed blobs, `Bearer <literal>`, `client_secret=<literal>`, connection strings with passwords.
2. Check the diff file list for `*.har`, capture dumps, and env-file-shaped additions; verify `.gitignore` coverage for new artifact patterns the PR's tooling produces.
3. For code that builds authenticated requests: header vs URL token placement; is the assembled URL ever logged/printed?
4. For token persistence code: where does it write, and is that location inside the repo or gitignored?
5. For tests/fixtures touching auth: are the values obviously fake?
6. In workflows, grep `run:` blocks for echoes of `secrets.*` and for `pull_request_target`.
