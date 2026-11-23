# Security Policy

## Supported version

Security fixes currently target the latest `main` branch and the `0.1.x`
reference implementation.

## Reporting

Do not open a public issue for credentials, authorization bypasses, unsafe
file access, or source-data exposure. Report the issue privately through the
GitHub repository's security advisory feature.

Include the affected version, reproduction steps, impact, and the smallest
possible test case. Do not attach private scientific data or credentials.

## Deployment boundary

HELIX v0.1 is a single-user local reference implementation. It binds to
`127.0.0.1` by default and does not provide accounts, multi-tenant isolation,
or production authorization. Do not expose it directly to the public internet.

Model keys are read from process environment variables and must not be
committed. Runtime databases, downloaded source objects, model checkpoints,
exports, and `.env` files are excluded from release archives.

The manifest downloader restricts network targets and file sizes, but
application-level checks are not a substitute for an isolated network policy
in production.
