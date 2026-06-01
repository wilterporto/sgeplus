import os
import json

path = r"C:\Users\pc\.gemini\antigravity-ide\brain\70f78df4-9d92-43af-98fb-cb2f19730573\.system_generated\logs\transcript.jsonl"
print(f"Lendo as primeiras linhas de {path}...")

with open(path, "r", encoding="utf-8", errors="ignore") as f:
    for i, line in enumerate(f):
        if i >= 15:
            break
        try:
            obj = json.loads(line)
            print(f"\nLinha {i+1}:")
            print(f" - step_index: {obj.get('step_index')}")
            print(f" - type: {obj.get('type')}")
            print(f" - source: {obj.get('source')}")
            print(f" - keys: {list(obj.keys())}")
            # Se tiver tool_calls, mostra os nomes
            if "tool_calls" in obj:
                tc_names = [tc.get("name") for tc in obj["tool_calls"]]
                print(f" - tool_calls: {tc_names}")
        except Exception as e:
            print(f"Erro na linha {i+1}: {e}")
