import os
import json

paths = [
    r"C:\Users\pc\.gemini\antigravity-ide\brain\70f78df4-9d92-43af-98fb-cb2f19730573\.system_generated\logs\transcript.jsonl",
    r"C:\Users\pc\.gemini\antigravity-ide\brain\84d6545e-2cac-4e91-b5e0-d1c5d14a4a0c\.system_generated\logs\transcript.jsonl"
]

print("Iniciando extração profunda dos arquivos transcript.jsonl...")

candidate_count = 0
for path in paths:
    if not os.path.exists(path):
        print(f"Arquivo não existe: {path}")
        continue
    
    print(f"\nLendo {path}...")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, 1):
            if "class User" in line or "class Tenant" in line or "models.py" in line:
                try:
                    obj = json.loads(line)
                    
                    # Vamos inspecionar todas as strings recursivamente neste objeto JSON
                    def check_val(val, source_info):
                        global candidate_count
                        if isinstance(val, str) and ("class User" in val or "class Tenant" in val) and len(val) > 5000:
                            candidate_count += 1
                            out_path = f"c:\\Users\\pc\\source\\sgeplus\\scratch\\recovered_models_{candidate_count}.py"
                            with open(out_path, "w", encoding="utf-8") as out:
                                out.write(val)
                            print(f"    [OK] Salvo candidato {candidate_count} ({len(val)} chars) do campo {source_info} em {out_path}")
                        elif isinstance(val, dict):
                            for k, v in val.items():
                                check_val(v, f"{source_info}.{k}")
                        elif isinstance(val, list):
                            for idx, item in enumerate(val):
                                check_val(item, f"{source_info}[{idx}]")
                    
                    check_val(obj, f"L{line_num}")
                except Exception as e:
                    pass

print(f"\nFinalizado. Candidatos salvos: {candidate_count}")
