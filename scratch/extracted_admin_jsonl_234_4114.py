Created At: 2026-05-29T16:59:51Z
Completed At: 2026-05-29T16:59:51Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 484
Total Bytes: 18803
Showing lines 179 to 320
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
179: def _process_dietary_restrictions_import(app, job_id, filepath, task_id=None):
180:     with app.app_context():
181:         import pandas as pd
182:         import json
183:         from datetime import datetime
184:         from app.models import DietaryRestriction
185:         from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task
186:         
187:         job = ImportJob.query.get(job_id)
188:         if not job: return
189: 
190:         try:
191:             job.status = 'running'
192:             job.started_at = datetime.utcnow()
193:             db.session.commit()
194: 
195:             df = pd.read_excel(filepath)
196:             total = len(df)
197:             job.total_rows = total
198:             db.session.commit()
199:             
200:             if task_id:
201:                 start_import_task(total, task_id=task_id)
202: 
203:             success_count = 0
204:             errors = []
205:             
206:             # For performance in mass inserts
207:             existing_names = {r.name.strip().lower() for r in DietaryRestriction.query.all()}
208:             
209:             # Using bulk insert approach if possible, but for simplicity and error tracking we iterate
210:             for index, row in df.iterrows():
211:                 # We assume the excel has a column 'Nome' or just read first column
212:                 col_name = 'Nome' if 'Nome' in df.columns else df.columns[0]
213:                 name = str(row.get(col_name, '')).strip()
214: 
215:  
<truncated 3010 bytes>
dex'))
278:         
279:     from app.forms import ImportDietaryRestrictionForm
280:     from werkzeug.utils import secure_filename
281:     from flask import current_app
282:     import os, threading
283:     
284:     if ImportJob.is_any_running():
285:         flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
286:         return redirect(url_for('admin.list_dietary_restrictions'))
287: 
288:     form = ImportDietaryRestrictionForm()
289:     if form.validate_on_submit():
290:         file = form.file.data
291:         filename = secure_filename(file.filename)
292:         task_id = request.form.get('X-Progress-ID')
293:         
294:         uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
295:         os.makedirs(uploads_dir, exist_ok=True)
296:         filepath = os.path.join(uploads_dir, filename)
297:         file.save(filepath)
298: 
299:         job = ImportJob(
300:             user_id=current_user.id,
301:             import_type='DietaryRestrictions',
302:             filename=filename,
303:             status='pending'
304:         )
305:         db.session.add(job)
306:         db.session.commit()
307: 
308:         thread = threading.Thread(target=_process_dietary_restrictions_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
309:         thread.start()
310: 
311:         flash('A importação foi iniciada em segundo plano.', 'info')
312:         
313:     return redirect(url_for('admin.list_dietary_restrictions'))
314: 
315: @admin_bp.route('/tenants')
316: @login_required
317: def list_tenants():
318:     if not current_user.is_system_admin:
319:         flash('Acesso restrito a administradores do sistema.', 'danger')
320:         return redirect(url_for('main.index'))
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
