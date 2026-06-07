from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import AnthropometricRecord, Student
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from app import db
from sqlalchemy import func

nutrition_bp = Blueprint('nutrition', __name__)

@nutrition_bp.route('/nutrition/dashboard')
@login_required
def dashboard():
    # Filter by tenant
    query = db.session.query(AnthropometricRecord).join(Student).filter(
        AnthropometricRecord.tenant_id == get_tenant_id()
    )

    races = request.args.getlist('race')
    if races:
        query = query.filter(Student.race.in_(races))
        
    nationalities = request.args.getlist('nationality')
    if nationalities:
        query = query.filter(Student.nationality.in_(nationalities))
        
    incomes = request.args.getlist('income')
    if incomes:
        query = query.filter(Student.family_income.in_(incomes))
        
    zones = request.args.getlist('zone')
    if zones:
        query = query.filter(Student.residential_zone.in_(zones))
        
    locations = request.args.getlist('location')
    if locations:
        query = query.filter(Student.differentiated_location.in_(locations))
        
    deficiencies = request.args.getlist('deficiency')
    if len(deficiencies) == 1:
        if deficiencies[0] == 'Sim':
            query = query.filter(Student.special_needs == True)
        elif deficiencies[0] == 'Não' or deficiencies[0] == 'Não':
            query = query.filter(Student.special_needs == False)
            
    bolsas = request.args.getlist('bolsa')
    if len(bolsas) == 1:
        if bolsas[0] == 'Sim':
            query = query.filter(Student.bolsa_familia == True)
        elif bolsas[0] == 'Não' or bolsas[0] == 'Não':
            query = query.filter(Student.bolsa_familia == False)
            
    dietarys = request.args.getlist('dietary')
    if len(dietarys) == 1:
        if dietarys[0] == 'Sim':
            query = query.filter(Student.dietary_restrictions.any())
        elif dietarys[0] == 'Não' or dietarys[0] == 'Não':
            query = query.filter(~Student.dietary_restrictions.any())

    

    indigenous_ids = request.args.getlist('indigenous', type=int)
    if indigenous_ids:
        query = query.filter(Student.indigenous_people_id.in_(indigenous_ids))
        
    quilombola_vals = request.args.getlist('quilombola')
    if len(quilombola_vals) == 1:
        if quilombola_vals[0] == 'Sim':
            query = query.filter(Student.is_quilombola == True)
        elif quilombola_vals[0] == 'Nǜo' or quilombola_vals[0] == 'No' or quilombola_vals[0] == 'Não':
            query = query.filter(Student.is_quilombola == False)

    quilombola_community_ids = request.args.getlist('quilombolaCommunity', type=int)
    if quilombola_community_ids:
        query = query.filter(Student.quilombola_community_id.in_(quilombola_community_ids))

    # Simple analytics (can be optimized later using subqueries to get only the latest record per student)
    # Let's fetch all and process in python for simplicity since datasets aren't huge
    records = query.all()
    
    # We want ONLY the latest record for each student for the dashboard stats
    latest_records = {}
    for r in records:
        if r.student_id not in latest_records or r.date > latest_records[r.student_id].date:
            latest_records[r.student_id] = r
            
    stats = {
        'total': len(latest_records),
        'by_age_group': {'0-5': 0, '5-19': 0},
        'by_sex': {'M': 0, 'F': 0},
        'nutritional_status': {},
        'growth_status': {}
    }
    
    for r in latest_records.values():
        if not r.student or not r.student.birth_date:
            continue
            
        # Age group
        from dateutil.relativedelta import relativedelta
        age_years = relativedelta(r.date, r.student.birth_date).years
        if age_years <= 5:
            stats['by_age_group']['0-5'] += 1
        else:
            stats['by_age_group']['5-19'] += 1
            
        # Sex
        sex_char = 'M' if r.student.sex and str(r.student.sex).lower().startswith('m') else 'F'
        stats['by_sex'][sex_char] += 1
        
        # Nutritional Status
        ns = r.nutritional_status or 'N/A'
        stats['nutritional_status'][ns] = stats['nutritional_status'].get(ns, 0) + 1
        
        # Growth Status
        gs = r.growth_status or 'N/A'
        stats['growth_status'][gs] = stats['growth_status'].get(gs, 0) + 1

    from app.models import IndigenousPeople, QuilombolaCommunity
    from app.utils.tenancy import filter_by_tenant
    indigenous_list = filter_by_tenant(IndigenousPeople.query, IndigenousPeople).all()
    quilombolas_list = filter_by_tenant(QuilombolaCommunity.query, QuilombolaCommunity).all()

    return render_template('nutrition/dashboard.html', stats=stats, indigenous=indigenous_list, quilombolas=quilombolas_list)
