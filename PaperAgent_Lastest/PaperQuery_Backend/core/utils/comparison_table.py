"""Parse structured comparison output without losing the model's original text."""
import json
import re


def parse_comparison_table(raw):
    candidates = [raw.strip(), *re.findall(r'```(?:json)?\s*\n?([\s\S]*?)```', raw, re.I)]
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, str):
                value = json.loads(value)
            if not isinstance(value, dict):
                continue
            columns, rows = value.get('columns'), value.get('rows')
            if not isinstance(columns, list) or not columns or not all(isinstance(c, str) and c.strip() for c in columns):
                continue
            if len(set(columns)) != len(columns) or not isinstance(rows, list):
                continue
            if not all(isinstance(row, dict) or (isinstance(row, list) and len(row) == len(columns)) for row in rows):
                continue
            return {'columns': columns, 'rows': [dict(zip(columns, row)) if isinstance(row, list) else row for row in rows]}
        except (ValueError, TypeError):
            continue
    return None
