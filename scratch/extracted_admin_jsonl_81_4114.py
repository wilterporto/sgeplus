Created At: 2026-05-28T14:14:58Z
Completed At: 2026-05-28T14:14:58Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 285
Total Bytes: 11193
Showing lines 1 to 285
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
2: from flask_login import login_required, current_user
3: from app.models import ImportJob
4: from app import db
5: 
6: admin_bp = Blueprint('admin', __name__)
7: 
8: @admin_bp.route('/imports')
9: @login_required
10: def list_imports():
11:     if current_user.role != 'admin':
12:         flash('Acesso restrito a administradores.', 'danger')
13:         return redirect(url_for('main.index'))
14:     
15:     from app.models import Student
16:     from sqlalchemy import func
17:     
18:     jobs = ImportJob.query.order_by(ImportJob.created_at.desc()).limit(50).all()
19:     
20:     # Perfil do Aluno Stats
21:     # 1. Nationality stats
22:     nationality_stats = db.session.query(
23:         Student.nationality, func.count(Student.id)
24:     ).group_by(Student.nationality).all()
25:     
26:     br_count = 0
27:     foreign_count = 0
28:     for nat, count in nationality_stats:
29:         # Default to Brazilian if None, empty, or 'nan'
30:         if not nat or 'Brasileiro' in nat or nat.strip().lower() == 'nan':
31:             br_count += count
32:         else:
33:             foreign_count += count
34:             
35:     # 2. Top 5 countries for foreign students
36:     country_stats = db.session.query(
37:         Student.birth_country, func.count(Student.id)
38:     ).filter(
39:         Student.nationality.notilike('%Brasileiro%'),
40:         Student.birth_country != None,
41:         Student.birth_country.notilike('Brasil')
42:     ).gro
<truncated 8934 bytes>
  finally:
239:             import os
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
The above content shows the entire, complete file contents of the requested file.
