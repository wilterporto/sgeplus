import re

with open('app/templates/students/list.html', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('data-bs-toggle="modal" data-bs-target="#newStudentModal"', 'href="{{ url_for(\'students.new_student\') }}"')
c = c.replace('<button type="button" class="btn btn-primary" href', '<a class="btn btn-primary" href')
c = c.replace('Novo Aluno</button>', 'Novo Aluno</a>')

# Remove the New Student Modal block
# Note: we can just use re.sub from '<!-- New Student Modal -->' down to right before '<script>'
c = re.sub(r'<!-- New Student Modal -->.*?<script>', '<script>', c, flags=re.DOTALL)

# Remove the form error handling for newStudentModal
c = re.sub(r'const hasFormErrors = \"\{\{ \'true\' if form\.errors else \'false\' \}\}\" === \'true\';\s*if \(hasFormErrors\) \{\s*var newStudentModal = new bootstrap\.Modal\(document\.getElementById\(\'newStudentModal\'\)\);\s*newStudentModal\.show\(\);\s*\}', '', c)

# Remove the select2 init for dietary restrictions modal
c = re.sub(r'\$\(\'#modal_dietary_restrictions\'\)\.select2\(\{.*?\}\);', '', c, flags=re.DOTALL)

with open('app/templates/students/list.html', 'w', encoding='utf-8') as f:
    f.write(c)
print('Done list.html!')
