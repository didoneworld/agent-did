# Agent ID Protocol Draft

## Purpose

The Agent ID Protocol defines a versioned, protocol-neutral agent identity envelope built on W3C Decentralized Identifiers (DIDs).

It is intended to be published and reused across organizations, runtimes, and interoperability protocols.

## Non-Goals

- It does not define agent messaging.
- It does not replace A2A, ACP, or ANP.
- It does not define a new decentralized identifier format when W3C DID already exists.

## Core Principles

- W3C DID as identity foundation
- Protocol neutrality
- Explicit versioning
- Extensibility
- Backward-compatible evolution where feasible

## Core Record

```yaml
agent_id_protocol_version: "0.1.0"
agent:
  did: did:<method>:<method-specific-id>
  display_name: <human-readable-name>
  owner: <team-or-organization>
  role: <primary-role>
  environment: <environment>
  version: <version>
  status: <active|disabled|quarantine>
  trust_level: <internal|curated|external>
  capabilities:
    - <capability>
```

## Binding Model

Bindings are optional attachments to the DID-backed core record.

```yaml
bindings:
  a2a:
    endpoint_url: https://example.com/a2a
    agent_card_name: <agent-card-name>
  acp:
    endpoint_url: https://example.com/acp
  anp:
    did: did:<method>:<method-specific-id>
    endpoint_url: https://example.com/anp/message
```

## Evolution Model

- Every record declares `agent_id_protocol_version`.
- Consumers should ignore unknown extension fields.
- Binding blocks may expand independently of core identity fields.
- Future identity protocols may be mapped alongside DID, but DID is the default identity foundation.
