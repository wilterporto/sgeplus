import sqlite3
import os

db_path = r"c:\Users\pc\source\sgeplus\instance\idebmais.db"

if not os.path.exists(db_path):
    print("Database path not found! Checking fallback...")
    db_path = "instance/idebmais.db"

print(f"Connecting to SQLite database at {db_path}...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create table if not exists
query = """
CREATE TABLE IF NOT EXISTS question_unit_validations (
    question_id INTEGER NOT NULL,
    teaching_unit_id INTEGER NOT NULL,
    PRIMARY KEY (question_id, teaching_unit_id),
    FOREIGN KEY(question_id) REFERENCES question(id) ON DELETE CASCADE,
    FOREIGN KEY(teaching_unit_id) REFERENCES teaching_unit(id) ON DELETE CASCADE
);
"""

cursor.execute(query)
conn.commit()

print("Table 'question_unit_validations' checked/created successfully!")

# Verify columns and tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='question_unit_validations';")
result = cursor.fetchone()
if result:
    print(f"Verification Success: Table '{result[0]}' is present in database.")
else:
    print("Verification Error: Table was not found after creation attempt.")

conn.close()
