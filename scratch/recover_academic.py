import os
import re

convs_dir = r"C:\Users\pc\.gemini\antigravity-ide\conversations"
output_path = r"c:\Users\pc\source\sgeplus\app\models.py"

print(f"Scanning IDE conversations directory: {convs_dir}")
if not os.path.exists(convs_dir):
    print("Conversations folder does not exist.")
    exit(1)

# List all .pb files sorted by modification time descending (latest first)
pb_files = []
for file in os.listdir(convs_dir):
    if file.endswith(".pb"):
        file_path = os.path.join(convs_dir, file)
        pb_files.append((file_path, os.path.getmtime(file_path)))

pb_files.sort(key=lambda x: x[1], reverse=True)

recovered = False
for file_path, mtime in pb_files:
    if recovered:
        break
        
    print(f"Scanning log file: {file_path}")
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            
        keyword = b"class AuditLog(db.Model):"
        idx = 0
        while True:
            idx = data.find(keyword, idx)
            if idx == -1:
                break
            
            print(f"  Found keyword '{keyword.decode()}' at byte offset: {idx}")
            # Locate the start of models.py
            start_keyword = b"from werkzeug.security import generate_password_hash"
            start_idx = data.rfind(start_keyword, 0, idx)
            if start_idx != -1:
                # Go backwards slightly to catch "from datetime import"
                datetime_keyword = b"from datetime import"
                start_dt = data.rfind(datetime_keyword, 0, start_idx)
                if start_dt != -1 and (start_idx - start_dt < 2000):
                    start_pos = start_dt
                else:
                    start_pos = start_idx
            else:
                start_pos = max(0, idx - 30000) # fallback
                
            # Locate the end of models.py (e.g. where Country class is)
            end_keyword = b"class Country(db.Model):"
            end_idx = data.find(end_keyword, idx)
            if end_idx != -1:
                # Find the next class or end of block
                end_pos = end_idx + 1500
            else:
                end_pos = min(len(data), idx + 20000) # fallback
                
            block = data[start_pos:end_pos]
            try:
                text = block.decode("utf-8", errors="ignore")
                if "class User(UserMixin, db.Model):" in text and "class Tenant(db.Model):" in text:
                    print(f"  -> SUCCESS! Found matched models.py source block of size {len(text)}!")
                    cleaned_lines = []
                    lines = text.split('\n')
                    for line in lines:
                        printable_ratio = len([c for c in line if c.isprintable() or c in '\r\t ']) / (len(line) + 1)
                        if printable_ratio > 0.85:
                            line = re.sub(r'^[^\s\w#@\'\"\[\(\{]+', '', line)
                            cleaned_lines.append(line)
                    
                    full_code = "\n".join(cleaned_lines)
                    with open(output_path, "w", encoding="utf-8") as out:
                        out.write(full_code)
                    
                    recovered = True
                    break
            except Exception as e:
                print(f"  Failed to decode block: {e}")
                
            idx += len(keyword)
            
    except Exception as e:
        print(f"Error scanning file {file_path}: {e}")

if recovered:
    print("\nRECOVERY OF models.py WORKED PERFECTLY FROM SESSION PROTOBUF LOG!")
else:
    print("\nRecovery failed. No matching source block found.")
