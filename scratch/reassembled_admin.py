from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from app.models import ImportJob
from app import db
6: admin_bp = Blueprint('admin', __name__)

8: @admin_bp.route('/imports')

@login_required
def list_imports():
if current_user.role != 'admin':
flash('Acesso restrito a administradores.', 'danger')
return redirect(url_for('main.index'))
15:     from app.models import Student

from sqlalchemy import func
18:     jobs = ImportJob.query.order_by(ImportJob.created_at.desc()).limit(50).all()

20:     # Perfil do Aluno Stats

# 1. Nationality stats
nationality_stats = db.session.query(
Student.nationality, func.count(Student.id)
).group_by(Student.nationality).all()
26:     br_count = 0

foreign_count = 0
for nat, count in nationality_stats:
# Default to Brazilian if None, empty, or 'nan'
if not nat or 'Brasileiro' in nat or nat.strip().lower() == 'nan':
br_count += count
else:
foreign_count += count
35:     # 2. Top 5 countries for foreign students

country_stats = db.session.query(
Student.birth_country, func.count(Student.id)
).filter(
Student.nationality.notilike('%Brasileiro%'),
Student.birth_country != None,
Student.birth_country.notilike('Brasil')
).gro
44:     stats = {

'br_count': br_count,
'foreign_count': foreign_count,
'countries': [{'name': c[0] or 'Não informado', 'count': c[1]} for c in country_stats]
}
50:     return render_template('admin/imports.html', jobs=jobs, stats=stats)
return render_template('admin/imports.html', jobs=jobs, stats=stats)
52: @admin_bp.route('/imports/status/<int:id>')

@login_required
def get_import_status(id):
job = ImportJob.query.get_or_404(id)
# Only allow own jobs or admin
if job.user_id != current_user.id and current_user.role != 'admin':
return jsonify({'error': 'Unauthorized'}), 403
60:     return jsonify({

'id': job.id,
'status': job.status,
'processed': job.processed_rows,
'total': job.total_rows,
'progress': job.progress_percentage,
'finished': job.finished_at.strftime('%d/%m/%Y %H:%M') if job.finished_at else None,
'errors': job.errors # JSON string
})
70: @admin_bp.route('/imports/<int:id>/cancel', methods=['POST'])

@login_required
def cancel_import(id):
if current_user.role != 'admin':
flash('Acesso restrito a administradores.', 'danger')
return redirect(url_for('main.index'))
77:     import json
return redirect(url_for('main.index'))
from app.models import ImportJob
job = ImportJob.query.get_or_404(id)
81:     if job.status in ['pending', 'running']:
82:     page = request.args.get('page', 1, type=int)
job.status = 'failed'
errors_list = json.loads(job.errors) if job.errors else []
errors_list.append("Importação cancelada pelo administrador.")
job.errors = json.dumps(errors_list)
from datetime import datetime
job.finished_at = datetime.utcnow()
db.session.commit()
90:         # Log de auditoria
91:     form = DietaryRestrictionForm()
from app.routes.audit import log_audit
log_audit('UPDATE', 'ImportJob', job.id, f"Importação {job.filename} cancelada manualmente pelo administrador.")
94:         flash('Importação cancelada com sucesso.', 'success')

else:
flash('Esta importação já foi concluída ou falhou.', 'warning')
98:     return redirect(url_for('admin.list_imports'))
db.session.add(restriction)
100: # --- Dietary Restrictions ---
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
102: @admin_bp.route('/dietary-restrictions', methods=['GET', 'POST'])

@login_required
def list_dietary_restrictions():
if current_user.role != 'admin':
flash('Acesso restrito a administradores.', 'danger')
return redirect(url_for('main.index'))
109:     from app.models import DietaryRestriction

from app.forms import DietaryRestrictionForm, ImportDietaryRestrictionForm
112:     page = request.args.get('page', 1, type=int)

search = request.args.get('search', '').strip()
115:     query = DietaryRestriction.query

if search:
query = query.filter(DietaryRestriction.name.ilike(f'%{search}%'))
119:     restrictions = query.order_by(DietaryRestriction.name).paginate(page=page, per_page=30)

The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.









131:         flash('Restrição Alimentar criada com sucesso.', 'success')

