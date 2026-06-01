import os

root_dir = r"C:\Users\pc\.gemini\antigravity-ide"
print(f"Buscando de forma genérica em {root_dir}...")

found = []
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith((".py", ".pb", ".jsonl", ".txt", ".md")):
            full_path = os.path.join(root, file)
            # Ignora a pasta scratch do workspace se ela estiver dentro de .gemini (não está, mas por precaução)
            if "sgeplus" in full_path:
                continue
            try:
                # Lê os primeiros 100KB do arquivo
                with open(full_path, "rb") as f:
                    content = f.read(100000)
                if b"class Tenant(" in content or b"class User(" in content or b"class AuditLog(" in content:
                    found.append((full_path, os.path.getsize(full_path)))
            except Exception:
                pass

print(f"Encontrados {len(found)} arquivos contendo referências:")
for path, size in found:
    print(f" - {path} (tamanho: {size} bytes)")
