from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import AnthropometricRecord, Student, Enrollment, Class, TeachingUnit
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from app import db
from sqlalchemy import func

nutrition_bp = Blueprint('nutrition', __name__)

@nutrition_bp.route('/nutrition/dashboard')
@login_required
def dashboard():
    # Subquery to get the latest date for each student
    subquery = db.session.query(
        AnthropometricRecord.student_id,
        func.max(AnthropometricRecord.date).label('max_date')
    ).group_by(AnthropometricRecord.student_id).subquery()

    drill_regional = request.args.get('drill_regional')
    drill_municipio = request.args.get('drill_municipio')

    # Query to count total students matching filters (independent of anthropometric records)
    student_query = db.session.query(func.count(Student.id)).filter(Student.tenant_id == get_tenant_id())
    
    RegionalUnit = db.aliased(TeachingUnit)
    SchoolUnit = db.aliased(TeachingUnit)
    
    if drill_regional or drill_municipio:
        student_query = student_query.outerjoin(Enrollment, (Enrollment.student_id == Student.id) & (Enrollment.active == True))\
                                     .outerjoin(Class, Enrollment.class_id == Class.id)\
                                     .outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id)\
                                     .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)
        if drill_regional:
            student_query = student_query.filter(RegionalUnit.name == drill_regional)
        if drill_municipio:
            student_query = student_query.filter(SchoolUnit.municipio == drill_municipio)
    
    # Base query joined with the subquery to get only the latest records
    query = db.session.query(
        AnthropometricRecord.student_id,
        AnthropometricRecord.date,
        Student.birth_date,
        Student.sex,
        AnthropometricRecord.nutritional_status,
        AnthropometricRecord.growth_status,
        func.coalesce(RegionalUnit.name, 'Sem Regional').label('regional_name'),
        func.coalesce(SchoolUnit.municipio, 'Sem Município').label('municipio_name'),
        func.coalesce(SchoolUnit.name, 'Sem Escola').label('school_name')
    ).join(
        subquery,
        (AnthropometricRecord.student_id == subquery.c.student_id) &
        (AnthropometricRecord.date == subquery.c.max_date)
    ).join(Student, AnthropometricRecord.student_id == Student.id)\
     .outerjoin(Enrollment, (Enrollment.student_id == Student.id) & (Enrollment.active == True))\
     .outerjoin(Class, Enrollment.class_id == Class.id)\
     .outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id)\
     .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)\
     .filter(
        AnthropometricRecord.tenant_id == get_tenant_id()
    )

    if drill_regional:
        query = query.filter(RegionalUnit.name == drill_regional)
    if drill_municipio:
        query = query.filter(SchoolUnit.municipio == drill_municipio)

    races = request.args.getlist('race')
    if races:
        query = query.filter(Student.race.in_(races))
        student_query = student_query.filter(Student.race.in_(races))
        
    nationalities = request.args.getlist('nationality')
    if nationalities:
        query = query.filter(Student.nationality.in_(nationalities))
        student_query = student_query.filter(Student.nationality.in_(nationalities))
        
    incomes = request.args.getlist('income')
    if incomes:
        query = query.filter(Student.family_income.in_(incomes))
        student_query = student_query.filter(Student.family_income.in_(incomes))
        
    zones = request.args.getlist('zone')
    if zones:
        query = query.filter(Student.residential_zone.in_(zones))
        student_query = student_query.filter(Student.residential_zone.in_(zones))
        
    locations = request.args.getlist('location')
    if locations:
        query = query.filter(Student.differentiated_location.in_(locations))
        student_query = student_query.filter(Student.differentiated_location.in_(locations))
        
    deficiencies = request.args.getlist('deficiency')
    if len(deficiencies) == 1:
        if deficiencies[0] == 'Sim':
            query = query.filter(Student.special_needs == True)
            student_query = student_query.filter(Student.special_needs == True)
        elif deficiencies[0] in ['Não', 'No', 'Nǜo']:
            query = query.filter(Student.special_needs == False)
            student_query = student_query.filter(Student.special_needs == False)
            
    bolsas = request.args.getlist('bolsa')
    if len(bolsas) == 1:
        if bolsas[0] == 'Sim':
            query = query.filter(Student.bolsa_familia == True)
            student_query = student_query.filter(Student.bolsa_familia == True)
        elif bolsas[0] in ['Não', 'No', 'Nǜo']:
            query = query.filter(Student.bolsa_familia == False)
            student_query = student_query.filter(Student.bolsa_familia == False)
            
    dietarys = request.args.getlist('dietary')
    if len(dietarys) == 1:
        if dietarys[0] == 'Sim':
            query = query.filter(Student.dietary_restrictions.any())
            student_query = student_query.filter(Student.dietary_restrictions.any())
        elif dietarys[0] in ['Não', 'No', 'Nǜo']:
            query = query.filter(~Student.dietary_restrictions.any())
            student_query = student_query.filter(~Student.dietary_restrictions.any())

    indigenous_ids = request.args.getlist('indigenous', type=int)
    if indigenous_ids:
        query = query.filter(Student.indigenous_people_id.in_(indigenous_ids))
        student_query = student_query.filter(Student.indigenous_people_id.in_(indigenous_ids))
        
    quilombola_vals = request.args.getlist('quilombola')
    if len(quilombola_vals) == 1:
        if quilombola_vals[0] == 'Sim':
            query = query.filter(Student.is_quilombola == True)
            student_query = student_query.filter(Student.is_quilombola == True)
        elif quilombola_vals[0] in ['Não', 'No', 'Nǜo']:
            query = query.filter(Student.is_quilombola == False)
            student_query = student_query.filter(Student.is_quilombola == False)

    quilombola_community_ids = request.args.getlist('quilombolaCommunity', type=int)
    if quilombola_community_ids:
        query = query.filter(Student.quilombola_community_id.in_(quilombola_community_ids))
        student_query = student_query.filter(Student.quilombola_community_id.in_(quilombola_community_ids))

    # Calculate total students matching filters
    total_students = student_query.scalar() or 0

    # Fetch lightweight tuples instead of full ORM objects
    results = query.all()
    
    # Deduplicate in case of multiple records on the same max_date
    latest_records = {}
    for row in results:
        latest_records[row[0]] = row
            
    total_aferidos = len(latest_records)
    
    stats = {
        'total': total_aferidos,
        'total_nao_aferidos': max(0, total_students - total_aferidos),
        'by_age_group': {'0-5': 0, '5-19': 0},
        'by_sex': {'M': 0, 'F': 0},
        'pct_age': {'0-5': 0, '5-19': 0},
        'pct_sex': {'M': 0, 'F': 0},
        'nutritional_status': {},
        'growth_status': {},
        'nutritional_by_age': {'0-5': {}, '5-19': {}},
        'nutritional_by_sex': {'M': {}, 'F': {}},
        'growth_by_age': {'0-5': {}, '5-19': {}},
        'growth_by_sex': {'M': {}, 'F': {}},
        'drill_down': {}
    }
    
    from dateutil.relativedelta import relativedelta
    for row_id, row in latest_records.items():
        student_id, rec_date, birth_date, sex, nutritional_status, growth_status, regional_name, municipio_name, school_name = row
        if not birth_date:
            continue
            
        # Age group
        age_years = relativedelta(rec_date, birth_date).years
        age_key = '0-5' if age_years <= 5 else '5-19'
        stats['by_age_group'][age_key] += 1
            
        # Sex
        sex_char = 'M' if sex and str(sex).lower().startswith('m') else 'F'
        stats['by_sex'][sex_char] += 1
        
        # Nutritional Status
        ns = nutritional_status or 'Não avaliado'
        stats['nutritional_status'][ns] = stats['nutritional_status'].get(ns, 0) + 1
        
        # Nutritional Status By Age
        stats['nutritional_by_age'][age_key][ns] = stats['nutritional_by_age'][age_key].get(ns, 0) + 1
        
        # Nutritional Status By Sex
        stats['nutritional_by_sex'][sex_char][ns] = stats['nutritional_by_sex'][sex_char].get(ns, 0) + 1
        
        # Growth Status
        gs = growth_status or 'Não avaliado'
        stats['growth_status'][gs] = stats['growth_status'].get(gs, 0) + 1
        
        # Growth Status By Age
        stats['growth_by_age'][age_key][gs] = stats['growth_by_age'][age_key].get(gs, 0) + 1
        
        # Growth Status By Sex
        stats['growth_by_sex'][sex_char][gs] = stats['growth_by_sex'][sex_char].get(gs, 0) + 1
        
        # Totals by Regional / Drill-down
        if drill_regional and drill_municipio:
            group_key = school_name
        elif drill_regional:
            group_key = municipio_name
        else:
            group_key = regional_name
            
        if group_key not in stats['drill_down']:
            stats['drill_down'][group_key] = {'0-5': 0, '5-19': 0, 'M': 0, 'F': 0, 'total': 0}
        stats['drill_down'][group_key][age_key] += 1
        stats['drill_down'][group_key][sex_char] += 1
        stats['drill_down'][group_key]['total'] += 1
        
    if stats['total'] > 0:
        stats['pct_age']['0-5'] = round((stats['by_age_group']['0-5'] / stats['total']) * 100, 1)
        stats['pct_age']['5-19'] = round((stats['by_age_group']['5-19'] / stats['total']) * 100, 1)
        stats['pct_sex']['M'] = round((stats['by_sex']['M'] / stats['total']) * 100, 1)
        stats['pct_sex']['F'] = round((stats['by_sex']['F'] / stats['total']) * 100, 1)

    from app.models import IndigenousPeople, QuilombolaCommunity
    if drill_regional or drill_municipio:
        student_query = student_query.outerjoin(Enrollment, (Enrollment.student_id == Student.id) & (Enrollment.active == True))\
                                     .outerjoin(Class, Enrollment.class_id == Class.id)\
                                     .outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id)\
                                     .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)
        if drill_regional:
            student_query = student_query.filter(RegionalUnit.name == drill_regional)
        if drill_municipio:
            student_query = student_query.filter(SchoolUnit.municipio == drill_municipio)
    
    # Base query joined with the subquery to get only the latest records
    query = db.session.query(
        AnthropometricRecord.student_id,
        AnthropometricRecord.date,
        Student.birth_date,
        Student.sex,
        AnthropometricRecord.nutritional_status,
        AnthropometricRecord.growth_status,
        func.coalesce(RegionalUnit.name, 'Sem Regional').label('regional_name'),
        func.coalesce(SchoolUnit.municipio, 'Sem Município').label('municipio_name'),
        func.coalesce(SchoolUnit.name, 'Sem Escola').label('school_name')
    ).join(
        subquery,
        (AnthropometricRecord.student_id == subquery.c.student_id) &
        (AnthropometricRecord.date == subquery.c.max_date)
    ).join(Student, AnthropometricRecord.student_id == Student.id)\
     .outerjoin(Enrollment, (Enrollment.student_id == Student.id) & (Enrollment.active == True))\
     .outerjoin(Class, Enrollment.class_id == Class.id)\
     .outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id)\
     .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)\
     .filter(
        AnthropometricRecord.tenant_id == get_tenant_id()
    )

    if drill_regional:
        query = query.filter(RegionalUnit.name == drill_regional)
    if drill_municipio:
        query = query.filter(SchoolUnit.municipio == drill_municipio)

    races = request.args.getlist('race')
    if races:
        query = query.filter(Student.race.in_(races))
        student_query = student_query.filter(Student.race.in_(races))
        
    nationalities = request.args.getlist('nationality')
    if nationalities:
        query = query.filter(Student.nationality.in_(nationalities))
        student_query = student_query.filter(Student.nationality.in_(nationalities))
        
    incomes = request.args.getlist('income')
    if incomes:
        query = query.filter(Student.family_income.in_(incomes))
        student_query = student_query.filter(Student.family_income.in_(incomes))
        
    zones = request.args.getlist('zone')
    if zones:
        query = query.filter(Student.residential_zone.in_(zones))
        student_query = student_query.filter(Student.residential_zone.in_(zones))
        
    locations = request.args.getlist('location')
    if locations:
        query = query.filter(Student.differentiated_location.in_(locations))
        student_query = student_query.filter(Student.differentiated_location.in_(locations))
        
    deficiencies = request.args.getlist('deficiency')
    if len(deficiencies) == 1:
        if deficiencies[0] == 'Sim':
            query = query.filter(Student.special_needs == True)
            student_query = student_query.filter(Student.special_needs == True)
        elif deficiencies[0] in ['Não', 'No', 'Nǜo']:
            query = query.filter(Student.special_needs == False)
            student_query = student_query.filter(Student.special_needs == False)
            
    bolsas = request.args.getlist('bolsa')
    if len(bolsas) == 1:
        if bolsas[0] == 'Sim':
            query = query.filter(Student.bolsa_familia == True)
            student_query = student_query.filter(Student.bolsa_familia == True)
        elif bolsas[0] in ['Não', 'No', 'Nǜo']:
            query = query.filter(Student.bolsa_familia == False)
            student_query = student_query.filter(Student.bolsa_familia == False)
            
    dietarys = request.args.getlist('dietary')
    if len(dietarys) == 1:
        if dietarys[0] == 'Sim':
            query = query.filter(Student.dietary_restrictions.any())
            student_query = student_query.filter(Student.dietary_restrictions.any())
        elif dietarys[0] in ['Não', 'No', 'Nǜo']:
            query = query.filter(~Student.dietary_restrictions.any())
            student_query = student_query.filter(~Student.dietary_restrictions.any())

    indigenous_ids = request.args.getlist('indigenous', type=int)
    if indigenous_ids:
        query = query.filter(Student.indigenous_people_id.in_(indigenous_ids))
        student_query = student_query.filter(Student.indigenous_people_id.in_(indigenous_ids))
        
    quilombola_vals = request.args.getlist('quilombola')
    if len(quilombola_vals) == 1:
        if quilombola_vals[0] == 'Sim':
            query = query.filter(Student.is_quilombola == True)
            student_query = student_query.filter(Student.is_quilombola == True)
        elif quilombola_vals[0] in ['Não', 'No', 'Nǜo']:
            query = query.filter(Student.is_quilombola == False)
            student_query = student_query.filter(Student.is_quilombola == False)

    quilombola_community_ids = request.args.getlist('quilombolaCommunity', type=int)
    if quilombola_community_ids:
        query = query.filter(Student.quilombola_community_id.in_(quilombola_community_ids))
        student_query = student_query.filter(Student.quilombola_community_id.in_(quilombola_community_ids))

    # Calculate total students matching filters
    total_students = student_query.scalar() or 0

    # Fetch lightweight tuples instead of full ORM objects
    results = query.all()
    
    # Deduplicate in case of multiple records on the same max_date
    latest_records = {}
    for row in results:
        latest_records[row[0]] = row
            
    total_aferidos = len(latest_records)
    
    stats = {
        'total': total_aferidos,
        'total_nao_aferidos': max(0, total_students - total_aferidos),
        'by_age_group': {'0-5': 0, '5-19': 0},
        'by_sex': {'M': 0, 'F': 0},
        'pct_age': {'0-5': 0, '5-19': 0},
        'pct_sex': {'M': 0, 'F': 0},
        'nutritional_status': {},
        'growth_status': {},
        'nutritional_by_age': {'0-5': {}, '5-19': {}},
        'nutritional_by_sex': {'M': {}, 'F': {}},
        'growth_by_age': {'0-5': {}, '5-19': {}},
        'growth_by_sex': {'M': {}, 'F': {}},
        'drill_down': {}
    }
    
    from dateutil.relativedelta import relativedelta
    for row_id, row in latest_records.items():
        student_id, rec_date, birth_date, sex, nutritional_status, growth_status, regional_name, municipio_name, school_name = row
        if not birth_date:
            continue
            
        # Age group
        age_years = relativedelta(rec_date, birth_date).years
        age_key = '0-5' if age_years <= 5 else '5-19'
        stats['by_age_group'][age_key] += 1
            
        # Sex
        sex_char = 'M' if sex and str(sex).lower().startswith('m') else 'F'
        stats['by_sex'][sex_char] += 1
        
        # Nutritional Status
        ns = nutritional_status or 'Não avaliado'
        stats['nutritional_status'][ns] = stats['nutritional_status'].get(ns, 0) + 1
        
        # Nutritional Status By Age
        stats['nutritional_by_age'][age_key][ns] = stats['nutritional_by_age'][age_key].get(ns, 0) + 1
        
        # Nutritional Status By Sex
        stats['nutritional_by_sex'][sex_char][ns] = stats['nutritional_by_sex'][sex_char].get(ns, 0) + 1
        
        # Growth Status
        gs = growth_status or 'Não avaliado'
        stats['growth_status'][gs] = stats['growth_status'].get(gs, 0) + 1
        
        # Growth Status By Age
        stats['growth_by_age'][age_key][gs] = stats['growth_by_age'][age_key].get(gs, 0) + 1
        
        # Growth Status By Sex
        stats['growth_by_sex'][sex_char][gs] = stats['growth_by_sex'][sex_char].get(gs, 0) + 1
        
        # Totals by Regional / Drill-down
        if drill_regional and drill_municipio:
            group_key = school_name
        elif drill_regional:
            group_key = municipio_name
        else:
            group_key = regional_name
            
        if group_key not in stats['drill_down']:
            stats['drill_down'][group_key] = {
                '0-5': 0, '5-19': 0, 'M': 0, 'F': 0, 'total': 0,
                'nutritional_by_age': {'0-5': {}, '5-19': {}}
            }
        stats['drill_down'][group_key][age_key] += 1
        stats['drill_down'][group_key][sex_char] += 1
        stats['drill_down'][group_key]['total'] += 1
        stats['drill_down'][group_key]['nutritional_by_age'][age_key][ns] = stats['drill_down'][group_key]['nutritional_by_age'][age_key].get(ns, 0) + 1
        
    if stats['total'] > 0:
        stats['pct_age']['0-5'] = round((stats['by_age_group']['0-5'] / stats['total']) * 100, 1)
        stats['pct_age']['5-19'] = round((stats['by_age_group']['5-19'] / stats['total']) * 100, 1)
        stats['pct_sex']['M'] = round((stats['by_sex']['M'] / stats['total']) * 100, 1)
        stats['pct_sex']['F'] = round((stats['by_sex']['F'] / stats['total']) * 100, 1)

    from app.models import IndigenousPeople, QuilombolaCommunity
    from app.utils.tenancy import filter_by_tenant
    indigenous_list = filter_by_tenant(IndigenousPeople.query, IndigenousPeople).all()
    quilombolas_list = filter_by_tenant(QuilombolaCommunity.query, QuilombolaCommunity).all()

    return render_template('nutrition/dashboard.html', stats=stats, indigenous=indigenous_list, quilombolas=quilombolas_list)

