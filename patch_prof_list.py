import re

with open('app/templates/professors/list.html', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('data-bs-toggle="modal" data-bs-target="#newProfessorModal"', 'href="{{ url_for(\'professors.new_professor\') }}"')
c = c.replace('<button type="button" class="btn btn-primary" href', '<a class="btn btn-primary" href')
c = c.replace('Novo Professor</button>', 'Novo Professor</a>')

# Remove modal
c = re.sub(r'<!-- New Professor Modal -->.*?<script>', '<script>', c, flags=re.DOTALL)

# Remove script errors
c = re.sub(r'const hasFormErrors = \"\{\{ \'true\' if form\.errors else \'false\' \}\}\" === \'true\';\s*if \(hasFormErrors\) \{\s*var newProfessorModal = new bootstrap\.Modal\(document\.getElementById\(\'newProfessorModal\'\)\);\s*newProfessorModal\.show\(\);\s*\}', '', c)

# Remove select2 init for dietary restrictions modal
c = re.sub(r'\$\(\'#modal_dietary_restrictions\'\)\.select2\(\{.*?\}\);', '', c, flags=re.DOTALL)

with open('app/templates/professors/list.html', 'w', encoding='utf-8') as f:
    f.write(c)
print('Done list.html!')
