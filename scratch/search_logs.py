import os
import json

root_dir = r"C:\Users\pc\.gemini\antigravity-ide"
print(f"Buscando arquivos de models.py em {root_dir}...")

transcripts = []
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file == "transcript.jsonl":
            full_path = os.path.join(root, file)
            transcripts.append((full_path, os.path.getmtime(full_path)))

transcripts.sort(key=lambda x: x[1], reverse=True)

candidate_count = 0
for path, _ in transcripts:
    print(f"\nAnalisando {path}...")
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "models.py" in line:
                    try:
                        obj = json.loads(line)
                        # Verificar em content
                        content = obj.get("content", "")
                        if "class User(UserMixin, db.Model):" in content and len(content) > 10000:
                            candidate_count += 1
                            out_path = f"c:\\Users\\pc\\source\\sgeplus\\scratch\\recovered_models_content_{candidate_count}.py"
                            with open(out_path, "w", encoding="utf-8") as out:
                                out.write(content)
                            print(f"  [CONTENT] Salvo candidato {candidate_count} ({len(content)} chars) em {out_path}")

                        # Verificar em tool_calls
                        tool_calls = obj.get("tool_calls", [])
                        for tc in tool_calls:
                            args = tc.get("args", {})
                            for k, v in args.items():
                                if isinstance(v, str) and "class User(UserMixin, db.Model):" in v and len(v) > 10000:
                                    candidate_count += 1
                                    out_path = f"c:\\Users\\pc\\source\\sgeplus\\scratch\\recovered_models_arg_{candidate_count}.py"
                                    with open(out_path, "w", encoding="utf-8") as out:
                                        out.write(v)
                                    print(f"  [ARG:{k}] Salvo candidato {candidate_count} ({len(v)} chars) em {out_path}")
                    except Exception as e:
                        pass
    except Exception as e:
        print(f"Erro ao ler {path}: {e}")

print(f"\nFim da busca. Foram salvos {candidate_count} candidatos.")