@nutrition_bp.route('/nutrition/export-risk-report')
@login_required
def export_risk_report():
    import pandas as pd
    import io
    from flask import send_file
    from app.models import Enrollment, Class, TeachingUnit, SchoolYear
    
    subquery = db.session.query(
        AnthropometricRecord.student_id,
        func.max(AnthropometricRecord.date).label('max_date')
    ).group_by(AnthropometricRecord.student_id).subquery()

    RegionalUnit = db.aliased(TeachingUnit)
    SchoolUnit = db.aliased(TeachingUnit)
    
    query = db.session.query(
        Student.name.label('student_name'),
        Student.registration_number.label('registration_number'),
        func.coalesce(RegionalUnit.name, 'Sem Regional').label('regional_name'),
        func.coalesce(SchoolUnit.municipio, 'Sem Município').label('municipio_name'),
        func.coalesce(SchoolUnit.name, 'Sem Escola').label('school_name'),
        func.coalesce(SchoolYear.name, 'Sem Ano').label('school_year_name'),
        func.coalesce(Class.name, 'Sem Turma').label('class_name'),
        func.coalesce(Class.shift, 'Sem Turno').label('class_shift'),
        AnthropometricRecord.nutritional_status.label('nutritional_status'),
        AnthropometricRecord.date.label('record_date'),
        Student.sex.label('sex'),
        Student.birth_date.label('birth_date')
    ).join(
        subquery,
        (AnthropometricRecord.student_id == subquery.c.student_id) &
        (AnthropometricRecord.date == subquery.c.max_date)
    ).join(Student, AnthropometricRecord.student_id == Student.id)\
     .outerjoin(Enrollment, (Enrollment.student_id == Student.id) & (Enrollment.active == True))\
     .outerjoin(Class, Enrollment.class_id == Class.id)\
     .outerjoin(SchoolYear, Class.school_year_id == SchoolYear.id)\
     .outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id)\
     .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)\
     .filter(
        AnthropometricRecord.tenant_id == get_tenant_id()
    )

    risk_conditions = ['Magreza', 'Magreza Acentuada', 'Obesidade', 'Obesidade Grave']
    query = query.filter(AnthropometricRecord.nutritional_status.in_(risk_conditions))

    drill_regional = request.args.get('drill_regional')
    drill_municipio = request.args.get('drill_municipio')

    if drill_regional:
        query = query.filter(RegionalUnit.name == drill_regional)
    if drill_municipio:
        query = query.filter(SchoolUnit.municipio == drill_municipio)

    races = request.args.getlist('race')
    if races: query = query.filter(Student.race.in_(races))
    nationalities = request.args.getlist('nationality')
    if nationalities: query = query.filter(Student.nationality.in_(nationalities))
    incomes = request.args.getlist('income')
    if incomes: query = query.filter(Student.family_income.in_(incomes))
    zones = request.args.getlist('zone')
    if zones: query = query.filter(Student.residential_zone.in_(zones))
    locations = request.args.getlist('location')
    if locations: query = query.filter(Student.differentiated_location.in_(locations))
    
    deficiencies = request.args.getlist('deficiency')
    if len(deficiencies) == 1:
        if deficiencies[0] == 'Sim': query = query.filter(Student.special_needs == True)
        elif deficiencies[0] in ['Não', 'No', 'Nǜo']: query = query.filter(Student.special_needs == False)
        
    bolsas = request.args.getlist('bolsa')
    if len(bolsas) == 1:
        if bolsas[0] == 'Sim': query = query.filter(Student.bolsa_familia == True)
        elif bolsas[0] in ['Não', 'No', 'Nǜo']: query = query.filter(Student.bolsa_familia == False)
        
    dietarys = request.args.getlist('dietary')
    if len(dietarys) == 1:
        if dietarys[0] == 'Sim': query = query.filter(Student.dietary_restrictions.any())
        elif dietarys[0] in ['Não', 'No', 'Nǜo']: query = query.filter(~Student.dietary_restrictions.any())
        
    indigenous_ids = request.args.getlist('indigenous', type=int)
    if indigenous_ids: query = query.filter(Student.indigenous_people_id.in_(indigenous_ids))
    
    quilombola_vals = request.args.getlist('quilombola')
    if len(quilombola_vals) == 1:
        if quilombola_vals[0] == 'Sim': query = query.filter(Student.is_quilombola == True)
        elif quilombola_vals[0] in ['Não', 'No', 'Nǜo']: query = query.filter(Student.is_quilombola == False)
        
    quilombola_community_ids = request.args.getlist('quilombolaCommunity', type=int)
    if quilombola_community_ids: query = query.filter(Student.quilombola_community_id.in_(quilombola_community_ids))

    results = query.all()
    
    from datetime import date
    from dateutil.relativedelta import relativedelta
    today = date.today()
    
    data = []
    seen = set()
    for row in results:
        if row.registration_number in seen:
            continue
        seen.add(row.registration_number)
        
        idade = ''
        if row.birth_date:
            idade = relativedelta(today, row.birth_date).years
            
        data.append({
            'Nome do Aluno': row.student_name,
            'Matrícula': row.registration_number,
            'Sexo': row.sex,
            'Idade': idade,
            'Regional': row.regional_name,
            'Município': row.municipio_name,
            'Escola': row.school_name,
            'Ano Escolar': row.school_year_name,
            'Turno': row.class_shift,
            'Turma': row.class_name,
            'Estado Nutricional': row.nutritional_status,
            'Data da Aferição': row.record_date.strftime('%d/%m/%Y') if row.record_date else ''
        })
        
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=['Nome do Aluno', 'Matrícula', 'Sexo', 'Idade', 'Regional', 'Município', 'Escola', 'Ano Escolar', 'Turno', 'Turma', 'Estado Nutricional', 'Data da Aferição'])
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Risco Nutricional')
        
    output.seek(0)
    return send_file(
        output,
        download_name='relatorio_risco_nutricional.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@nutrition_bp.route('/nutrition/export-unmeasured-report')
@login_required
def export_unmeasured_report():
    import pandas as pd
    import io
    from flask import send_file
    from app.models import Enrollment, Class, TeachingUnit, SchoolYear, Student, AnthropometricRecord
    
    RegionalUnit = db.aliased(TeachingUnit)
    SchoolUnit = db.aliased(TeachingUnit)
    
    query = db.session.query(
        func.coalesce(RegionalUnit.name, 'Sem Regional').label('regional_name'),
        func.coalesce(SchoolUnit.name, 'Sem Escola').label('school_name'),
        func.coalesce(SchoolYear.name, 'Sem Ano').label('school_year_name'),
        func.coalesce(Class.shift, 'Sem Turno').label('class_shift'),
        func.coalesce(Class.name, 'Sem Turma').label('class_name'),
        Student.name.label('student_name'),
        Student.birth_date.label('birth_date'),
        Student.sex.label('sex')
    ).outerjoin(AnthropometricRecord, Student.id == AnthropometricRecord.student_id)\
     .outerjoin(Enrollment, (Enrollment.student_id == Student.id) & (Enrollment.active == True))\
     .outerjoin(Class, Enrollment.class_id == Class.id)\
     .outerjoin(SchoolYear, Class.school_year_id == SchoolYear.id)\
     .outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id)\
     .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)\
     .filter(
        Student.tenant_id == get_tenant_id(),
        AnthropometricRecord.id == None
    )

    drill_regional = request.args.get('drill_regional')
    drill_municipio = request.args.get('drill_municipio')

    if drill_regional:
        query = query.filter(RegionalUnit.name == drill_regional)
    if drill_municipio:
        query = query.filter(SchoolUnit.municipio == drill_municipio)

    races = request.args.getlist('race')
    if races: query = query.filter(Student.race.in_(races))
    nationalities = request.args.getlist('nationality')
    if nationalities: query = query.filter(Student.nationality.in_(nationalities))
    incomes = request.args.getlist('income')
    if incomes: query = query.filter(Student.family_income.in_(incomes))
    zones = request.args.getlist('zone')
    if zones: query = query.filter(Student.residential_zone.in_(zones))
    locations = request.args.getlist('location')
    if locations: query = query.filter(Student.differentiated_location.in_(locations))
    
    deficiencies = request.args.getlist('deficiency')
    if len(deficiencies) == 1:
        if deficiencies[0] == 'Sim': query = query.filter(Student.special_needs == True)
        elif deficiencies[0] in ['Não', 'No', 'Nǜo']: query = query.filter(Student.special_needs == False)
        
    bolsas = request.args.getlist('bolsa')
    if len(bolsas) == 1:
        if bolsas[0] == 'Sim': query = query.filter(Student.bolsa_familia == True)
        elif bolsas[0] in ['Não', 'No', 'Nǜo']: query = query.filter(Student.bolsa_familia == False)
        
    dietarys = request.args.getlist('dietary')
    if len(dietarys) == 1:
        if dietarys[0] == 'Sim': query = query.filter(Student.dietary_restrictions.any())
        elif dietarys[0] in ['Não', 'No', 'Nǜo']: query = query.filter(~Student.dietary_restrictions.any())
        
    indigenous_ids = request.args.getlist('indigenous', type=int)
    if indigenous_ids: query = query.filter(Student.indigenous_people_id.in_(indigenous_ids))
    
    quilombola_vals = request.args.getlist('quilombola')
    if len(quilombola_vals) == 1:
        if quilombola_vals[0] == 'Sim': query = query.filter(Student.is_quilombola == True)
        elif quilombola_vals[0] in ['Não', 'No', 'Nǜo']: query = query.filter(Student.is_quilombola == False)
        
    quilombola_community_ids = request.args.getlist('quilombolaCommunity', type=int)
    if quilombola_community_ids: query = query.filter(Student.quilombola_community_id.in_(quilombola_community_ids))

    results = query.all()
    
    from datetime import date
    from dateutil.relativedelta import relativedelta
    today = date.today()
    
    data = []
    seen = set()
    for row in results:
        unique_key = f"{row.student_name}_{row.birth_date}"
        if unique_key in seen:
            continue
        seen.add(unique_key)
        
        idade = ''
        if row.birth_date:
            idade = relativedelta(today, row.birth_date).years
            
        data.append({
            'Regional': row.regional_name,
            'Escola': row.school_name,
            'Ano Escolar': row.school_year_name,
            'Turno': row.class_shift,
            'Turma': row.class_name,
            'Nome do Aluno': row.student_name,
            'Sexo': row.sex,
            'Data de Nascimento': row.birth_date.strftime('%d/%m/%Y') if row.birth_date else '',
            'Idade': idade
        })
        
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=['Regional', 'Escola', 'Ano Escolar', 'Turno', 'Turma', 'Nome do Aluno', 'Sexo', 'Data de Nascimento', 'Idade'])
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Não Aferidos')
        
    output.seek(0)
    return send_file(
        output,
        download_name='relatorio_alunos_nao_aferidos.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
