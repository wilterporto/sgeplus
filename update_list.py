import os

filepath = 'app/templates/ouvidoria/manifestation_list.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("m.status == 'Pendente'", "OmbudsmanStatusEnum(m.status).name == 'PENDENTE'")
content = content.replace("m.status == 'Aceita'", "OmbudsmanStatusEnum(m.status).name == 'ACEITA'")
content = content.replace("m.status == 'Tramitando'", "OmbudsmanStatusEnum(m.status).name == 'TRAMITANDO'")
content = content.replace("m.status == 'Rejeitada'", "OmbudsmanStatusEnum(m.status).name == 'REJEITADA'")
content = content.replace("{{ m.status }}", "{{ OmbudsmanStatusEnum(m.status).label if m.status else '-' }}")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
    
print("List template updated")
