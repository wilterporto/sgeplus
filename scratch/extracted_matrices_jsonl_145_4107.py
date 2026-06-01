Created At: 2026-05-28T14:17:53Z
Completed At: 2026-05-28T14:17:54Z
The following changes were made by the replace_file_content tool to: c:\Users\pc\source\sgeplus\app\routes\matrices.py. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -152,107 +152,199 @@
                          matrices=matrices, 
                          form=form, 
                          import_form=import_form, 
-                         current_matrix_id=matrix_id)
-
-@matrices_bp.route('/descriptors/import', methods=['POST'])
-def import_descriptors():
-    from app.models import ImportJob
-    if ImportJob.is_any_running():
-        flash('Não é possível realizar importações enquanto houver outra em andamento. Por favor, aguarde a conclusão.', 'warning')
-        return redirect(url_for('matrices.list_descriptors'))
-
-    form = ImportDescriptorForm()
-    
-    if form.validate_on_submit():
-        file = form.file.data
-        filename = secure_filename(file.filename)
-        
+                         current_matrix_id=matrix_id)def _process_descriptors_import(app, job_id, filepath, task_id=None):
+    with app.app_context():
+        import pandas as pd
+        import json
+        import os
+        from datetime import datetime
+        from app.models import ReferenceMatrix, Theme, SchoolYear, Subject, Descriptor, ImportJob
+        from app import db
+        from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task
+        
+        job = ImportJob.query.get(job_id)
+        if not job: return
+
         try:
-            if filename.endswith('.csv'):
-                df = pd.read_csv(file, sep=';', encoding='utf-8', dtype=str)
+            job.status = 'running'
+            job.started_at = datetime.utcnow()
+            db.session.commit()
+
+            if filepath.endswith('.csv'):
+                df = pd.read_csv(filepath, sep=';', enco
<truncated 10039 bytes>
name
+    from flask import current_app
+    from flask_login import current_user
+    import os
+    import threading
+    
+    if ImportJob.is_any_running():
+        flash('Não é possível realizar importações enquanto houver outra em andamento. Por favor, aguarde a conclusão.', 'warning')
+        return redirect(url_for('matrices.list_descriptors'))
+
+    form = ImportDescriptorForm()
+    
+    if form.validate_on_submit():
+        file = form.file.data
+        filename = secure_filename(file.filename)
+        task_id = request.form.get('X-Progress-ID')
+        
+        # Save temp file
+        uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
+        os.makedirs(uploads_dir, exist_ok=True)
+        filepath = os.path.join(uploads_dir, filename)
+        file.save(filepath)
+
+        # Create job
+        job = ImportJob(
+            user_id=current_user.id,
+            import_type='Descriptors',
+            filename=filename,
+            status='pending'
+        )
+        db.session.add(job)
+        db.session.commit()
+
+        # Start background thread
+        thread = threading.Thread(target=_process_descriptors_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
+        thread.start()
+
+        flash('A importação de descritores foi iniciada em segundo plano.', 'info')
+        
     else:
         for field, errors in form.errors.items():
             for error in errors:
@@ -259,5 +259,5 @@
 
-    return redirect(url_for('matrices.list_descriptors'))
+    return redirect(url_for('matrices.list_descriptors'))ices.list_descriptors'))
 
 @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])
 def edit_descriptor(id):
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.