# Security Policy

Life Topography is pre-alpha and must not be trusted with real personal data yet.

## Reporting

Do not open public issues containing personal data, credentials, tokens, vault material, or exploit details. Use GitHub private vulnerability reporting when available.

## Security boundaries

- Localhost is the default API/MCP boundary.
- Connectors receive only their declared credentials and capabilities.
- Credentials never enter the evidence store.
- Derived artifacts are treated as sensitive and deletable.
- Ordinary SQLite builds are not encrypted; production readiness requires a tested encrypted storage path.

No telemetry or remote inference is enabled by default.
