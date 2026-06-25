import os

replacements = {
    'app/templates/ouvidoria/manifestation_form.html': [
        ('form.nature_id', 'form.nature'),
    ],
    'app/templates/ouvidoria/subject_form.html': [
        ('form.nature_id', 'form.nature'),
    ],
    'app/templates/ouvidoria/subject_list.html': [
        ('form.nature_id', 'form.nature'),
        ('subject.nature.name', 'OmbudsmanNatureEnum(subject.nature).label if subject.nature else ""')
    ]
}

for filepath, reps in replacements.items():
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in reps:
        content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
print("Template forms updated")
