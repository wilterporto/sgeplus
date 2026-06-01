Created At: 2026-05-28T20:30:36Z
Completed At: 2026-05-28T20:30:36Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 421
Total Bytes: 18642
Showing lines 1 to 160
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
13:     matrices = ReferenceMatrix.query.all()
14:     form = ReferenceMatrixForm()
15:     
16:     if form.validate_on_submit():
17:         matrix = ReferenceMatrix(
18:             name=form.name.data,
19:             description=form.description.data
20:         )
21:         db.session.add(matrix)
22:         db.session.commit()
23:         flash('Matriz criada com sucesso!', 'success')
24:         return redirect(url_for('matrices.list_matrices'))
25:         
26:     return render_template('matrices/list.html', matrices=matrices, form=form)
27: 
28: @matrices_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
29: def edit_matrix(id):
30:     matrix = ReferenceMatrix.query.get_or_404(id)
31:     form = ReferenceMatrixForm(obj=matrix)
32:     
33:     if form.validate_on_submit():
34:         matrix.name = form.name.data
35:         matrix.description = form.description.data
36:         db.session.commit()
37:         flash('Matriz atualizada.', 'success')
38:         return redirect(url_for('matrices.list_matrices'))
39:  
<truncated 3906 bytes>
hemes = Theme.query.filter_by(matrix_id=form.matrix_id.data).all()
127:         form.theme_id.choices = [(0, 'Selecione um item...')] + [(t.id, t.name) for t in themes]
128: 
129:     if form.validate_on_submit():
130:         # Conditional Validation
131:         if form.type.data == 'Descritor' and (not form.theme_id.data or form.theme_id.data == 0):
132:             flash('O campo Tema é obrigatório para Descritores.', 'danger')
133:         else:
134:             desc = Descriptor(
135:                 code=form.code.data,
136:                 type=form.type.data,
137:                 description=form.description.data,
138:                 school_year_id=form.school_year_id.data,
139:                 subject_id=form.subject_id.data,
140:                 matrix_id=form.matrix_id.data,
141:                 theme_id=form.theme_id.data if (form.theme_id.data and form.theme_id.data != 0 and form.type.data == 'Descritor') else None
142:             )
143: 
144:             db.session.add(desc)
145:             db.session.commit()
146:             flash('Item adicionado.', 'success')
147:             return redirect(url_for('matrices.list_descriptors', matrix_id=form.matrix_id.data))
148: 
149:     active_job = ImportJob.query.filter_by(import_type='Descriptors', status='running').first()
150: 
151:     return render_template('matrices/descriptors.html', 
152:                          descriptors=descriptors, 
153:                          pagination=pagination,
154:                          matrices=matrices, 
155:                          form=form, 
156:                          import_form=import_form, 
157:                          current_matrix_id=matrix_id,
158:                          active_job=active_job)
159: 
160: def _process_descriptors_import(app, job_id, filepath, task_id=None):
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
