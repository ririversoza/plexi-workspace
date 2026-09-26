# Security Policy

## Handling secrets

Agents must never commit secrets to this repository. Secrets include API tokens,
passwords, private keys, credentials, environment files, and any other sensitive
configuration values.

- Store secrets in an approved secret manager or local environment variables.
- Commit only sanitized example configuration with placeholder values.
- Review staged changes before every commit to confirm that no secret is present.
- Do not copy suspected secrets into issues, chat messages, logs, or commit messages.

## Suspected leaks

If an agent finds or suspects a leaked secret, they must stop handling or sharing
the value and report it to the manager immediately. The report should identify
the affected file or commit without reproducing the secret. Treat the secret as
compromised until the manager confirms that it has been revoked or rotated.

Agents must not conceal a leak by rewriting history or deleting evidence unless
the manager explicitly directs the remediation.