return redirect(url_for('admin.list_dietary_restrictions'))
134:     return render_template('admin/dietary_restrictions.html', restrictions=restrictions, form=form, import_form=import_form, search=search, active_job=active_job)

136: @admin_bp.route('/dietary-restrictions/<int:id>/edit', methods=['POST'])

@login_required
def edit_dietary_restriction(id):
if current_user.role != 'admin':
return redirect(url_for('main.index'))
142:     from app.models import DietaryRestriction

restriction = DietaryRestriction.query.get_or_404(id)
145:     # We get data from form directly as it might be from a modal

name = request.form.get('name')
active = request.form.get('active') == 'on'
if name:
restriction.name = name
restriction.active = active
db.session.commit()
flash('Restrição Alimentar atualizada com sucesso.', 'success')
else:
flash('Erro ao atualizar: Nome é obrigatório.', 'danger')
156:     return redirect(url_for('admin.list_dietary_restrictions'))

158: @admin_bp.route('/dietary-restrictions/<int:id>/delete', methods=['POST'])

@login_required
def delete_dietary_restriction(id):
if current_user.role != 'admin':
return redirect(url_for('main.index'))
164:     from app.models import DietaryRestriction

<truncated 3761 bytes>
name = restriction.name
168:     # Check if there are students linked to this restriction

if restriction.students:
flash(f'Erro: Não é possível excluir a restrição "{name}" pois existem alunos vinculados.', 'danger')
return redirect(url_for('admin.list_dietary_restrictions'))
173:     db.session.delete(restriction)

db.session.commit()
176:     flash('Excluído com sucesso', 'success_delete')

return redirect(url_for('admin.list_dietary_restrictions'))
179: def _process_dietary_restrictions_import(app, job_id, filepath, task_id=None):
def _process_dietary_restrictions_import(app, job_id, filepath, task_id=None):
with app.app_context():
import pandas as pd
import json
from datetime import datetime
from app.models import DietaryRestriction
from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task
187:         job = ImportJob.query.get(job_id)

if not job: return
190:         try:

job.status = 'running'
job.started_at = datetime.utcnow()
db.session.commit()
195:             df = pd.read_excel(filepath)

total = len(df)
job.total_rows = total
db.session.commit()
200:             if task_id:

start_import_task(total, task_id=task_id)
203:             success_count = 0

errors = []
206:             # For performance in mass inserts

existing_names = {r.name.strip().lower() for r in DietaryRestriction.query.all()}
209:             # Using bulk insert approach if possible, but for simplicity and error tracking we iterate

for index, row in df.iterrows():
# We assume the excel has a column 'Nome' or just read first column
col_name = 'Nome' if 'Nome' in df.columns else df.columns[0]
name = str(row.get(col_name, '')).strip()
215:  
























