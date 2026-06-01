Created At: 2026-05-28T20:30:40Z
Completed At: 2026-05-28T20:30:40Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 421
Total Bytes: 18642
Showing lines 350 to 421
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
350:         job = ImportJob(
351:             user_id=current_user.id,
352:             import_type='Descriptors',
353:             filename=filename,
354:             status='pending'
355:         )
356:         db.session.add(job)
357:         db.session.commit()
358: 
359:         # Start background thread
360:         thread = threading.Thread(target=_process_descriptors_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
361:         thread.start()
362: 
363:         flash('A importação de descritores foi iniciada em segundo plano.', 'info')
364:         
365:     else:
366:         for field, errors in form.errors.items():
367:             for error in errors:
368:                 flash(f'Erro no campo {field}: {error}', 'danger')
369: 
370:     return redirect(url_for('matrices.list_descriptors'))
371: 
372: @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])
373: def edit_descriptor(id):
374:     descriptor = Descriptor.query.get_or_404(id)
375:     form = DescriptorForm(obj=descriptor)
376:     form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.all()]
377:     form.school_year_id.choices = [(y.id, y.name) for y in SchoolYear.query.all()]
378:     form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
379:     # Populate theme choices for edit
380:     if descriptor.matrix_id:
381:         form.theme_id.choices = [(t.id, t.name) for t in Theme.query.filter_by(matrix_id=descriptor.matrix_id).all()]
382:     else:
383:         form.theme_id.choices = [(0,
<truncated 287 bytes>
89:             descriptor.type = form.type.data
390:             descriptor.code = form.code.data
391:             descriptor.description = form.description.data
392:             descriptor.school_year_id = form.school_year_id.data
393:             descriptor.subject_id = form.subject_id.data
394:             descriptor.matrix_id = form.matrix_id.data
395:             # Set Theme ID only if Descritor, else None
396:             descriptor.theme_id = form.theme_id.data if (form.theme_id.data and form.theme_id.data != 0 and form.type.data == 'Descritor') else None
397:             
398:             db.session.commit()
399:             flash('Item atualizado.', 'success')
400:             return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
401:         
402:     return render_template('matrices/descriptor_edit.html', form=form, descriptor=descriptor)
403: 
404: @matrices_bp.route('/descriptors/<int:id>/delete', methods=['POST'])
405: def delete_descriptor(id):
406:     descriptor = Descriptor.query.get_or_404(id)
407:     matrix_id = descriptor.matrix_id
408:     db.session.delete(descriptor)
409:     db.session.commit()
410:     flash('Excluído com sucesso', 'success_delete')
411:     return redirect(url_for('matrices.list_descriptors', matrix_id=matrix_id))
412: 
413: @matrices_bp.route('/descriptors/<int:id>/toggle-active', methods=['POST'])
414: def toggle_descriptor_active(id):
415:     descriptor = Descriptor.query.get_or_404(id)
416:     descriptor.is_active = not descriptor.is_active
417:     db.session.commit()
418:     status = "ativado" if descriptor.is_active else "desativado"
419:     flash(f"Descritor {descriptor.code} {status} com sucesso.", "success")
420:     return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
421: 
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
