import json
import random
import string
from typing import Any, Optional
import anthropic
from faker import Faker
from ._ai_utils import parse_json_response
from ..config import config
from ..request_config import get_anthropic_api_key, ai_configured

fake = Faker()

BLOCKCHAIN_DOMAINS = {
    "ethereum_address": lambda: "0x" + "".join(random.choices("0123456789abcdef", k=40)),
    "tx_hash": lambda: "0x" + "".join(random.choices("0123456789abcdef", k=64)),
    "private_key": lambda: "0x" + "".join(random.choices("0123456789abcdef", k=64)),
    "ens_name": lambda: f"{fake.user_name()}.eth",
    "token_amount_wei": lambda: str(random.randint(1, 10**18)),
    "block_number": lambda: random.randint(17000000, 20000000),
    "gas_price_gwei": lambda: round(random.uniform(1, 100), 2),
}

DOMAIN_GENERATORS = {
    "email": fake.email,
    "name": fake.name,
    "phone": fake.phone_number,
    "address": fake.address,
    "company": fake.company,
    "url": fake.url,
    "uuid": fake.uuid4,
    "date": lambda: fake.date().isoformat(),
    "datetime": lambda: fake.date_time().isoformat(),
    "ip": fake.ipv4,
    "username": fake.user_name,
    "password": lambda: fake.password(length=12, special_chars=True, digits=True, upper_case=True),
    "credit_card": fake.credit_card_number,
    "jwt_token": lambda: f"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ7ZmFrZS51c2VyX25hbWUoKX0iLCJpYXQiOjE2MDAwMDAwMDB9.fake_signature_{fake.md5()[:20]}",
    "api_key": lambda: "ak_" + "".join(random.choices(string.ascii_letters + string.digits, k=32)),
    **BLOCKCHAIN_DOMAINS,
}


def _generate_value_from_schema(field_schema: dict, field_name: str = "") -> Any:
    field_type = field_schema.get("type", "string")
    format_ = field_schema.get("format", "")
    example = field_schema.get("example")

    if example is not None:
        return example

    name_lower = field_name.lower()
    for domain_key, generator in DOMAIN_GENERATORS.items():
        if domain_key in name_lower:
            return generator()

    if field_type == "string":
        if format_ == "email":
            return fake.email()
        if format_ == "date":
            return fake.date().isoformat()
        if format_ == "date-time":
            return fake.date_time().isoformat()
        if format_ == "uri" or format_ == "url":
            return fake.url()
        if format_ == "uuid":
            return str(fake.uuid4())
        min_len = field_schema.get("minLength", 3)
        max_len = field_schema.get("maxLength", 50)
        return fake.text(max_nb_chars=min(max_len, 100))[:max(min_len, 10)]

    if field_type == "integer":
        min_val = field_schema.get("minimum", 0)
        max_val = field_schema.get("maximum", 10000)
        return random.randint(min_val, max_val)

    if field_type == "number":
        min_val = field_schema.get("minimum", 0.0)
        max_val = field_schema.get("maximum", 10000.0)
        return round(random.uniform(min_val, max_val), 2)

    if field_type == "boolean":
        return random.choice([True, False])

    if field_type == "array":
        items_schema = field_schema.get("items", {"type": "string"})
        count = random.randint(1, 5)
        return [_generate_value_from_schema(items_schema) for _ in range(count)]

    if field_type == "object":
        properties = field_schema.get("properties", {})
        return {k: _generate_value_from_schema(v, k) for k, v in properties.items()}

    return fake.word()


def _generate_edge_cases(field_name: str, field_schema: dict) -> list[Any]:
    field_type = field_schema.get("type", "string")
    edges = []

    if field_type == "string":
        max_len = field_schema.get("maxLength", 255)
        min_len = field_schema.get("minLength", 0)
        edges += [
            "",
            " ",
            "a" * (max_len + 1) if max_len < 10000 else "boundary_exceeded",
            "'; DROP TABLE users; --",
            "<script>alert(1)</script>",
            "null",
            "undefined",
            "0",
            "\n\t\r",
            "🚀💀🔥",
        ]
        if min_len == 0:
            edges.append(None)

    if field_type in ("integer", "number"):
        minimum = field_schema.get("minimum")
        maximum = field_schema.get("maximum")
        edges += [0, -1, 2**31 - 1, -(2**31), 0.0]
        if minimum is not None:
            edges += [minimum - 1, minimum]
        if maximum is not None:
            edges += [maximum, maximum + 1]

    return edges[:8]


async def run(
    schema: str,
    count: int = 10,
    domain: str = "general",
    include_edge_cases: bool = True,
) -> dict:
    schema_dict: dict = {}
    try:
        schema_dict = json.loads(schema)
    except json.JSONDecodeError:
        if ai_configured():
            client = anthropic.AsyncAnthropic(api_key=get_anthropic_api_key())
            msg = await client.messages.create(
                model=config.claude_model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": f"Convert this schema description to a valid JSON Schema object:\n\n{schema}\n\nReturn only the JSON Schema object, no explanation.",
                }],
            )
            try:
                parsed, _ = parse_json_response(msg.content[0].text.strip())
                schema_dict = parsed if parsed is not None else {}
            except json.JSONDecodeError:
                return {"error": "Could not parse schema. Provide a valid JSON Schema or clear description with ANTHROPIC_API_KEY set."}
        else:
            return {"error": "Could not parse schema as JSON. Provide valid JSON Schema or set ANTHROPIC_API_KEY for natural language parsing."}

    properties = schema_dict.get("properties", {})
    if not properties and schema_dict.get("type") == "object":
        properties = schema_dict

    valid_records = []
    for _ in range(min(count, 100)):
        record = {}
        for field_name, field_schema in properties.items():
            if isinstance(field_schema, dict):
                record[field_name] = _generate_value_from_schema(field_schema, field_name)
        valid_records.append(record)

    edge_cases = []
    if include_edge_cases and properties:
        for field_name, field_schema in list(properties.items())[:5]:
            if isinstance(field_schema, dict):
                field_edges = _generate_edge_cases(field_name, field_schema)
                for edge_val in field_edges[:3]:
                    base_record = {k: _generate_value_from_schema(v, k) for k, v in properties.items() if isinstance(v, dict)}
                    base_record[field_name] = edge_val
                    edge_cases.append({"_edge_case_field": field_name, "_edge_value": repr(edge_val), **base_record})

    return {
        "schema_fields": list(properties.keys()),
        "valid_records": valid_records,
        "edge_cases": edge_cases[:20],
        "total_generated": len(valid_records) + len(edge_cases[:20]),
        "domain": domain,
        "summary": {
            "valid_count": len(valid_records),
            "edge_case_count": len(edge_cases[:20]),
            "blockchain_fields_detected": [f for f in properties if any(k in f.lower() for k in BLOCKCHAIN_DOMAINS)],
        },
    }
