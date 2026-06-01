import os
import re

scratch_dir = r"c:\Users\pc\source\sgeplus\scratch"
files = [f for f in os.listdir(scratch_dir) if f.startswith("extracted_matrices_jsonl_")]

print(f"Lendo {len(files)} candidatos de matrices em {scratch_dir}...")

assembled_lines = {}

for file in files:
    path = os.path.join(scratch_dir, file)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        matches = re.findall(r"^(\d+):\s*(.*)$", content, re.MULTILINE)
        for line_num_str, line_content in matches:
            line_num = int(line_num_str)
            assembled_lines[line_num] = line_content
            
    except Exception as e:
        print(f"Erro ao processar {file}: {e}")

print(f"Total de linhas individuais recuperadas: {len(assembled_lines)}")
if assembled_lines:
    max_line = max(assembled_lines.keys())
    print(f"Linha máxima encontrada: {max_line}")
    
    out_path = r"c:\Users\pc\source\sgeplus\scratch\reassembled_matrices.py"
    with open(out_path, "w", encoding="utf-8") as out:
        for i in range(1, max_line + 1):
            line = assembled_lines.get(i, "")
            out.write(line + "\n")
    print(f"Arquivo remontado salvo em {out_path}!")
else:
    print("Nenhuma linha numerada encontrada.")
