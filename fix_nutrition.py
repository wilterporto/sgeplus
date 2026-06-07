import re

with open('app/routes/nutrition.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('def export_risk_report')
prefix = content[:start_idx]
suffix = content[start_idx:]

# Find the LAST occurrence of the return render_template for dashboard
matches = list(re.finditer(r"return render_template\('nutrition/dashboard\.html',.*?\)", prefix))
if len(matches) > 1:
    # There are multiple occurrences, meaning dashboard is duplicated
    # The first occurrence is the end of the correct dashboard
    first_match = matches[0]
    # We slice up to the end of the first match, then append the suffix
    new_content = prefix[:first_match.end()] + '\n\n\n' + suffix
    with open('app/routes/nutrition.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed duplication.")
else:
    print("No duplication found.")
