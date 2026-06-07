from flask import Blueprint, render_template, redirect, flash, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import AnthropometricRecord, Student, Class, SchoolYear, TeachingUnit, Enrollment
from app.forms import AnthropometricForm, AnthropometricBatchForm
from app.utils.anthropometry import process_anthropometric_data
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from datetime import datetime

anthropometry_bp = Blueprint('anthropometry', __name__)

@anthropometry_bp.route('/students/<int:student_id>/anthropometry', methods=['POST'])
@login_required
def add_record(student_id):
    student = Student.query.get_or_404(student_id)
    if student.tenant_id != get_tenant_id():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.index'))
        
    form = AnthropometricForm()
    if form.validate_on_submit():
        record = AnthropometricRecord(
            tenant_id=get_tenant_id(),
            student_id=student.id,
            date=form.date.data,
            weight=form.weight.data,
            height=form.height.data
        )
        process_anthropometric_data(record)
        db.session.add(record)
        db.session.commit()
        flash('Registro antropometrico adicionado com sucesso.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Erro no campo {getattr(form, field).label.text}: {error}', 'danger')
                
    return redirect(url_for('students.edit_student', id=student.id))

@anthropometry_bp.route('/anthropometry/<int:record_id>/delete', methods=['POST'])
@login_required
def delete_record(record_id):
    record = AnthropometricRecord.query.get_or_404(record_id)
    if record.tenant_id != get_tenant_id():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.index'))
        
    student_id = record.student_id
    db.session.delete(record)
    db.session.commit()
    flash('Registro apagado com sucesso.', 'success')
    return redirect(url_for('students.edit_student', id=student_id))

@anthropometry_bp.route('/anthropometry/batch', methods=['GET', 'POST'])
@login_required
def batch_entry():
    form = AnthropometricBatchForm()
    
    # Populate choices
    regionals = filter_by_tenant(TeachingUnit.query, TeachingUnit).filter_by(type='Regional').order_by(TeachingUnit.name).all()
    form.regional_id.choices = [(0, 'Selecione...')] + [(r.id, r.name) for r in regionals]
    
    # We will load units by JS, but if form is submitted, we need them valid
    units = filter_by_tenant(TeachingUnit.query, TeachingUnit).order_by(TeachingUnit.name).all()
    form.teaching_unit_id.choices = [(0, 'Selecione...')] + [(u.id, u.name) for u in units]
    
    # Class choices are usually loaded dynamically via JS, but we'll accept any valid class for the tenant
    classes = filter_by_tenant(Class.query, Class).all()
    form.class_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in classes]
    
    students = []
    selected_class = None
    
    if request.method == 'POST' and form.validate_on_submit():
        if form.class_id.data and form.class_id.data != 0:
            selected_class = Class.query.get(form.class_id.data)
            if selected_class and selected_class.tenant_id == get_tenant_id():
                # Get enrolled students
                enrollments = filter_by_tenant(Enrollment.query, Enrollment).filter_by(class_id=selected_class.id).all()
                students = [e.student for e in enrollments if e.student]
                
    return render_template('anthropometry/batch_entry.html', form=form, students=students, selected_class=selected_class, current_date=datetime.now().strftime('%Y-%m-%d'), now=datetime.now)

@anthropometry_bp.route('/anthropometry/batch/save', methods=['POST'])
@login_required
def batch_save():
    date_str = request.form.get('date')
    if not date_str:
        flash('A data da aferição é obrigatória.', 'danger')
        return redirect(url_for('anthropometry.batch_entry'))
        
    try:
        afericao_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Data inválida.', 'danger')
        return redirect(url_for('anthropometry.batch_entry'))
        
    saved_count = 0
    for key, value in request.form.items():
        if key.startswith('weight_'):
            student_id = key.split('_')[1]
            weight_val = value.strip()
            height_val = request.form.get(f'height_{student_id}', '').strip()
            
            if weight_val and height_val:
                try:
                    weight = float(weight_val.replace(',', '.'))
                    height = float(height_val.replace(',', '.'))
                    
                    # Verify student belongs to tenant
                    student = Student.query.get(int(student_id))
                    if student and student.tenant_id == get_tenant_id():
                        record = AnthropometricRecord(
                            tenant_id=get_tenant_id(),
                            student_id=student.id,
                            date=afericao_date,
                            weight=weight,
                            height=height
                        )
                        process_anthropometric_data(record)
                        db.session.add(record)
                        saved_count += 1
                except ValueError:
                    pass # ignore invalid numbers
                    
    if saved_count > 0:
        db.session.commit()
        flash(f'{saved_count} registros de antropometria salvos com sucesso.', 'success')
    else:
        flash('Nenhum dado válido para salvar. Preencha peso e altura corretamente.', 'warning')
        
    return redirect(url_for('anthropometry.batch_entry'))


