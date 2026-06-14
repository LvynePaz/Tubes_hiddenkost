import psycopg2
import psycopg2.extras
import streamlit as st

@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        port=st.secrets.get("DB_PORT", 5432),
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
    )

def run_query(sql: str, params=None) -> list[dict]:
    conn = get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()

def run_explain(sql: str, params=None) -> list[str]:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(f"EXPLAIN ANALYZE {sql}", params)
        return [row[0] for row in cur.fetchall()]