import os
if os.path.exists(filepath):
os.remove(filepath)
243: @admin_bp.route('/dietary-restrictions/import', methods=['POST'])
db.session.rollback()
@login_required
def import_dietary_restrictions():
if current_user.role != 'admin':
return redirect(url_for('main.index'))
249:     from app.forms import ImportDietaryRestrictionForm
db.session.rollback()
from werkzeug.utils import secure_filename
from flask import current_app
import os, threading
254:     if ImportJob.is_any_running():
job.errors = json.dumps(errors)
flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
return redirect(url_for('admin.list_dietary_restrictions'))
258:     form = ImportDietaryRestrictionForm()
finish_import_task(task_id, message=f"Importação concluída: {success_count} registros.", log_file=None)
if form.validate_on_submit():
file = form.file.data
filename = secure_filename(file.filename)
task_id = request.form.get('X-Progress-ID')
264:         uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
db.session.commit()
os.makedirs(uploads_dir, exist_ok=True)
filepath = os.path.join(uploads_dir, filename)
file.save(filepath)
269:         job = ImportJob(
import os
user_id=current_user.id,
import_type='DietaryRestrictions',
filename=filename,
status='pending'
)
db.session.add(job)
db.session.commit()
278:         thread = threading.Thread(target=_process_dietary_restrictions_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
279:     from app.forms import ImportDietaryRestrictionForm
thread.start()
281:         flash('A importação foi iniciada em segundo plano.', 'info')
from flask import current_app
283:     return redirect(url_for('admin.list_dietary_restrictions'))
284:     if ImportJob.is_any_running():
285: 
flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
return redirect(url_for('admin.list_dietary_restrictions'))
288:     form = ImportDietaryRestrictionForm()

if form.validate_on_submit():
file = form.file.data
filename = secure_filename(file.filename)
task_id = request.form.get('X-Progress-ID')
294:         uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')

os.makedirs(uploads_dir, exist_ok=True)
filepath = os.path.join(uploads_dir, filename)
file.save(filepath)
299:         job = ImportJob(

user_id=current_user.id,
import_type='DietaryRestrictions',
filename=filename,
status='pending'
)
db.session.add(job)
db.session.commit()
308:         thread = threading.Thread(target=_process_dietary_restrictions_import, args=(current_app._get_current_object(), job.id, filepath, task_id))

thread.start()
311:         flash('A importação foi iniciada em segundo plano.', 'info')

313:     return redirect(url_for('admin.list_dietary_restrictions'))

315: @admin_bp.route('/tenants')

@login_required
def list_tenants():
if not current_user.is_system_admin:
flash('Acesso restrito a administradores do sistema.', 'danger')
return redirect(url_for('main.index'))


from app.routes.audit import log_audit
log_audit('CREATE', 'Tenant', tenant.id, f"Cliente {tenant.name} criado do tipo {tenant.type}")
326:             flash('Cliente criado com sucesso.', 'success')

return redirect(url_for('admin.list_tenants'))
except Exception as e:
db.session.rollback()
flash(f'Erro ao criar cliente: {str(e)}', 'danger')
332:     return render_template('admin/tenant_form.html', form=form, title="Novo Cliente")

334: @admin_bp.route('/tenants/<int:id>/edit', methods=['GET', 'POST'])

@login_required
def edit_tenant(id):
if not current_user.is_system_admin:
flash('Acesso restrito a administradores do sistema.', 'danger')
return redirect(url_for('main.index'))
341:     from app.models import Tenant

from app.forms import TenantForm
344:     tenant = Tenant.query.get_or_404(id)

form = TenantForm(obj=tenant)
if form.validate_on_submit():
tenant.name = form.name.data
tenant.type = form.type.data
try:
db.session.commit()
352:             # Log de auditoria

from app.routes.audit import log_audit
log_audit('UPDATE', 'Tenant', tenant.id, f"Cliente {tenant.name} atualizado do tipo {tenant.type}")
356:             flash('Cliente atualizado com sucesso.', 'success')

return redirect(url_for('admin.list_tenants'))
except Exception as e:
db.session.rollback()
flash(f'Erro ao atualizar cliente: {str(e)}', 'danger')
362:     return render_template('admin/tenant_form.html', form=form, title="Editar Cliente", tenant=tenant)

364: 












if form.validate_on_submit():
tenant.name = form.name.data
tenant.type = form.type.data
try:
db.session.commit()
382:             # Log de auditoria

from app.routes.audit import log_audit
log_audit('UPDATE', 'Tenant', tenant.id, f"Cliente {tenant.name} atualizado do tipo {tenant.type}")
386:             flash('Cliente atualizado com sucesso.', 'success')

return redirect(url_for('admin.list_tenants'))
except Exception as e:
db.session.rollback()
flash(f'Erro ao atualizar cliente: {str(e)}', 'danger')
392:     return render_template('admin/tenant_form.html', form=form, title="Editar Cliente", tenant=tenant)

394: @admin_bp.route('/tenants/<int:id>/authenticate', methods=['GET'])

@login_required
def authenticate_tenant(id):
if not current_user.is_system_admin:
abort(403)
400:     from app.models import Tenant

tenant = Tenant.query.get_or_404(id)
403:     session['active_tenant_id'] = tenant.id

session['active_tenant_name'] = tenant.name
406:     flash(f'Autenticado com sucesso no cliente: {tenant.name}', 'success')

408:     # Redireciona para o dashboard

return redirect(url_for('reports.dashboard'))
411: @admin_bp.route('/tenants/deauthenticate', methods=['GET'])

@login_required
def deauthenticate_tenant():
if not current_user.is_system_admin:
abort(403)
417:     tenant_name = session.pop('active_tenant_name', 'Cliente')

session.pop('active_tenant_id', None)
420:     flash(f'Conexão encerrada com: {tenant_name}', 'info')

return redirect(url_for('admin.list_tenants'))
423: 
