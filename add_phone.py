import sqlite3
import os

db_path = os.path.join('instance', 'idebmais.db')
print(f"Connecting to {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE participant ADD COLUMN phone VARCHAR(20)")
    print("Column 'phone' added to 'participant' table.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("Column 'phone' already exists in 'participant' table.")
    else:
        print(f"Error: {e}")

conn.commit()
conn.close()
