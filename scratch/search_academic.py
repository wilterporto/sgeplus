import os
import json
import re

root_dir = r"C:\Users\pc\.gemini\antigravity-ide"
print(f"Buscando 'academic.py' nos logs em {root_dir}...")

found_files = []
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith((".py", ".pb", ".jsonl", ".txt", ".md")):
            full_path = os.path.join(root, file)
            try:
                with open(full_path, "rb") as f:
                    content = f.read()
                if b"def list_evaluations" in content or b"def academic_dashboard" in content:
                    found_files.append((full_path, len(content)))
            except Exception:
                pass

print(f"\nEncontrados {len(found_files)} arquivos:")
for path, size in found_files:
    print(f" - {path} (tamanho: {size} bytes)")
    
    if path.endswith(".jsonl"):
        print(f"   Extraindo do JSONL...")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                if "def list_evaluations" in line:
                    try:
                        obj = json.loads(line)
                        def check(val, key_path):
                            if isinstance(val, str) and "def list_evaluations" in val and len(val) > 10000:
                                cand_path = f"c:\\Users\\pc\\source\\sgeplus\\scratch\\extracted_academic_jsonl_{line_num}_{len(val)}.py"
                                with open(cand_path, "w", encoding="utf-8") as out:
                                    out.write(val)
                                print(f"     [SALVO] Candidato de {len(val)} bytes em {key_path} salvo em {cand_path}")
                            elif isinstance(val, dict):
                                for k, v in val.items():
                                    check(v, f"{key_path}.{k}")
                            elif isinstance(val, list):
                                for idx, item in enumerate(val):
                                    check(item, f"{key_path}[{idx}]")
                        check(obj, f"L{line_num}")
                    except Exception as e:
                        pass
