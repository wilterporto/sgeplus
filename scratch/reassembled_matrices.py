from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db
from app.models import ReferenceMatrix, Descriptor, SchoolYear, Subject, Theme
from app.forms import ReferenceMatrixForm, DescriptorForm, ImportDescriptorForm, ThemeForm
import pandas as pd
from werkzeug.utils import secure_filename
8: matrices_bp = Blueprint('matrices', __name__)

10: # --- Matrices CRUD ---
# --- Matrices CRUD ---
@matrices_bp.route('/', methods=['GET', 'POST'])
def list_matrices():
matrices = ReferenceMatrix.query.all()
form = ReferenceMatrixForm()
16:     if form.validate_on_submit():
17:     if form.validate_on_submit():
matrix = ReferenceMatrix(
name=form.name.data,
description=form.description.data
)
db.session.add(matrix)
db.session.commit()
flash('Matriz criada com sucesso!', 'success')
return redirect(url_for('matrices.list_matrices'))
26:     return render_template('matrices/list.html', matrices=matrices, form=form)
log_audit('CREATE', 'ReferenceMatrix', matrix.id, f"Criou a matriz de referência '{matrix.name}'")
28: @matrices_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
return redirect(url_for('matrices.list_matrices'))
def edit_matrix(id):
matrix = ReferenceMatrix.query.get_or_404(id)
form = ReferenceMatrixForm(obj=matrix)
33:     if form.validate_on_submit():
def edit_matrix(id):
matrix.name = form.name.data
matrix.description = form.description.data
db.session.commit()
flash('Matriz atualizada.', 'success')
return redirect(url_for('matrices.list_matrices'))
40
log_audit('UPDATE', 'ReferenceMatrix', matrix.id, f"Editou a matriz de referência '{matrix.name}'")
flash('Matriz atualizada.', 'success')
return redirect(url_for('matrices.list_matrices'))
44:     return render_template('matrices/edit.html', form=form, matrix=matrix)

46:     return render_template('matrices/edit.html', form=form, matrix=matrix)

48: # --- Themes Management ---

@matrices_bp.route('/themes', methods=['GET', 'POST'])
def list_themes():
themes = Theme.query.all()
form = ThemeForm()
form.matrix_id.choices = [(0, 'Selecione um item...')] + [(m.id, m.name) for m in ReferenceMatrix.query.all()]
55:     if form.validate_on_submit():

if form.matrix_id.data == 0:
flash('Selecione uma Matriz válida.', 'danger')
else:
theme = Theme(name=form.name.data, matrix_id=form.matrix_id.data)
db.session.add(theme)
db.session.commit()
from app.audit_utils import log_audit
log_audit('CREATE', 'Theme', theme.id, f"Criou o tema '{theme.name}' vinculado à matriz ID {theme.matrix_id}")
flash('Tema criado com sucesso.', 'success')
return redirect(url_for('matrices.list_themes'))
67:     return render_template('matrices/themes.html', themes=themes, form=form)

69: @matrices_bp.route('/themes/<int:id>/edit', methods=['GET', 'POST'])

def edit_theme(id):
theme = Theme.query.get_or_404(id)
form = ThemeForm(obj=theme)
form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.all()]
75:     if form.validate_on_submit():

theme.name = form.name.data
theme.matrix_id = form.matrix_id.data
flash('O campo Tema é obrigatório para Descritores.', 'danger')
from app.audit_utils import log_audit
log_audit('UPDATE', 'Theme', theme.id, f"Editou o tema '{theme.name}'")








descriptor.type = form.type.data

























from app.utils.tenancy import filter_by_tenant
themes = filter_by_tenant(Theme.query, Theme).filter_by(matrix_id=matrix_id).all()
return jsonify([{'id': t.id, 'name': t.name} for t in themes])
119: # --- Descriptors CRUD (Linked to Matrices) ---

@matrices_bp.route('/descriptors', methods=['GET', 'POST'])
def list_descriptors():
from app.utils.tenancy import filter_by_tenant, get_tenant_id
# Filter by matrix if provided
matrix_id = request.args.get('matrix_id', type=int)
126:     query = filter_by_tenant(Descriptor.query, Descriptor)

