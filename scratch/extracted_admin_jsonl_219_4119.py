Created At: 2026-05-29T09:06:11Z
Completed At: 2026-05-29T09:06:11Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 393
Total Bytes: 15162
Showing lines 1 to 100
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, session, abort
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
41:         Student.birth_country.notilike('Brasil'
<truncated 599 bytes>
min
57:     if job.user_id != current_user.id and current_user.role != 'admin':
58:         return jsonify({'error': 'Unauthorized'}), 403
59:         
60:     return jsonify({
61:         'id': job.id,
62:         'status': job.status,
63:         'processed': job.processed_rows,
64:         'total': job.total_rows,
65:         'progress': job.progress_percentage,
66:         'finished': job.finished_at.strftime('%d/%m/%Y %H:%M') if job.finished_at else None,
67:         'errors': job.errors # JSON string
68:     })
69: 
70: # --- Dietary Restrictions ---
71: 
72: @admin_bp.route('/dietary-restrictions', methods=['GET', 'POST'])
73: @login_required
74: def list_dietary_restrictions():
75:     if current_user.role != 'admin':
76:         flash('Acesso restrito a administradores.', 'danger')
77:         return redirect(url_for('main.index'))
78:         
79:     from app.models import DietaryRestriction
80:     from app.forms import DietaryRestrictionForm, ImportDietaryRestrictionForm
81:     
82:     page = request.args.get('page', 1, type=int)
83:     search = request.args.get('search', '').strip()
84:     
85:     query = DietaryRestriction.query
86:     if search:
87:         query = query.filter(DietaryRestriction.name.ilike(f'%{search}%'))
88:         
89:     restrictions = query.order_by(DietaryRestriction.name).paginate(page=page, per_page=30)
90:     
91:     form = DietaryRestrictionForm()
92:     import_form = ImportDietaryRestrictionForm()
93:     
94:     active_job = ImportJob.query.filter_by(import_type='DietaryRestrictions', status='running').first()
95:     
96:     if form.validate_on_submit():
97:         restriction = DietaryRestriction(name=form.name.data, active=form.active.data)
98:         db.session.add(restriction)
99:         db.session.commit()
100:         
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
