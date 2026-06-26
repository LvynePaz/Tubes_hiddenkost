import psycopg2, psycopg2.extras, streamlit as st

@st.cache_resource
def get_connection():
    conn = psycopg2.connect(
        host=st.secrets["DB_HOST"], port=st.secrets.get("DB_PORT", 5432),
        dbname=st.secrets["DB_NAME"], user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
    )
    conn.autocommit = True
    return conn

def run_query(sql, params=None):
    conn = get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []

def run_execute(sql, params=None):
    conn = get_connection()
    with conn.cursor() as cur:
        if params:
            cur.execute(sql, params)
        else:
            for s in [s.strip() for s in sql.split(";") if s.strip()]:
                cur.execute(s)

def run_explain(sql, params=None):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(f"EXPLAIN ANALYZE {sql}", params)
        return [r[0] for r in cur.fetchall()]

def run_explain_buffers(sql, params=None):
    """EXPLAIN (ANALYZE, BUFFERS) — lebih detail, ada info buffer hit/read."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {sql}", params)
        return [r[0] for r in cur.fetchall()]