if matrix_id:
query = query.filter_by(matrix_id=matrix_id)
130:     matrices = filter_by_tenant(ReferenceMatrix.query, ReferenceMatrix).all()
# Conditional Validation
132:     # Pagination
flash('O campo Tema é obrigatório para Descritores.', 'danger')
page = request.args.get('page', 1, type=int)
pagination = query.order_by(Descriptor.code).paginate(page=page, per_page=30)
descriptors = pagination.items
137:     # Form for adding new descriptor
description=form.description.data,
form = DescriptorForm()
form.matrix_id.choices = [(0, 'Selecione um item...')] + [(m.id, m.name) for m in matrices]
form.school_year_id.choices = [(0, 'Selecione um item...')] + [(y.id, y.name) for y in filter_by_tenant(SchoolYear.query, SchoolYear).all()]
form.subject_id.choices = [(0, 'Selecione um item...')] + [(s.id, s.name) for s in filter_by_tenant(Subject.query, Subject).all()]
form.theme_id.choices = [(0, 'Selecione um item...')] # Choices loaded via JS
144:     # Form for importing descriptors

import_form = ImportDescriptorForm()
147:     # Pre-select matrix in form if filtered
return redirect(url_for('matrices.list_descriptors', matrix_id=form.matrix_id.data))
if matrix_id:
form.matrix_id.data = matrix_id
151:     return render_template('matrices/descriptors.html', 

descriptors=descriptors, 
pagination=pagination,
matrices=matrices, 
current_matrix_id=matrix_id)
157: @matrices_bp.route('/descriptors/import', methods=['POST'])
current_matrix_id=matrix_id,
def import_descriptors():
from app.models import ImportJob
if ImportJob.is_any_running():
flash('Não é possível realizar importações enquanto houver outra em andamento. Por favor, aguarde a conclusão.', 'warning')
return redirect(url_for('matrices.list_descriptors'))
164:     form = ImportDescriptorForm()

166:     if form.validate_on_submit():

file = form.file.data
filename = secure_filename(file.filename)
170:         try:

if filename.endswith('.csv'):
df = pd.read_csv(file, sep=';', encoding='utf-8', dtype=str)
else:
df = pd.read_excel(file, dtype=str)
176:             # Validate columns

required_cols = ['Matriz de Referência', 'Tema', 'Ano Escolar', 'Disciplina', 'Código', 'Descrição']
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
flash(f'Arquivo inválido. Colunas ausentes: {", ".join(missing_cols)}', 'danger')
return redirect(url_for('matrices.list_descriptors'))
183:             # Pre-load lookups (Name -> ID)

matrices = {m.name: m.id for m in ReferenceMatrix.query.all()}
themes = {(t.name, t.matrix_id): t.id for t in Theme.quer







































continue
227:                 descriptor = Descriptor(

code=code,
description=desc_text,
matrix_id=matrix_id,
theme_id=theme_id,
school_year_id=year_id,
subject_id=subject_id
)
new_descriptors.append(descriptor)
237:             if errors:

# If any errors, abort and show all errors (up to 5 for brevity in flash)
for err in errors[:5]:
flash(err, 'danger')
if len(errors) > 5:
flash(f'E mais {len(errors) - 5} erros...', 'danger')
return redirect(url_for('matrices.list_descriptors'))
245:             # Bulk save

for d in new_descriptors:
db.session.add(d)
249:             db.session.commit()

flash(f'{len(new_descriptors)} descritores importados com sucesso!', 'success')
252:         except Exception as e:

db.session.rollback()
flash(f'Erro ao processar arquivo: {str(e)}', 'danger')
256:     else:

for field, errors in form.errors.items():
for error in errors:
flash(f'Erro no campo {field}: {error}', 'danger')
261:     return redirect(url_for('matrices.list_descriptors'))

263: @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])

def edit_descriptor(id):
descriptor = Descriptor.query.get_or_404(id)













else:
descriptor.type = form.type.data
descriptor.code = form.code.data
descriptor.description = form.description.data
descriptor.school_year_id = form.school_year_id.data
descriptor.subject_id = form.subject_id.data
descriptor.matrix_id = form.matrix_id.data
# Set Theme ID only if Descritor, else None
descriptor.theme_id = form.theme_id.data if (form.theme_id.data and form.theme_id.data != 0 and form.type.data == 'Descritor') else None
289:             db.session.commit()

flash('Item atualizado.', 'success')
return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
293:     return render_template('matrices/descriptor_edit.html', form=form, descriptor=descriptor)

295: @matrices_bp.route('/descriptors/<int:id>/delete', methods=['POST'])

def delete_descriptor(id):
descriptor = Descriptor.query.get_or_404(id)
matrix_id = descriptor.matrix_id
db.session.delete(descriptor)
db.session.commit()
flash('Excluído com sucesso', 'success_delete')
return redirect(url_for('matrices.list_descriptors', matrix_id=matrix_id))
304: @matrices_bp.route('/descriptors/<int:id>/toggle-active', methods=['POST'])

def toggle_descriptor_active(id):
descriptor = Descriptor.query.get_or_404(id)
descriptor.is_active = not descriptor.is_active
db.session.commit()
status = "ativado" if descriptor.is_active else "desativado"
flash(f"Descritor {descriptor.code} {status} com sucesso.", "success")
return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
The above content shows the entire, complete file contents of the requested file.

















