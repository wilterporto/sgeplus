Created At: 2026-05-28T14:14:20Z
Completed At: 2026-05-28T14:14:20Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 312
Total Bytes: 13806
Showing lines 1 to 312
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: from flask import Blueprint, render_template, redirect, url_for, flash, request
2: from app import db
3: from app.models import ReferenceMatrix, Descriptor, SchoolYear, Subject, Theme
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
40
<truncated 11685 bytes>
78:             flash('O campo Tema é obrigatório para Descritores.', 'danger')
279:         else:
280:             descriptor.type = form.type.data
281:             descriptor.code = form.code.data
282:             descriptor.description = form.description.data
283:             descriptor.school_year_id = form.school_year_id.data
284:             descriptor.subject_id = form.subject_id.data
285:             descriptor.matrix_id = form.matrix_id.data
286:             # Set Theme ID only if Descritor, else None
287:             descriptor.theme_id = form.theme_id.data if (form.theme_id.data and form.theme_id.data != 0 and form.type.data == 'Descritor') else None
288:             
289:             db.session.commit()
290:             flash('Item atualizado.', 'success')
291:             return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
292:         
293:     return render_template('matrices/descriptor_edit.html', form=form, descriptor=descriptor)
294: 
295: @matrices_bp.route('/descriptors/<int:id>/delete', methods=['POST'])
296: def delete_descriptor(id):
297:     descriptor = Descriptor.query.get_or_404(id)
298:     matrix_id = descriptor.matrix_id
299:     db.session.delete(descriptor)
300:     db.session.commit()
301:     flash('Excluído com sucesso', 'success_delete')
302:     return redirect(url_for('matrices.list_descriptors', matrix_id=matrix_id))
303: 
304: @matrices_bp.route('/descriptors/<int:id>/toggle-active', methods=['POST'])
305: def toggle_descriptor_active(id):
306:     descriptor = Descriptor.query.get_or_404(id)
307:     descriptor.is_active = not descriptor.is_active
308:     db.session.commit()
309:     status = "ativado" if descriptor.is_active else "desativado"
310:     flash(f"Descritor {descriptor.code} {status} com sucesso.", "success")
311:     return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
312: 
The above content shows the entire, complete file contents of the requested file.
