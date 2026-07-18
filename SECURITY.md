# Security Policy

## Supported versions

Only the latest minor release is supported during the research alpha.

## Reporting a vulnerability

Do not open a public issue for vulnerabilities involving privacy, authorization bypass, unsafe educational decisions or secret exposure. Use GitHub private vulnerability reporting when enabled, or contact the repository owner through the GitHub profile.

## Deployment warning

The reference API has no production authentication or persistent storage. It must not be exposed publicly or connected to real student data. Production integration requires threat modeling, purpose-bound consent, least-privilege authorization, encryption, audit retention, rate limiting, tenant isolation and incident response.

## Sensitive-data policy

- Never commit real student identifiers, chat transcripts, assessment results, tokens or credentials.
- Synthetic data must carry an explicit synthetic marker.
- Withdrawn evidence must be excluded from new decisions while preserving a minimal lawful audit tombstone.
- Fairness attributes, if lawfully collected, must be isolated from student-facing disadvantage scoring.

