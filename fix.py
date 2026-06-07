import re

with open('app/utils/analytics.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update signatures
content = content.replace(
    'bolsa=None, dietary=None):',
    'bolsa=None, dietary=None, indigenous=None, quilombola=None):'
)

# 2. Add indigenous and quilombola filters for query (get_dashboard_data, _get_total_students_count, get_absence_reasons_data)
dietary_filter_re = r"    if dietary and len\(dietary\) > 0:\s*if 'Sim' in dietary and 'N.?o' not in dietary:\s*query = query\.filter\(Student\.dietary_restrictions\.any\(\)\)\s*elif 'N.?o' in dietary and 'Sim' not in dietary:\s*query = query\.filter\(~Student\.dietary_restrictions\.any\(\)\)"

new_filters = """
    if indigenous and len(indigenous) > 0:
        if 'Sim' in indigenous and 'N\\u00e3o' not in indigenous and 'N\\u01d0o' not in indigenous and 'N\\u00e0o' not in indigenous:
            query = query.filter(Student.indigenous_people_id.isnot(None))
        elif ('N\\u00e3o' in indigenous or 'N\\u01d0o' in indigenous or 'N\\u00e0o' in indigenous) and 'Sim' not in indigenous:
            query = query.filter(Student.indigenous_people_id.is_(None))
    if quilombola and len(quilombola) > 0:
        if 'Sim' in quilombola and 'N\\u00e3o' not in quilombola and 'N\\u01d0o' not in quilombola and 'N\\u00e0o' not in quilombola:
            query = query.filter(Student.is_quilombola == True)
        elif ('N\\u00e3o' in quilombola or 'N\\u01d0o' in quilombola or 'N\\u00e0o' in quilombola) and 'Sim' not in quilombola:
            query = query.filter(Student.is_quilombola == False)
"""

content = re.sub(dietary_filter_re, lambda m: m.group(0) + new_filters, content)

# 3. Add to base_query in get_rankings_data
dietary_base_re = r"      if dietary and len\(dietary\) > 0:\s*if 'Sim' in dietary and 'N.?o' not in dietary:\s*base_query = base_query\.filter\(Student\.dietary_restrictions\.any\(\)\)\s*elif 'N.?o' in dietary and 'Sim' not in dietary:\s*base_query = base_query\.filter\(~Student\.dietary_restrictions\.any\(\)\)"

new_base_filters = """
      if indigenous and len(indigenous) > 0:
          if 'Sim' in indigenous and 'N\\u00e3o' not in indigenous and 'N\\u01d0o' not in indigenous and 'N\\u00e0o' not in indigenous:
              base_query = base_query.filter(Student.indigenous_people_id.isnot(None))
          elif ('N\\u00e3o' in indigenous or 'N\\u01d0o' in indigenous or 'N\\u00e0o' in indigenous) and 'Sim' not in indigenous:
              base_query = base_query.filter(Student.indigenous_people_id.is_(None))
      if quilombola and len(quilombola) > 0:
          if 'Sim' in quilombola and 'N\\u00e3o' not in quilombola and 'N\\u01d0o' not in quilombola and 'N\\u00e0o' not in quilombola:
              base_query = base_query.filter(Student.is_quilombola == True)
          elif ('N\\u00e3o' in quilombola or 'N\\u01d0o' in quilombola or 'N\\u00e0o' in quilombola) and 'Sim' not in quilombola:
              base_query = base_query.filter(Student.is_quilombola == False)
"""

content = re.sub(dietary_base_re, lambda m: m.group(0) + new_base_filters, content)

# 4. Update function calls inside get_dashboard_data
content = content.replace(
    'bolsa=bolsa,\n        dietary=dietary\n    )',
    'bolsa=bolsa,\n        dietary=dietary,\n        indigenous=indigenous,\n        quilombola=quilombola\n    )'
)

with open('app/utils/analytics.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated analytics.py')
