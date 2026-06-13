"""
SQL RAG chain: NL question → SQL → execute → NL answer.
Only available for billing_executive and admin roles.
"""
import re
import sqlite3

from groq import Groq

from config import settings

GROQ_MODEL = "llama-3.3-70b-versatile"


def _get_schema(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    schema_parts = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = cursor.fetchall()
        col_defs = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        cursor.execute(f"SELECT * FROM {table} LIMIT 3")
        sample = cursor.fetchall()
        schema_parts.append(f"Table: {table}\nColumns: {col_defs}\nSample rows: {sample}")
    conn.close()
    return "\n\n".join(schema_parts)


def _extract_sql(raw: str) -> str:
    raw = raw.strip()
    fenced = re.search(r"```(?:sql)?\s*([\s\S]+?)```", raw, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    match = re.search(r"(SELECT[\s\S]+?;)", raw, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    idx = raw.upper().find("SELECT")
    if idx >= 0:
        return raw[idx:].strip()
    return raw


def sql_rag_chain(question: str, db_path: str | None = None) -> str:
    """
    Three-step SQL RAG:
    1. NL question → SQL (LLM)
    2. Extract clean SQL from LLM output
    3. Execute SQL → NL answer (LLM)
    """
    if db_path is None:
        db_path = settings.db_path

    client = Groq(api_key=settings.groq_api_key)
    schema = _get_schema(db_path)

    # Step 1: Generate SQL
    sql_response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=512,
        messages=[
            {
                "role": "system",
                "content": "You are a SQL expert. Return ONLY the SQL query, no explanations or markdown.",
            },
            {
                "role": "user",
                "content": f"Schema:\n{schema}\n\nQuestion: {question}\n\nSQL:",
            },
        ],
    )
    raw_sql = sql_response.choices[0].message.content

    # Step 2: Extract clean SQL
    clean_sql = _extract_sql(raw_sql)

    # Step 3: Execute SQL
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(clean_sql)
        rows = cursor.fetchall()
        col_names = [d[0] for d in cursor.description] if cursor.description else []
        conn.close()
        result_str = f"Columns: {col_names}\nRows: {rows}"
    except Exception as e:
        return f"SQL execution error: {e}\nGenerated SQL: {clean_sql}"

    # Step 4: NL answer
    answer_response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful medical operations analyst. Answer clearly and concisely.",
            },
            {
                "role": "user",
                "content": f'Question: "{question}"\n\nSQL executed:\n{clean_sql}\n\nResult:\n{result_str}\n\nProvide a natural language answer.',
            },
        ],
    )
    return answer_response.choices[0].message.content
