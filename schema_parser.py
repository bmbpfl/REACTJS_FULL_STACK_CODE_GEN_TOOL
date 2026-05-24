"""
schema_parser.py
Parses the flat CSV schema into a structured dict keyed by table name.
"""
import re
import pandas as pd


def parse_schema(df: pd.DataFrame) -> dict:
    """
    Returns:
      {
        "table_name": {
          "fields": [
            {
              "name": str,
              "data_type": str,
              "is_pk": bool,
              "required": bool,
              "max_len": int|None,
              "decimals": int|None,
              "java_type": str,
              "ts_type": str,
              "html_input": str,  # text|number|date|checkbox
            }
          ],
          "pk_field": str,
          "foreign_keys": [
            {
              "field": str,
              "ref_table": str,
              "ref_field": str,
            }
          ]
        }
      }
    """
    schema = {}
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    df = df.fillna("")

    for _, row in df.iterrows():
        table  = str(row.get("table_name", "")).strip()
        field  = str(row.get("field_name", "")).strip()
        dtype  = str(row.get("data_type", "")).strip().lower()
        identity = str(row.get("identity", "")).strip().lower()
        length   = row.get("len", "")
        dec      = row.get("dec", "")
        constraint = str(row.get("constraint", "")).strip()

        if not table or not field:
            continue

        if table not in schema:
            schema[table] = {"fields": [], "pk_field": None, "foreign_keys": []}

        is_pk = identity == "yes"
        if is_pk:
            schema[table]["pk_field"] = field

        try:   max_len = int(float(length)) if length != "" else None
        except: max_len = None
        try:   decimals = int(float(dec)) if dec != "" else None
        except: decimals = None

        java_type  = _java_type(dtype, is_pk)
        ts_type    = _ts_type(dtype)
        html_input = _html_input(dtype)

        schema[table]["fields"].append({
            "name":       field,
            "data_type":  dtype,
            "is_pk":      is_pk,
            "required":   is_pk,   # PK required; FK required determined below
            "max_len":    max_len,
            "decimals":   decimals,
            "java_type":  java_type,
            "ts_type":    ts_type,
            "html_input": html_input,
        })

        # Parse FK constraint
        # e.g. FOREIGN KEY (cat_id) REFERENCES mas_category(cat_id)
        if constraint:
            fk_match = re.search(
                r"FOREIGN\s+KEY\s*\((\w+)\)\s+REFERENCES\s+(\w+)\((\w+)\)",
                constraint, re.IGNORECASE
            )
            if fk_match:
                schema[table]["foreign_keys"].append({
                    "field":     fk_match.group(1),
                    "ref_table": fk_match.group(2),
                    "ref_field": fk_match.group(3),
                })
                # Mark FK field as required
                for f in schema[table]["fields"]:
                    if f["name"] == fk_match.group(1):
                        f["required"] = True

    return schema


def _java_type(dtype: str, is_pk: bool) -> str:
    dtype = dtype.lower()
    if "int" in dtype:
        return "Long" if is_pk else "Integer"
    if "varchar" in dtype or "char" in dtype or "text" in dtype:
        return "String"
    if "decimal" in dtype or "numeric" in dtype or "float" in dtype:
        return "BigDecimal"
    if "date" in dtype or "time" in dtype:
        return "LocalDateTime"
    if "bool" in dtype or "bit" in dtype:
        return "Boolean"
    return "String"


def _ts_type(dtype: str) -> str:
    dtype = dtype.lower()
    if "int" in dtype:
        return "number"
    if "decimal" in dtype or "float" in dtype or "numeric" in dtype:
        return "number"
    if "bool" in dtype or "bit" in dtype:
        return "boolean"
    return "string"


def _html_input(dtype: str) -> str:
    dtype = dtype.lower()
    if "int" in dtype:
        return "number"
    if "decimal" in dtype or "float" in dtype or "numeric" in dtype:
        return "number"
    if "date" in dtype or "time" in dtype:
        return "datetime-local"
    if "bool" in dtype or "bit" in dtype:
        return "checkbox"
    return "text"


def to_pascal(s: str) -> str:
    return "".join(w.capitalize() for w in s.split("_"))


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])
