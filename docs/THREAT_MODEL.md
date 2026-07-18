# Threat model

## 1. Assets

Purpose-bound consent, student evidence, profile versions, current rules, path/task outputs, service-assignment data, fairness-audit attributes, causal reports, human overrides, credentials and audit integrity.

## 2. Trust boundaries

External clients and uploaded evidence are untrusted. Enterprise systems, Feishu, model providers and rule sources are third parties whose responses require validation. Structured algorithms are trusted only within tested contracts. Generated explanations and human overrides are not automatically correct. Fairness attributes occupy a separately authorized audit zone.

## 3. Main threats and controls

| Threat | Impact | Reference control | Production requirement |
|---|---|---|---|
| Cross-student evidence | privacy breach and false profile | subject and consent ID equality check | tenant-aware authorization and row-level policy |
| Withdrawn/expired purpose | unlawful reuse | time/purpose `ConsentRecord.allows` | consent service and deletion/retention workflow |
| Prompt injection in evidence | tool/gate manipulation | evidence text is inert data; deterministic algorithms | sanitize retrieval, tool allowlist, LLM isolation |
| Rule poisoning or expiry | invalid path advice | source/version/window and hard gate | signed sources, four-eyes approval and refresh SLA |
| Duplicate evidence amplification | overconfident state | duplicate-group penalty | origin fingerprinting and provenance graph |
| Commercial objective override | coercive paid recommendation | Safe-VOI hard gate and dominance | independent governance approval and complaint audit |
| Causal claim upgrade | misleading enterprise claim | VA/SE types and claim levels | publication review and report template controls |
| Group selective exclusion | unequal support | coverage/error/burden audit | protected audit environment and remediation budget |
| Audit tampering | loss of accountability | append-only hash chain | durable WORM log, access control and key management |
| API abuse | denial, data exfiltration | strict schemas only in reference | authentication, rate limit, encryption and monitoring |
| Secret leakage | account compromise | `.gitignore`, no credentials | secret manager, scanning and rotation |
| Model/rule drift | silent behavior change | explicit versions and replay | shadow evaluation, canary and rollback |

## 4. Residual risk

The reference API has no authentication, authorization database, rate limiting, encrypted storage or tenant isolation. Its safe state is local synthetic evaluation. A production deployment is a new security scope and requires a formal data-protection impact assessment, architecture review and incident-response owner.
