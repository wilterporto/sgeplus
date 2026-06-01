import os

convs_dir = r"C:\Users\pc\.gemini\antigravity-ide\conversations"
out_dir = r"c:\Users\pc\source\sgeplus\scratch\extracted"
os.makedirs(out_dir, exist_ok=True)

print(f"Buscando nos arquivos pb em {convs_dir}...")
pb_files = [os.path.join(convs_dir, f) for f in os.listdir(convs_dir) if f.endswith(".pb")]

candidate_idx = 0
for file_path in pb_files:
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        
        # Vamos buscar por class Tenant(db.Model) ou class User(
        idx = 0
        while True:
            idx = data.find(b"class Tenant(db.Model):", idx)
            if idx == -1:
                break
            
            # Achou! Vamos extrair um bloco de 60.000 bytes ao redor
            start = max(0, idx - 10000)
            end = min(len(data), idx + 50000)
            block = data[start:end]
            
            # Tenta decodificar
            text = block.decode("utf-8", errors="ignore")
            if "class User" in text:
                candidate_idx += 1
                cand_path = os.path.join(out_dir, f"candidate_{candidate_idx}.py")
                with open(cand_path, "w", encoding="utf-8") as out:
                    out.write(text)
                print(f"Salvo candidato {candidate_idx} de {os.path.basename(file_path)} em {cand_path}")
            
            idx += 100
    except Exception as e:
        print(f"Erro ao ler {file_path}: {e}")

print("Fim da varredura de arquivos pb.")
