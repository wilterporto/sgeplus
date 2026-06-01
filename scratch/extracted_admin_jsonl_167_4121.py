Created At: 2026-05-29T09:03:52Z
Completed At: 2026-05-29T09:03:52Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 364
Total Bytes: 14197
Showing lines 1 to 364
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
2: from flask_login import login_required, current_user
3: from app.models import ImportJob
4: from app import db
5: 
6: admin_bp = Blueprint('admin', __name__)
7: 
8: @admin_bp.route('/imports')
9: @login_required
10: def list_imports():
11:     if current_user.role != 'admin':
12:         flash('Acesso restrito a administradores.', 'danger')
13:         return redirect(url_for('main.index'))
14:     
15:     from app.models import Student
16:     from sqlalchemy import func
17:     
18:     jobs = ImportJob.query.order_by(ImportJob.created_at.desc()).limit(50).all()
19:     
20:     # Perfil do Aluno Stats
21:     # 1. Nationality stats
22:     nationality_stats = db.session.query(
23:         Student.nationality, func.count(Student.id)
24:     ).group_by(Student.nationality).all()
25:     
26:     br_count = 0
27:     foreign_count = 0
28:     for nat, count in nationality_stats:
29:         # Default to Brazilian if None, empty, or 'nan'
30:         if not nat or 'Brasileiro' in nat or nat.strip().lower() == 'nan':
31:             br_count += count
32:         else:
33:             foreign_count += count
34:             
35:     # 2. Top 5 countries for foreign students
36:     country_stats = db.session.query(
37:         Student.birth_country, func.count(Student.id)
38:     ).filter(
39:         Student.nationality.notilike('%Brasileiro%'),
40:         Student.birth_country != None,
41:         Student.birth_country.notilike('Brasil')
42:     ).gro
<truncated 12333 bytes>
   # Log de auditoria
323:             from app.routes.audit import log_audit
324:             log_audit('CREATE', 'Tenant', tenant.id, f"Cliente {tenant.name} criado do tipo {tenant.type}")
325:             
326:             flash('Cliente criado com sucesso.', 'success')
327:             return redirect(url_for('admin.list_tenants'))
328:         except Exception as e:
329:             db.session.rollback()
330:             flash(f'Erro ao criar cliente: {str(e)}', 'danger')
331:             
332:     return render_template('admin/tenant_form.html', form=form, title="Novo Cliente")
333: 
334: @admin_bp.route('/tenants/<int:id>/edit', methods=['GET', 'POST'])
335: @login_required
336: def edit_tenant(id):
337:     if not current_user.is_system_admin:
338:         flash('Acesso restrito a administradores do sistema.', 'danger')
339:         return redirect(url_for('main.index'))
340:         
341:     from app.models import Tenant
342:     from app.forms import TenantForm
343:     
344:     tenant = Tenant.query.get_or_404(id)
345:     form = TenantForm(obj=tenant)
346:     if form.validate_on_submit():
347:         tenant.name = form.name.data
348:         tenant.type = form.type.data
349:         try:
350:             db.session.commit()
351:             
352:             # Log de auditoria
353:             from app.routes.audit import log_audit
354:             log_audit('UPDATE', 'Tenant', tenant.id, f"Cliente {tenant.name} atualizado do tipo {tenant.type}")
355:             
356:             flash('Cliente atualizado com sucesso.', 'success')
357:             return redirect(url_for('admin.list_tenants'))
358:         except Exception as e:
359:             db.session.rollback()
360:             flash(f'Erro ao atualizar cliente: {str(e)}', 'danger')
361:             
362:     return render_template('admin/tenant_form.html', form=form, title="Editar Cliente", tenant=tenant)
363: 
364: 
The above content shows the entire, complete file contents of the requested file.
