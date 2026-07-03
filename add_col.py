import sqlite3
import os

db_path = os.path.join('instance', 'idebmais.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE event RENAME COLUMN date TO start_date;")
    cursor.execute("ALTER TABLE event ADD COLUMN end_date DATE;")
    cursor.execute("ALTER TABLE event ADD COLUMN registration_start DATE;")
    cursor.execute("ALTER TABLE event ADD COLUMN registration_end DATE;")
    cursor.execute("ALTER TABLE event ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'Previsto';")
    cursor.execute("ALTER TABLE event ADD COLUMN workload INTEGER NOT NULL DEFAULT 0;")
    conn.commit()
    print("Columns added and renamed successfully.")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
