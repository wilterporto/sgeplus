import os

replacements = {
    'app/templates/ouvidoria/manifestation_detail.html': [
        ('manifestation.nature.name if manifestation.nature else', 'OmbudsmanNatureEnum(manifestation.nature).label if manifestation.nature else'),
        ('manifestation.status == \'Pendente\'', 'OmbudsmanStatusEnum(manifestation.status).name == \'PENDENTE\''),
        ('manifestation.status == \'Aceita\'', 'OmbudsmanStatusEnum(manifestation.status).name == \'ACEITA\''),
        ('manifestation.status == \'Tramitando\'', 'OmbudsmanStatusEnum(manifestation.status).name == \'TRAMITANDO\''),
        ('manifestation.status == \'Rejeitada\'', 'OmbudsmanStatusEnum(manifestation.status).name == \'REJEITADA\''),
        ('{{ manifestation.status }}', '{{ OmbudsmanStatusEnum(manifestation.status).label if manifestation.status else \'-\' }}'),
        ('{{ manifestation.requester_type }}', '{{ OmbudsmanRequesterTypeEnum(manifestation.requester_type).label if manifestation.requester_type else \'-\' }}'),
        ('{{ manifestation.entry_mode }}', '{{ OmbudsmanEntryModeEnum(manifestation.entry_mode).label if manifestation.entry_mode else \'-\' }}'),
    ],
    'app/templates/ouvidoria/public_detail.html': [
        ('manifestation.nature.name if manifestation.nature else', 'OmbudsmanNatureEnum(manifestation.nature).label if manifestation.nature else'),
        ('manifestation.status == \'Pendente\'', 'OmbudsmanStatusEnum(manifestation.status).name == \'PENDENTE\''),
        ('manifestation.status == \'Aceita\'', 'OmbudsmanStatusEnum(manifestation.status).name == \'ACEITA\''),
        ('manifestation.status == \'Tramitando\'', 'OmbudsmanStatusEnum(manifestation.status).name == \'TRAMITANDO\''),
        ('manifestation.status == \'Rejeitada\'', 'OmbudsmanStatusEnum(manifestation.status).name == \'REJEITADA\''),
        ('{{ manifestation.status }}', '{{ OmbudsmanStatusEnum(manifestation.status).label if manifestation.status else \'-\' }}'),
        ('{{ manifestation.requester_type }}', '{{ OmbudsmanRequesterTypeEnum(manifestation.requester_type).label if manifestation.requester_type else \'-\' }}'),
        ('{{ manifestation.entry_mode }}', '{{ OmbudsmanEntryModeEnum(manifestation.entry_mode).label if manifestation.entry_mode else \'-\' }}'),
    ],
    'app/templates/ouvidoria/email/created.html': [
        ('manifestation.nature.name if manifestation.nature else', 'OmbudsmanNatureEnum(manifestation.nature).label if manifestation.nature else'),
        ('{{ manifestation.status }}', '{{ OmbudsmanStatusEnum(manifestation.status).label if manifestation.status else \'-\' }}'),
    ]
}

for filepath, reps in replacements.items():
    if not os.path.exists(filepath): continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in reps:
        content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
print("Template details updated")
