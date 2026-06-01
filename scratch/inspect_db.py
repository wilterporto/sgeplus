import sqlite3
import os

db_path = r'c:\Users\pc\source\sgeplus\instance\idebmais.db'
if not os.path.exists(db_path):
    print("Database not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Vamos listar todas as tabelas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print(f"Total de tabelas encontradas: {len(tables)}")
for table in sorted(tables):
    try:
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
        row = cursor.fetchone()
        if row:
            print(f"\n--- DDL para '{table}' ---")
            print(row[0])
    except Exception as e:
        print(f"Erro ao ler tabela '{table}': {e}")

conn.close()
