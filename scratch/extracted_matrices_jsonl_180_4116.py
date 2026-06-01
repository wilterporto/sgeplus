Created At: 2026-05-29T16:57:42Z
Completed At: 2026-05-29T16:57:42Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 444
Total Bytes: 20331
Showing lines 1 to 444
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
23:         from app.audit_utils import log_audit
24:         log_audit('CREATE', 'ReferenceMatrix', matrix.id, f"Criou a matriz de referência '{matrix.name}'")
25:         flash('Matriz criada com sucesso!', 'success')
26:         return redirect(url_for('matrices.list_matrices'))
27:         
28:     return render_template('matrices/list.html', matrices=matrices, form=form)
29: 
30: @matrices_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
31: def edit_matrix(id):
32:     matrix = ReferenceMatrix.query.get_or_404(id)
33:     form = ReferenceMatrixForm(obj=matrix)
34:     
35:     if form.validate_on_submit():
36:         matrix.name = form.name.data
37:         matrix.description = form.descript
<truncated 18870 bytes>
e_id.data and form.theme_id.data != 0 and form.type.data == 'Descritor') else None
412:             
413:             db.session.commit()
414:             from app.audit_utils import log_audit
415:             log_audit('UPDATE', 'Descriptor', descriptor.id, f"Editou o descritor/tópico {descriptor.code}")
416:             flash('Item atualizado.', 'success')
417:             return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
418:         
419:     return render_template('matrices/descriptor_edit.html', form=form, descriptor=descriptor)
420: 
421: @matrices_bp.route('/descriptors/<int:id>/delete', methods=['POST'])
422: def delete_descriptor(id):
423:     descriptor = Descriptor.query.get_or_404(id)
424:     matrix_id = descriptor.matrix_id
425:     d_id = descriptor.id
426:     d_code = descriptor.code
427:     db.session.delete(descriptor)
428:     db.session.commit()
429:     from app.audit_utils import log_audit
430:     log_audit('DELETE', 'Descriptor', d_id, f"Excluiu o descritor/tópico {d_code}")
431:     flash('Excluído com sucesso', 'success_delete')
432:     return redirect(url_for('matrices.list_descriptors', matrix_id=matrix_id))
433: 
434: @matrices_bp.route('/descriptors/<int:id>/toggle-active', methods=['POST'])
435: def toggle_descriptor_active(id):
436:     descriptor = Descriptor.query.get_or_404(id)
437:     descriptor.is_active = not descriptor.is_active
438:     db.session.commit()
439:     from app.audit_utils import log_audit
440:     status = "ativado" if descriptor.is_active else "desativado"
441:     log_audit('UPDATE', 'Descriptor', descriptor.id, f"Alterou o status do descritor/tópico {descriptor.code} para {'Ativo' if descriptor.is_active else 'Inativo'}")
442:     flash(f"Descritor {descriptor.code} {status} com sucesso.", "success")
443:     return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
444: 
The above content shows the entire, complete file contents of the requested file.