file.save(filepath)
332:         # Create job

job = ImportJob(
user_id=current_user.id,
import_type='Descriptors',
filename=filename,
status='pending'
)
db.session.add(job)
db.session.commit()
342:         # Start background thread

thread = threading.Thread(target=_process_descriptors_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
thread.start()
346:         flash('A importação de descritores foi iniciada em segundo plano.', 'info')

348:     else:

for field, errors in form.errors.items():
for error in errors:
flash(f'Erro no campo {field}: {error}', 'danger')
353:     return redirect(url_for('matrices.list_descriptors'))ices.list_descriptors'))
filename=filename,
355: @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])
)
def edit_descriptor(id):
descriptor = Descriptor.query.get_or_404(id)
form = DescriptorForm(obj=descriptor)
form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.all()]
form.school_year_id.choices = [(y.id, y.name) for y in SchoolYear.query.all()]
form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
# Populate theme choices for edit
if descriptor.matrix_id:
form.theme_id.choices = [(t.id, t.name) for t in Theme.query.filter_by(matrix_id=descriptor.matrix_id).all()]
else:
for field, errors in form.errors.items():
for error in errors:
flash(f'Erro no campo {field}: {error}', 'danger')
370:     return redirect(url_for('matrices.list_descriptors'))

372: @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])

def edit_descriptor(id):
descriptor = Descriptor.query.get_or_404(id)
form = DescriptorForm(obj=descriptor)
form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.all()]
form.school_year_id.choices = [(y.id, y.name) for y in SchoolYear.query.all()]
form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
# Populate theme choices for edit
else:
for field, errors in form.errors.items():
for error in errors:
flash(f'Erro no campo {field}: {error}', 'danger')
385:     return redirect(url_for('matrices.list_descriptors'))

387: @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])

def edit_descriptor(id):
descriptor = Descriptor.query.get_or_404(id)
form = DescriptorForm(obj=descriptor)
form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.all()]
form.school_year_id.choices = [(y.id, y.name) for y in SchoolYear.query.all()]
form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
# Populate theme choices for edit
if descriptor.matrix_id:
form.theme_id.choices = [(t.id, t.name) for t in Theme.query.filter_by(matrix_id=descriptor.matrix_id).all()]
else:
form.theme_id.choices = [(0, 'Selecione um item...')]
400:     if form.validate_on_submit():
return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
if form.type.data == 'Descritor' and (not form.theme_id.data or form.theme_id.data == 0):
flash('O campo Tema é obrigatório para Descritores.', 'danger')
else:
descriptor.type = form.type.data
descriptor.code = form.code.data
descriptor.description = form.description.data
descriptor.school_year_id = form.school_year_id.data
descriptor.subject_id = form.subject_id.data
descri
flash('Excluído com sucesso', 'success_delete')
return redirect(url_for('matrices.list_descriptors', matrix_id=matrix_id))
413:             db.session.commit()

from app.audit_utils import log_audit
log_audit('UPDATE', 'Descriptor', descriptor.id, f"Editou o descritor/tópico {descriptor.code}")
flash('Item atualizado.', 'success')
return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
419:     return render_template('matrices/descriptor_edit.html', form=form, descriptor=descriptor)
flash(f"Descritor {descriptor.code} {status} com sucesso.", "success")
421: @matrices_bp.route('/descriptors/<int:id>/delete', methods=['POST'])
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
def delete_descriptor(id):
descriptor = Descriptor.query.get_or_404(id)
matrix_id = descriptor.matrix_id
d_id = descriptor.id
d_code = descriptor.code
db.session.delete(descriptor)
db.session.commit()
from app.audit_utils import log_audit
log_audit('DELETE', 'Descriptor', d_id, f"Excluiu o descritor/tópico {d_code}")
flash('Excluído com sucesso', 'success_delete')
return redirect(url_for('matrices.list_descriptors', matrix_id=matrix_id))
434: @matrices_bp.route('/descriptors/<int:id>/toggle-active', methods=['POST'])

def toggle_descriptor_active(id):
descriptor = Descriptor.query.get_or_404(id)
descriptor.is_active = not descriptor.is_active
db.session.commit()
from app.audit_utils import log_audit
status = "ativado" if descriptor.is_active else "desativado"
log_audit('UPDATE', 'Descriptor', descriptor.id, f"Alterou o status do descritor/tópico {descriptor.code} para {'Ativo' if descriptor.is_active else 'Inativo'}")
flash(f"Descritor {descriptor.code} {status} com sucesso.", "success")
return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
