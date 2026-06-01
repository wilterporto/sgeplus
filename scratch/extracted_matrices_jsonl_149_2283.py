Created At: 2026-05-28T14:18:02Z
Completed At: 2026-05-28T14:18:02Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 404
Total Bytes: 17831
Showing lines 330 to 365
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
330:         file.save(filepath)
331: 
332:         # Create job
333:         job = ImportJob(
334:             user_id=current_user.id,
335:             import_type='Descriptors',
336:             filename=filename,
337:             status='pending'
338:         )
339:         db.session.add(job)
340:         db.session.commit()
341: 
342:         # Start background thread
343:         thread = threading.Thread(target=_process_descriptors_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
344:         thread.start()
345: 
346:         flash('A importação de descritores foi iniciada em segundo plano.', 'info')
347:         
348:     else:
349:         for field, errors in form.errors.items():
350:             for error in errors:
351:                 flash(f'Erro no campo {field}: {error}', 'danger')
352: 
353:     return redirect(url_for('matrices.list_descriptors'))ices.list_descriptors'))
354: 
355: @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])
356: def edit_descriptor(id):
357:     descriptor = Descriptor.query.get_or_404(id)
358:     form = DescriptorForm(obj=descriptor)
359:     form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.all()]
360:     form.school_year_id.choices = [(y.id, y.name) for y in SchoolYear.query.all()]
361:     form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
362:     # Populate theme choices for edit
363:     if descriptor.matrix_id:
364:         form.theme_id.choices = [(t.id, t.name) for t in Theme.query.filter_by(matrix_id=descriptor.matrix_id).all()]
365:     else:
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