import math

def calc_who_percentile(L, M, S, Z):
    if L == 0:
        return M * math.exp(Z * S)
    else:
        return M * math.pow(1 + Z * L * S, 1/L)

@anthropometry_bp.route('/student/<int:student_id>/report', methods=['GET'])
@login_required
def student_report(student_id):
    student = Student.query.get_or_404(student_id)
    
    # Restrict to active tenant
    from app.utils.tenancy import get_tenant_id
    from flask import abort
    if student.tenant_id != get_tenant_id():
        abort(403)
        
    records = student.anthropometric_records.order_by(AnthropometricRecord.date.asc()).all()
    
    # Percentiles: P3, P15, P50, P85, P97
    z_scores = [-1.881, -1.036, 0, 1.036, 1.881]
    
    chart_data = {
        'dates': [],
        'actual_weight': [],
        'actual_height': [],
        'actual_bmi': [],
        'who_weight': {'P3':[], 'P15':[], 'P50':[], 'P85':[], 'P97':[]},
        'who_height': {'P3':[], 'P15':[], 'P50':[], 'P85':[], 'P97':[]},
        'who_bmi': {'P3':[], 'P15':[], 'P50':[], 'P85':[], 'P97':[]}
    }
    
    radar_data = {
        'weight_pct': 0,
        'height_pct': 0,
        'bmi_pct': 0
    }
    
    latest_record = None
    latest_lms = None
    
    from app.models import WHOLmsData
    
    for r in records:
        date_str = r.date.strftime('%d/%m/%Y')
        chart_data['dates'].append(date_str)
        chart_data['actual_weight'].append(r.weight)
        chart_data['actual_height'].append(r.height)
        chart_data['actual_bmi'].append(r.bmi)
        
        # Calculate age in months exactly as in process_anthropometric_data
        days = (r.date - student.birth_date).days
        age_months = int(days / 30.4375)
        
        # We need WHO data for Weight, Height, BMI
        w_lms = WHOLmsData.query.filter_by(indicator='weight_for_age', sex=student.sex, age_months=age_months).first()
        h_lms = WHOLmsData.query.filter_by(indicator='height_for_age', sex=student.sex, age_months=age_months).first()
        b_lms = WHOLmsData.query.filter_by(indicator='bmi_for_age', sex=student.sex, age_months=age_months).first()
        
        latest_record = r
        latest_lms = {'w': w_lms, 'h': h_lms, 'b': b_lms}
        
        for z in z_scores:
            key = 'P50' if z == 0 else f'P{int(z*100) if z > 0 else int(z*100)}' # just arbitrary key names mapping, let\'s use explicit keys
            if z == -1.881: k = 'P3'
            elif z == -1.036: k = 'P15'
            elif z == 0: k = 'P50'
            elif z == 1.036: k = 'P85'
            elif z == 1.881: k = 'P97'
            
            chart_data['who_weight'][k].append(calc_who_percentile(w_lms.l, w_lms.m, w_lms.s, z) if w_lms else None)
            chart_data['who_height'][k].append(calc_who_percentile(h_lms.l, h_lms.m, h_lms.s, z) if h_lms else None)
            chart_data['who_bmi'][k].append(calc_who_percentile(b_lms.l, b_lms.m, b_lms.s, z) if b_lms else None)
            
    # Radar Data based on latest record vs P50
    if latest_record and latest_lms:
        if latest_lms['w']:
            radar_data['weight_pct'] = min(150, max(50, (latest_record.weight / latest_lms['w'].m) * 100))
        if latest_lms['h']:
            radar_data['height_pct'] = min(150, max(50, (latest_record.height / latest_lms['h'].m) * 100))
        if latest_lms['b']:
            radar_data['bmi_pct'] = min(150, max(50, (latest_record.bmi / latest_lms['b'].m) * 100))

    return render_template('anthropometry/student_report.html', student=student, records=records, chart_data=chart_data, radar_data=radar_data)


@anthropometry_bp.route('/api/units/<int:regional_id>', methods=['GET'])
@login_required
def get_units_by_regional(regional_id):
    units = filter_by_tenant(TeachingUnit.query, TeachingUnit).filter_by(parent_id=regional_id).order_by(TeachingUnit.name).all()
    return jsonify([{'id': u.id, 'name': u.name} for u in units])

@anthropometry_bp.route('/api/classes/<int:unit_id>', methods=['GET'])
@login_required
def get_classes_by_unit(unit_id):
    classes = filter_by_tenant(Class.query, Class).filter_by(teaching_unit_id=unit_id).order_by(Class.name).all()
    return jsonify([{'id': c.id, 'name': c.name} for c in classes])
