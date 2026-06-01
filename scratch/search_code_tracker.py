import os

root_dir = r"C:\Users\pc\.gemini\antigravity-ide\code_tracker"
print(f"Buscando arquivos 'academic.py' em {root_dir}...")

found = []
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if "academic" in file.lower() or "models" in file.lower():
            full_path = os.path.join(root, file)
            found.append((full_path, os.path.getsize(full_path)))

print(f"\nEncontrados {len(found)} arquivos:")
for path, size in found:
    print(f" - {path} (tamanho: {size} bytes)")
