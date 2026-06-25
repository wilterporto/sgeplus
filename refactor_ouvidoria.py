import re

with open('app/routes/ouvidoria.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. get_subjects
content = content.replace(
    'subjects = OmbudsmanSubject.query.filter_by(nature_id=nature_id, active=True, tenant_id=tenant_id).order_by(OmbudsmanSubject.name).all()',
    'subjects = OmbudsmanSubject.query.filter_by(nature=nature_id, active=True, tenant_id=tenant_id).order_by(OmbudsmanSubject.name).all()'
)

# 2. subject_list
content = re.sub(
    r'    natures = OmbudsmanNature\.query\.filter_by\(tenant_id=None, active=True\)\.order_by\(OmbudsmanNature\.name\)\.all\(\)\n    form\.nature_id\.choices = \[\(n\.id, n\.name\) for n in natures\]\n',
    '',
    content
)
content = content.replace('nature_id=form.nature_id.data', 'nature=form.nature.data')
content = content.replace('subject.nature_id = form.nature_id.data', 'subject.nature = form.nature.data')
content = content.replace("render_template('ouvidoria/subject_list.html', subjects=subjects, form=form)", "render_template('ouvidoria/subject_list.html', subjects=subjects, form=form, OmbudsmanNatureEnum=OmbudsmanNatureEnum)")

# 3. dashboard nature query
old_nature_query = """    # 3. Quantity by Nature
    nature_data = db.session.query(
        OmbudsmanNature.name,
        func.count(OmbudsmanManifestation.id)
    ).join(OmbudsmanManifestation).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanNature.name).all()"""

new_nature_query = """    # 3. Quantity by Nature
    nature_data_raw = db.session.query(
        OmbudsmanManifestation.nature,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.nature).all()
    nature_data = [(OmbudsmanNatureEnum(n).label if n else 'Desconhecida', count) for n, count in nature_data_raw]"""

content = content.replace(old_nature_query, new_nature_query)

# 4. other dashboard queries to Enum
old_status_query = """    # 2. Quantity by Status
    status_data = db.session.query(
        OmbudsmanManifestation.status,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.status).all()"""

new_status_query = """    # 2. Quantity by Status
    status_data_raw = db.session.query(
        OmbudsmanManifestation.status,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.status).all()
    status_data = [(OmbudsmanStatusEnum(s).label if s else 'Desconhecido', count) for s, count in status_data_raw]"""

content = content.replace(old_status_query, new_status_query)

old_requester = """    # 5. Quantity by Requester Type
    requester_type_data = db.session.query(
        OmbudsmanManifestation.requester_type,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.requester_type).all()"""

new_requester = """    # 5. Quantity by Requester Type
    requester_type_data_raw = db.session.query(
        OmbudsmanManifestation.requester_type,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.requester_type).all()
    requester_type_data = [(OmbudsmanRequesterTypeEnum(r).label if r else 'Desconhecido', count) for r, count in requester_type_data_raw]"""
content = content.replace(old_requester, new_requester)

old_entry = """    # 6. Quantity by Entry Mode
    entry_mode_data = db.session.query(
        OmbudsmanManifestation.entry_mode,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.entry_mode).all()"""

new_entry = """    # 6. Quantity by Entry Mode
    entry_mode_data_raw = db.session.query(
        OmbudsmanManifestation.entry_mode,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.entry_mode).all()
    entry_mode_data = [(OmbudsmanEntryModeEnum(e).label if e else 'Desconhecido', count) for e, count in entry_mode_data_raw]"""
content = content.replace(old_entry, new_entry)

with open('app/routes/ouvidoria.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done refactoring ouvidoria.py")
