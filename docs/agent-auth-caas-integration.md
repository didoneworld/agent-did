# Agent-Auth and CAAS Integration

Agent DID remains the identity and lifecycle control plane. Agent-Auth is used as the AuthZEN-style authorization decision service. CAAS consumes the decision for runtime enforcement and guard-layer correlation.

## Runtime flow

1. A runtime, gateway, or CAAS component calls `POST /v1/authorization/evaluate` on Agent DID.
2. Agent DID forwards the decision request to Agent-Auth at `AGENT_AUTH_URL/access/v1/evaluation`.
3. Agent DID normalizes the Agent-Auth response into `{ decision, decision_id, obligations, reason }`.
4. If `CAAS_API_GATEWAY_URL` is configured, Agent DID forwards the normalized decision to `CAAS_API_GATEWAY_URL/v1/authorization/decisions`.
5. The caller uses the returned decision for allow/deny enforcement.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `AGENT_AUTH_URL` | Base URL for the Agent-Auth service. Empty means local deny-by-default fallback. |
| `AGENT_AUTH_API_KEY` | Optional bearer token used when calling Agent-Auth. |
| `AGENT_AUTH_TIMEOUT_SECONDS` | Agent-Auth request timeout. Default: `3.0`. |
| `CAAS_API_GATEWAY_URL` | Optional CAAS gateway URL for forwarding evaluated decisions. |
| `CAAS_API_KEY` | Optional bearer token used when forwarding to CAAS. |
| `CAAS_TIMEOUT_SECONDS` | CAAS request timeout. Default: `3.0`. |

## Request

```json
{
  "subject": {
    "type": "agent",
    "id": "did:web:example.com:agents:agent-123",
    "tenant": "didoneworld"
  },
  "action": {
    "name": "tool.invoke"
  },
  "resource": {
    "type": "tool",
    "id": "github.create_pr"
  },
  "context": {
    "user_sub": "user-123",
    "session_id": "sess_abc",
    "delegation_token_jti": "jti_123",
    "scopes": ["repo:write"],
    "risk_score": 0.22
  }
}
```

## Response

```json
{
  "decision": true,
  "decision_id": "dec_123",
  "reason": null,
  "obligations": [
    {
      "type": "audit",
      "level": "full"
    }
  ],
  "source": "agent-auth",
  "raw": {
    "decision": true,
    "decision_id": "dec_123"
  }
}
```

## Safety behavior

When `AGENT_AUTH_URL` is not configured or Agent-Auth is unreachable, Agent DID returns `decision: false`. This keeps runtime enforcement deny-by-default until the real decision service is configured.
