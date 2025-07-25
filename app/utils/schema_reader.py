# app/utils/schema_reader.py

import pandas as pd
from app.db.sql_connection import get_db_connection


def get_schema_and_sample_data():
    """
    Returns:
    - structured_schema: dict -> {table_name: [column1, column2, ...]}
    - schema_text: str -> Flattened for prompt input (table(column1, column2))
    - sample_data: set -> Unique values from top rows of tables
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get schema: {table: [columns]}
    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """)
    rows = cursor.fetchall()

    structured_schema = {}
    for table, column in rows:
        structured_schema.setdefault(table, []).append(column)

    # Flattened schema format: table(col1, col2) - for GPT use
    schema_text_lines = []
    for table, columns in structured_schema.items():
        schema_text_lines.append(f"{table}({', '.join(columns)})")
    schema_text = "\n".join(schema_text_lines)

    # Sample data collection: top 5 rows from each table
    all_sample_data = []
    for table in structured_schema:
        try:
            df = pd.read_sql(f"SELECT TOP 5 * FROM {table}", conn)
            sample_values = df.astype(str).values.flatten().tolist()
            all_sample_data.extend([val.lower() for val in sample_values if isinstance(val, str)])
        except Exception:
            continue  # Skip unreadable tables or permission issues

    conn.close()

    return structured_schema, schema_text, set(all_sample_data)


def get_db_schema():
    """
    Returns schema formatted as:
    table_name(column1, column2, ...)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """)
    rows = cursor.fetchall()

    schema = {}
    for table, column in rows:
        schema.setdefault(table, []).append(column)

    conn.close()

    # Convert to flattened format
    lines = [f"{table}({', '.join(columns)})" for table, columns in schema.items()]
    return "\n".join(lines)
