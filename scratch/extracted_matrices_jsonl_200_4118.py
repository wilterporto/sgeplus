Created At: 2026-05-29T16:59:11Z
Completed At: 2026-05-29T16:59:12Z
The following changes were made by the multi_replace_file_content tool to: c:\Users\pc\source\sgeplus\app\routes\matrices.py. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -10,7 +10,8 @@
 # --- Matrices CRUD ---
 @matrices_bp.route('/', methods=['GET', 'POST'])
 def list_matrices():
-    matrices = ReferenceMatrix.query.all()
+    from app.utils.tenancy import filter_by_tenant, get_tenant_id
+    matrices = filter_by_tenant(ReferenceMatrix.query, ReferenceMatrix).all()
     form = ReferenceMatrixForm()
     
     if form.validate_on_submit():
@@ -17,5 +17,6 @@
             name=form.name.data,
-            description=form.description.data
+            description=form.description.data,
+            tenant_id=get_tenant_id()
         )
         db.session.add(matrix)
         db.session.commit()
@@ -28,6 +28,9 @@
 @matrices_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
 def edit_matrix(id):
     matrix = ReferenceMatrix.query.get_or_404(id)
+    if not current_user.is_system_admin and matrix.tenant_id != current_user.tenant_id:
+        flash('Acesso não autorizado.', 'danger')
+        return redirect(url_for('matrices.list_matrices'))
     form = ReferenceMatrixForm(obj=matrix)
     
     if form.validate_on_submit():
@@ -35,7 +35,7 @@
         db.session.commit()
         from app.audit_utils import log_audit
         log_audit('UPDATE', 'ReferenceMatrix', matrix.id, f"Editou a matriz de referência '{matrix.name}'")
-        flash('Matriz atualizada.', 'success')
+        flash('Matriz actualizada.', 'success')
         return redirect(url_for('matrices.list_matrices'))
         
     return render_template('matrices/edit.html', form=form, matrix=matrix)
@@ -44,9 +44,10 @@
 # --- Themes Management ---
 @matrices_bp.route('/themes', methods=['GET', 'POST'])
 def list_themes():
-    themes = Theme.query.all()
+    from
<truncated 3634 bytes>
.choices = [(0, 'Selecione um item...')] + [(s.id, s.name) for s in filter_by_tenant(Subject.query, Subject).all()]
     form.theme_id.choices = [(0, 'Selecione um item...')] # Choices loaded via JS
     
     # Form for importing descriptors
@@ -124,7 +124,7 @@
 
     # Validate custom logic: Theme choices need to be populated for validation to pass if we enforce choice
     if form.matrix_id.data:
-        themes = Theme.query.filter_by(matrix_id=form.matrix_id.data).all()
+        themes = filter_by_tenant(Theme.query, Theme).filter_by(matrix_id=form.matrix_id.data).all()
         form.theme_id.choices = [(0, 'Selecione um item...')] + [(t.id, t.name) for t in themes]
 
     if form.validate_on_submit():
@@ -138,7 +138,8 @@
                 school_year_id=form.school_year_id.data,
                 subject_id=form.subject_id.data,
                 matrix_id=form.matrix_id.data,
-                theme_id=form.theme_id.data if (form.theme_id.data and form.theme_id.data != 0 and form.type.data == 'Descritor') else None
+                theme_id=form.theme_id.data if (form.theme_id.data and form.theme_id.data != 0 and form.type.data == 'Descritor') else None,
+                tenant_id=get_tenant_id()
             )
 
             db.session.add(desc)
@@ -147,7 +147,7 @@
             flash('Item adicionado.', 'success')
             return redirect(url_for('matrices.list_descriptors', matrix_id=form.matrix_id.data))
 
-    active_job = ImportJob.query.filter_by(import_type='Descriptors', status='running').first()
+    active_job = filter_by_tenant(ImportJob.query, ImportJob).filter_by(import_type='Descriptors', status='running').first()
 
     return render_template('matrices/descriptors.html', 
                          descriptors=descriptors, 
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.