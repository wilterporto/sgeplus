Created At: 2026-05-29T10:02:46Z
Completed At: 2026-05-29T10:02:46Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 423
Total Bytes: 16343
Showing lines 130 to 285
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
130:         
131:         flash('Restrição Alimentar criada com sucesso.', 'success')
132:         return redirect(url_for('admin.list_dietary_restrictions'))
133:         
134:     return render_template('admin/dietary_restrictions.html', restrictions=restrictions, form=form, import_form=import_form, search=search, active_job=active_job)
135: 
136: @admin_bp.route('/dietary-restrictions/<int:id>/edit', methods=['POST'])
137: @login_required
138: def edit_dietary_restriction(id):
139:     if current_user.role != 'admin':
140:         return redirect(url_for('main.index'))
141:         
142:     from app.models import DietaryRestriction
143:     restriction = DietaryRestriction.query.get_or_404(id)
144:     
145:     # We get data from form directly as it might be from a modal
146:     name = request.form.get('name')
147:     active = request.form.get('active') == 'on'
148:     if name:
149:         restriction.name = name
150:         restriction.active = active
151:         db.session.commit()
152:         flash('Restrição Alimentar atualizada com sucesso.', 'success')
153:     else:
154:         flash('Erro ao atualizar: Nome é obrigatório.', 'danger')
155:         
156:     return redirect(url_for('admin.list_dietary_restrictions'))
157: 
158: @admin_bp.route('/dietary-restrictions/<int:id>/delete', methods=['POST'])
159: @login_required
160: def delete_dietary_restriction(id):
161:     if current_user.role != 'admin':
162:         return redirect(url_for('main.index'))
163:         
164:     from app.models import DietaryRestriction
165:
<truncated 3761 bytes>
Exception as e:
243:                         db.session.rollback()
244:                         errors.append(f"Erro ao comitar lote: {str(e)}")
245: 
246:             try:
247:                 db.session.commit()
248:             except Exception as e:
249:                 db.session.rollback()
250:                 errors.append(f"Erro ao salvar registros: {str(e)}")
251: 
252:             job.status = 'completed'
253:             job.finished_at = datetime.utcnow()
254:             job.errors = json.dumps(errors)
255:             db.session.commit()
256:             
257:             if task_id:
258:                 finish_import_task(task_id, message=f"Importação concluída: {success_count} registros.", log_file=None)
259: 
260:         except Exception as e:
261:             job.status = 'failed'
262:             job.errors = json.dumps([f"Erro crítico: {str(e)}"])
263:             job.finished_at = datetime.utcnow()
264:             db.session.commit()
265:             
266:             if task_id:
267:                 fail_import_task(task_id, f"Erro crítico: {str(e)}")
268:         finally:
269:             import os
270:             if os.path.exists(filepath):
271:                 os.remove(filepath)
272: 
273: @admin_bp.route('/dietary-restrictions/import', methods=['POST'])
274: @login_required
275: def import_dietary_restrictions():
276:     if current_user.role != 'admin':
277:         return redirect(url_for('main.index'))
278:         
279:     from app.forms import ImportDietaryRestrictionForm
280:     from werkzeug.utils import secure_filename
281:     from flask import current_app
282:     import os, threading
283:     
284:     if ImportJob.is_any_running():
285:         flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
