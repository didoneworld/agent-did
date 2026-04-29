import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


def _normalize_json_compatible(value):
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, list):
        return [_normalize_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_json_compatible(item) for key, item in value.items()}
    return value


def _parse_simple_yaml(path: Path) -> dict:
    return _normalize_json_compatible(yaml.safe_load(path.read_text()))


def test_json_schema_declares_expected_protocol_version():
    schema_path = Path(__file__).resolve().parents[1] / 'schemas/json/agent-id-record.schema.json'
    schema = json.loads(schema_path.read_text())
    assert schema['properties']['agent_id_protocol_version']['const'] == '0.2.0'
    assert len(schema['allOf']) == 4
    assert schema['properties']['authorization']['properties']['delegation_proof_formats']['minItems'] == 1


def test_json_schema_encodes_delegation_guards():
    schema_path = Path(__file__).resolve().parents[1] / 'schemas/json/agent-id-record.schema.json'
    schema = json.loads(schema_path.read_text())
    delegated_rule = schema['allOf'][1]['then']['properties']
    assert delegated_rule['authorization']['properties']['subject_context']['enum'] == [
        'on_behalf_of_user',
        'on_behalf_of_team',
        'multi_party',
    ]
    assert delegated_rule['governance']['properties']['identity_chain_preserved']['const'] is True


def test_examples_validate_against_json_schema():
    schema_path = Path(__file__).resolve().parents[1] / 'schemas/json/agent-id-record.schema.json'
    schema = json.loads(schema_path.read_text())
    validator = Draft202012Validator(schema)
    example_paths = [
        Path(__file__).resolve().parents[1] / 'examples/did-methods/did-web-agent.yaml',
        Path(__file__).resolve().parents[1] / 'examples/did-methods/did-key-agent.yaml',
    ]
    for example_path in example_paths:
        validator.validate(_parse_simple_yaml(example_path))


def test_did_web_example_uses_did_web():
    example_path = Path(__file__).resolve().parents[1] / 'examples/did-methods/did-web-agent.yaml'
    data = _parse_simple_yaml(example_path)
    assert data['agent']['did'].startswith('did:web:')
    assert data['authorization']['mode'] == 'delegated'
    assert data['governance']['provisioning'] == 'scim'
    assert data['bindings']['a2a']['endpoint_url'].startswith('https://')


def test_did_key_example_uses_did_key():
    example_path = Path(__file__).resolve().parents[1] / 'examples/did-methods/did-key-agent.yaml'
    data = _parse_simple_yaml(example_path)
    assert data['agent']['did'].startswith('did:key:')
    assert data['authorization']['mode'] == 'autonomous'
    assert data['governance']['provisioning'] == 'manual'
    assert data['bindings']['anp']['did'].startswith('did:key:')
