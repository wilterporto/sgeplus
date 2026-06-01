Created At: 2026-05-29T16:58:51Z
Completed At: 2026-05-29T16:58:51Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 444
Total Bytes: 20331
Showing lines 10 to 80
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
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
37:         matrix.description = form.description.data
38:         db.session.commit()
39:         from app.audit_utils import log_audit
40:         log_audit('UPDATE', 'ReferenceMatrix', matrix.id, f"Editou a matriz de referência '{matrix.name}'")
41:         flash('Matriz atualizada.', 'success')
42:         return redirect(url_for('matrices.list_matrices'))
43:         
44:     return render_template('matrices/edit.html', form=form, matrix=matrix)
45: 
46:     return render_template('matrices/edit.html', form=form, matrix=matrix)
47: 
48: # --- Themes Management ---
49: @matrices_bp.route('/themes', methods=['GET', 'POST'])
50: def list_themes():
51:     themes = Theme.query.all()
52:     form = ThemeForm()
53:     form.matrix_id.choices = [(0, 'Selecione um item...')] + [(m.id, m.name) for m in ReferenceMatrix.query.all()]
54:     
55:     if form.validate_on_submit():
56:         if form.matrix_id.data == 0:
57:             flash('Selecione uma Matriz válida.', 'danger')
58:         else:
59:             theme = Theme(name=form.name.data, matrix_id=form.matrix_id.data)
60:             db.session.add(theme)
61:             db.session.commit()
62:             from app.audit_utils import log_audit
63:             log_audit('CREATE', 'Theme', theme.id, f"Criou o tema '{theme.name}' vinculado à matriz ID {theme.matrix_id}")
64:             flash('Tema criado com sucesso.', 'success')
65:             return redirect(url_for('matrices.list_themes'))
66:             
67:     return render_template('matrices/themes.html', themes=themes, form=form)
68: 
69: @matrices_bp.route('/themes/<int:id>/edit', methods=['GET', 'POST'])
70: def edit_theme(id):
71:     theme = Theme.query.get_or_404(id)
72:     form = ThemeForm(obj=theme)
73:     form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.all()]
74:     
75:     if form.validate_on_submit():
76:         theme.name = form.name.data
77:         theme.matrix_id = form.matrix_id.data
78:         db.session.commit()
79:         from app.audit_utils import log_audit
80:         log_audit('UPDATE', 'Theme', theme.id, f"Editou o tema '{theme.name}'")
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
