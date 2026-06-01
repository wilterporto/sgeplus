Created At: 2026-05-29T16:59:46Z
Completed At: 2026-05-29T16:59:46Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 484
Total Bytes: 18803
Showing lines 1 to 180
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
<truncated 4277 bytes>
     if current_user.role != 'admin':
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
165:     restriction = DietaryRestriction.query.get_or_404(id)
166:     name = restriction.name
167:     
168:     # Check if there are students linked to this restriction
169:     if restriction.students:
170:         flash(f'Erro: Não é possível excluir a restrição "{name}" pois existem alunos vinculados.', 'danger')
171:         return redirect(url_for('admin.list_dietary_restrictions'))
172:         
173:     db.session.delete(restriction)
174:     db.session.commit()
175:     
176:     flash('Excluído com sucesso', 'success_delete')
177:     return redirect(url_for('admin.list_dietary_restrictions'))
178: 
179: def _process_dietary_restrictions_import(app, job_id, filepath, task_id=None):
180:     with app.app_context():
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
