Created At: 2026-05-29T10:02:44Z
Completed At: 2026-05-29T10:02:44Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 423
Total Bytes: 16343
Showing lines 50 to 120
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
50:     return render_template('admin/imports.html', jobs=jobs, stats=stats)
51: 
52: @admin_bp.route('/imports/status/<int:id>')
53: @login_required
54: def get_import_status(id):
55:     job = ImportJob.query.get_or_404(id)
56:     # Only allow own jobs or admin
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
70: @admin_bp.route('/imports/<int:id>/cancel', methods=['POST'])
71: @login_required
72: def cancel_import(id):
73:     if current_user.role != 'admin':
74:         flash('Acesso restrito a administradores.', 'danger')
75:         return redirect(url_for('main.index'))
76:         
77:     import json
78:     from app.models import ImportJob
79:     job = ImportJob.query.get_or_404(id)
80:     
81:     if job.status in ['pending', 'running']:
82:         job.status = 'failed'
83:         errors_list = json.loads(job.errors) if job.errors else []
84:         errors_list.append("Importação cancelada pelo administrador.")
85:         job.errors = json.dumps(errors_list)
86:         from datetime import datetime
87:         job.finished_at = datetime.utcnow()
88:         db.session.commit()
89:         
90:         # Log de auditoria
91:         from app.routes.audit import log_audit
92:         log_audit('UPDATE', 'ImportJob', job.id, f"Importação {job.filename} cancelada manualmente pelo administrador.")
93:         
94:         flash('Importação cancelada com sucesso.', 'success')
95:     else:
96:         flash('Esta importação já foi concluída ou falhou.', 'warning')
97:         
98:     return redirect(url_for('admin.list_imports'))
99: 
100: # --- Dietary Restrictions ---
101: 
102: @admin_bp.route('/dietary-restrictions', methods=['GET', 'POST'])
103: @login_required
104: def list_dietary_restrictions():
105:     if current_user.role != 'admin':
106:         flash('Acesso restrito a administradores.', 'danger')
107:         return redirect(url_for('main.index'))
108:         
109:     from app.models import DietaryRestriction
110:     from app.forms import DietaryRestrictionForm, ImportDietaryRestrictionForm
111:     
112:     page = request.args.get('page', 1, type=int)
113:     search = request.args.get('search', '').strip()
114:     
115:     query = DietaryRestriction.query
116:     if search:
117:         query = query.filter(DietaryRestriction.name.ilike(f'%{search}%'))
118:         
119:     restrictions = query.order_by(DietaryRestriction.name).paginate(page=page, per_page=30)
120:     
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
