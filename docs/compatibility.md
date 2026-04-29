# Compatibility And Evolution

## Versioning

- Every Agent ID record declares `agent_id_protocol_version`.
- Minor additions should be backward compatible.
- Breaking changes should require a new major version.

## Consumer Rules

- Consumers should ignore unknown extension fields.
- Consumers should validate required DID and binding fields only for the bindings they implement.
- Consumers should not treat interoperability protocol identifiers as the primary identity.

## Binding Independence

- A2A, ACP, and ANP bindings may evolve independently of the core DID-backed record.
- Multiple bindings may coexist on one record.
- Bindings may be omitted entirely.
