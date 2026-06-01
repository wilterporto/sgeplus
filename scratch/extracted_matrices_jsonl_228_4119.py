Created At: 2026-05-29T16:59:43Z
Completed At: 2026-05-29T16:59:43Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 460
Total Bytes: 21676
Showing lines 1 to 149
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: from flask import Blueprint, render_template, redirect, url_for, flash, request
2: from app import db
3: from app.models import ReferenceMatrix, Descriptor, SchoolYear, Subject, Theme, ImportJob
4: from app.forms import ReferenceMatrixForm, DescriptorForm, ImportDescriptorForm, ThemeForm
5: import pandas as pd
6: from werkzeug.utils import secure_filename
7: 
8: matrices_bp = Blueprint('matrices', __name__)
9: 
10: # --- Matrices CRUD ---
11: @matrices_bp.route('/', methods=['GET', 'POST'])
12: def list_matrices():
13:     from app.utils.tenancy import filter_by_tenant, get_tenant_id
14:     matrices = filter_by_tenant(ReferenceMatrix.query, ReferenceMatrix).all()
15:     form = ReferenceMatrixForm()
16:     
17:     if form.validate_on_submit():
18:         matrix = ReferenceMatrix(
19:             name=form.name.data,
20:             description=form.description.data,
21:             tenant_id=get_tenant_id()
22:         )
23:         db.session.add(matrix)
24:         db.session.commit()
25:         from app.audit_utils import log_audit
26:         log_audit('CREATE', 'ReferenceMatrix', matrix.id, f"Criou a matriz de referência '{matrix.name}'")
27:         flash('Matriz criada com sucesso!', 'success')
28:         return redirect(url_for('matrices.list_matrices'))
29:         
30:     return render_template('matrices/list.html', matrices=matrices, form=form)
31: 
32: @matrices_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
33: def edit_matrix(id):
34:     matrix = ReferenceMatrix.query.get_or_404(id)
35:     if not current_user.is_syst
<truncated 4033 bytes>
et_themes_by_matrix(matrix_id):
115:     from app.utils.tenancy import filter_by_tenant
116:     themes = filter_by_tenant(Theme.query, Theme).filter_by(matrix_id=matrix_id).all()
117:     return jsonify([{'id': t.id, 'name': t.name} for t in themes])
118: 
119: # --- Descriptors CRUD (Linked to Matrices) ---
120: @matrices_bp.route('/descriptors', methods=['GET', 'POST'])
121: def list_descriptors():
122:     from app.utils.tenancy import filter_by_tenant, get_tenant_id
123:     # Filter by matrix if provided
124:     matrix_id = request.args.get('matrix_id', type=int)
125:     
126:     query = filter_by_tenant(Descriptor.query, Descriptor)
127:     if matrix_id:
128:         query = query.filter_by(matrix_id=matrix_id)
129:         
130:     matrices = filter_by_tenant(ReferenceMatrix.query, ReferenceMatrix).all()
131:     
132:     # Pagination
133:     page = request.args.get('page', 1, type=int)
134:     pagination = query.order_by(Descriptor.code).paginate(page=page, per_page=30)
135:     descriptors = pagination.items
136:     
137:     # Form for adding new descriptor
138:     form = DescriptorForm()
139:     form.matrix_id.choices = [(0, 'Selecione um item...')] + [(m.id, m.name) for m in matrices]
140:     form.school_year_id.choices = [(0, 'Selecione um item...')] + [(y.id, y.name) for y in filter_by_tenant(SchoolYear.query, SchoolYear).all()]
141:     form.subject_id.choices = [(0, 'Selecione um item...')] + [(s.id, s.name) for s in filter_by_tenant(Subject.query, Subject).all()]
142:     form.theme_id.choices = [(0, 'Selecione um item...')] # Choices loaded via JS
143:     
144:     # Form for importing descriptors
145:     import_form = ImportDescriptorForm()
146: 
147:     # Pre-select matrix in form if filtered
148:     if matrix_id:
149:         form.matrix_id.data = matrix_id
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
