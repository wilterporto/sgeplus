Created At: 2026-05-29T09:54:52Z
Completed At: 2026-05-29T09:54:52Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/admin.py`
Total Lines: 423
Total Bytes: 16343
Showing lines 1 to 423
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, session, abort
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
41:         Student.birth_country.notilike('Brasil'
<truncated 14774 bytes>
bj=tenant)
376:     if form.validate_on_submit():
377:         tenant.name = form.name.data
378:         tenant.type = form.type.data
379:         try:
380:             db.session.commit()
381:             
382:             # Log de auditoria
383:             from app.routes.audit import log_audit
384:             log_audit('UPDATE', 'Tenant', tenant.id, f"Cliente {tenant.name} atualizado do tipo {tenant.type}")
385:             
386:             flash('Cliente atualizado com sucesso.', 'success')
387:             return redirect(url_for('admin.list_tenants'))
388:         except Exception as e:
389:             db.session.rollback()
390:             flash(f'Erro ao atualizar cliente: {str(e)}', 'danger')
391:             
392:     return render_template('admin/tenant_form.html', form=form, title="Editar Cliente", tenant=tenant)
393: 
394: @admin_bp.route('/tenants/<int:id>/authenticate', methods=['GET'])
395: @login_required
396: def authenticate_tenant(id):
397:     if not current_user.is_system_admin:
398:         abort(403)
399:         
400:     from app.models import Tenant
401:     tenant = Tenant.query.get_or_404(id)
402:     
403:     session['active_tenant_id'] = tenant.id
404:     session['active_tenant_name'] = tenant.name
405:     
406:     flash(f'Autenticado com sucesso no cliente: {tenant.name}', 'success')
407:     
408:     # Redireciona para o dashboard
409:     return redirect(url_for('reports.dashboard'))
410: 
411: @admin_bp.route('/tenants/deauthenticate', methods=['GET'])
412: @login_required
413: def deauthenticate_tenant():
414:     if not current_user.is_system_admin:
415:         abort(403)
416:         
417:     tenant_name = session.pop('active_tenant_name', 'Cliente')
418:     session.pop('active_tenant_id', None)
419:     
420:     flash(f'Conexão encerrada com: {tenant_name}', 'info')
421:     return redirect(url_for('admin.list_tenants'))
422: 
423: 
The above content shows the entire, complete file contents of the requested file.
