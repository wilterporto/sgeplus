Created At: 2026-05-29T01:22:38Z
Completed At: 2026-05-29T01:22:38Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 285
Total Bytes: 11193
Showing lines 240 to 285
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
240:             if os.path.exists(filepath):
241:                 os.remove(filepath)
242: 
243: @admin_bp.route('/dietary-restrictions/import', methods=['POST'])
244: @login_required
245: def import_dietary_restrictions():
246:     if current_user.role != 'admin':
247:         return redirect(url_for('main.index'))
248:         
249:     from app.forms import ImportDietaryRestrictionForm
250:     from werkzeug.utils import secure_filename
251:     from flask import current_app
252:     import os, threading
253:     
254:     if ImportJob.is_any_running():
255:         flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
256:         return redirect(url_for('admin.list_dietary_restrictions'))
257: 
258:     form = ImportDietaryRestrictionForm()
259:     if form.validate_on_submit():
260:         file = form.file.data
261:         filename = secure_filename(file.filename)
262:         task_id = request.form.get('X-Progress-ID')
263:         
264:         uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
265:         os.makedirs(uploads_dir, exist_ok=True)
266:         filepath = os.path.join(uploads_dir, filename)
267:         file.save(filepath)
268: 
269:         job = ImportJob(
270:             user_id=current_user.id,
271:             import_type='DietaryRestrictions',
272:             filename=filename,
273:             status='pending'
274:         )
275:         db.session.add(job)
276:         db.session.commit()
277: 
278:         thread = threading.Thread(target=_process_dietary_restrictions_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
279:         thread.start()
280: 
281:         flash('A importação foi iniciada em segundo plano.', 'info')
282:         
283:     return redirect(url_for('admin.list_dietary_restrictions'))
284: 
285: 
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
