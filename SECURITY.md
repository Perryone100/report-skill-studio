# Security policy

## Supported versions

Security fixes are provided for the latest `0.4.x` release. Older development snapshots are not supported.

## Reporting a vulnerability

Please do not include vulnerabilities, credentials, transcripts, or personal report content in a public issue. Use GitHub's [private vulnerability reporting](https://github.com/Perryone100/report-skill-studio/security/advisories/new).

Include the affected version, operating system, reproducible conditions, impact, and the smallest synthetic example that demonstrates the issue. You should receive an acknowledgement within five business days. Fix and disclosure timing depends on severity and reproducibility.

## Security boundary

The supported v0.4 deployment is a single-user process bound to loopback. It is not a hosted or multi-tenant service. Do not expose the API to a LAN or the public internet without a separate design for authentication, authorization, TLS, rate limiting, tenant isolation, and auditing.

Provider credentials must remain in local environment configuration. Skills are declarative data and must not execute Python or JavaScript. Tests and reports submitted to the repository must use synthetic, non-sensitive content.
