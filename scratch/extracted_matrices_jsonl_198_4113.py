Created At: 2026-05-29T16:59:00Z
Completed At: 2026-05-29T16:59:00Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 444
Total Bytes: 20331
Showing lines 380 to 444
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
380:     else:
381:         for field, errors in form.errors.items():
382:             for error in errors:
383:                 flash(f'Erro no campo {field}: {error}', 'danger')
384: 
385:     return redirect(url_for('matrices.list_descriptors'))
386: 
387: @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])
388: def edit_descriptor(id):
389:     descriptor = Descriptor.query.get_or_404(id)
390:     form = DescriptorForm(obj=descriptor)
391:     form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.all()]
392:     form.school_year_id.choices = [(y.id, y.name) for y in SchoolYear.query.all()]
393:     form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
394:     # Populate theme choices for edit
395:     if descriptor.matrix_id:
396:         form.theme_id.choices = [(t.id, t.name) for t in Theme.query.filter_by(matrix_id=descriptor.matrix_id).all()]
397:     else:
398:         form.theme_id.choices = [(0, 'Selecione um item...')]
399:     
400:     if form.validate_on_submit():
401:         if form.type.data == 'Descritor' and (not form.theme_id.data or form.theme_id.data == 0):
402:             flash('O campo Tema é obrigatório para Descritores.', 'danger')
403:         else:
404:             descriptor.type = form.type.data
405:             descriptor.code = form.code.data
406:             descriptor.description = form.description.data
407:             descriptor.school_year_id = form.school_year_id.data
408:             descriptor.subject_id = form.subject_id.data
409:             descri
<truncated 275 bytes>
13:             db.session.commit()
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
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
