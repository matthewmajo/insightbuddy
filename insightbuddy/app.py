
import streamlit as st
import sqlite3
import pandas as pd
from openai import OpenAI
import os
import re

# --- Load API key securely ---
api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=api_key)

# --- Create or connect to SQLite DB ---
conn = sqlite3.connect("sample.db")
cursor = conn.cursor()

# --- Sample schema and data (only runs once) ---
def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        signup_date TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        total REAL,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    if cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        cursor.executemany("INSERT INTO users (name, signup_date) VALUES (?, ?)", [
            ("Alice", "2023-01-10"),
            ("Bob", "2023-02-15"),
            ("Charlie", "2023-03-20")
        ])
        cursor.executemany("INSERT INTO orders (user_id, total, created_at) VALUES (?, ?, ?)", [
            (1, 120.50, "2024-04-01"),
            (2, 250.00, "2024-04-02"),
            (1, 75.00, "2024-05-01")
        ])
        conn.commit()

init_db()

# --- Define schema string ---
schema = """
Tables:
- users(id INTEGER, name TEXT, signup_date TEXT)
- orders(id INTEGER, user_id INTEGER, total REAL, created_at TEXT)
"""

# --- App UI ---
st.title("🧠 InsightBuddy - AI SQL Assistant")
query = st.text_input("Ask a question about your data:", placeholder="e.g., What are the total orders this month?")

if query:
    with st.spinner("Thinking..."):
        prompt = f"""
You are a helpful assistant that writes SQL queries based on a question and schema.

Schema:
{schema}

User Question: {query}

SQL:
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You translate questions into SQL."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )


            # Extract SQL code block using regex
            content = response.choices[0].message.content.strip()
            sql_match = re.search(r"```sql\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
            
            if sql_match:
                sql_code = sql_match.group(1).strip()
            else:
                # Fallback: try to isolate last SQL-looking block
                lines = content.strip().splitlines()
                sql_code = "\n".join(line for line in lines if line.strip().lower().startswith(("select", "with", "insert", "update", "delete", "create", "drop")))
            
            st.code(sql_code, language="sql")

            try:
                df = pd.read_sql_query(sql_code, conn)
                st.dataframe(df)
                if len(df.columns) == 2 and pd.api.types.is_numeric_dtype(df[df.columns[1]]):
                    st.bar_chart(df.set_index(df.columns[0]))
            except Exception as e:
                st.error(f"SQL execution error: {e}")
        except Exception as e:
            st.error(f"OpenAI API error: {e}")
