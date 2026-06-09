import re

filepath = r'c:\Users\pc\source\sgeplus\app\routes\academic.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# I want to insert the base query setup after `drill_municipio = request.args.get('drill_municipio')`
base_setup = """
    # Helper base queries to support Drill Down filtering
    RegionalUnit = db.aliased(TeachingUnit)
    SchoolUnit = db.aliased(TeachingUnit)

    base_student_q = db.session.query(Student)
    base_prof_q = db.session.query(Professor)
    base_class_q = db.session.query(Class)
    base_school_q = db.session.query(SchoolUnit).filter_by(type='Escola')

    if drill_regional or drill_municipio:
        # Join path for students
        base_student_q = base_student_q.outerjoin(Enrollment, (Enrollment.student_id == Student.id) & (Enrollment.active == True)) \\
                                       .outerjoin(Class, Enrollment.class_id == Class.id) \\
                                       .outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id) \\
                                       .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)
        
        # Join path for professors (through TeachingAssignment -> Class -> SchoolUnit -> RegionalUnit)
        base_prof_q = base_prof_q.outerjoin(TeachingAssignment, TeachingAssignment.professor_id == Professor.id) \\
                                 .outerjoin(Class, TeachingAssignment.class_id == Class.id) \\
                                 .outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id) \\
                                 .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)
                                 
        # Join path for classes
        base_class_q = base_class_q.outerjoin(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id) \\
                                   .outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)
                                   
        # Join path for schools
        base_school_q = base_school_q.outerjoin(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id)

        if drill_regional:
            base_student_q = base_student_q.filter(RegionalUnit.name == drill_regional)
            base_prof_q = base_prof_q.filter(RegionalUnit.name == drill_regional)
            base_class_q = base_class_q.filter(RegionalUnit.name == drill_regional)
            base_school_q = base_school_q.filter(RegionalUnit.name == drill_regional)
            
        if drill_municipio:
            base_student_q = base_student_q.filter(SchoolUnit.municipio == drill_municipio)
            base_prof_q = base_prof_q.filter(SchoolUnit.municipio == drill_municipio)
            base_class_q = base_class_q.filter(SchoolUnit.municipio == drill_municipio)
            base_school_q = base_school_q.filter(SchoolUnit.municipio == drill_municipio)
"""

if "# Helper base queries" not in content:
    # We find where drill_municipio is defined.
    # It was defined around line 1747 after we added it.
    insert_point = "    drill_municipio = request.args.get('drill_municipio')"
    content = content.replace(insert_point, insert_point + "\n" + base_setup)

# Now we replace the simple query references with our base queries
replacements = {
    "total_schools = filter_by_tenant(TeachingUnit.query.filter_by(type='Escola'), TeachingUnit).count()": "total_schools = filter_by_tenant(base_school_q, SchoolUnit).with_entities(func.count(func.distinct(SchoolUnit.id))).scalar() or 0",
    "total_classes = filter_by_tenant(Class.query, Class).count()": "total_classes = filter_by_tenant(base_class_q, Class).with_entities(func.count(func.distinct(Class.id))).scalar() or 0",
    "total_students = filter_by_tenant(Student.query, Student).count()": "total_students = filter_by_tenant(base_student_q, Student).with_entities(func.count(func.distinct(Student.id))).scalar() or 0",
    "prof_q = filter_by_tenant(Professor.query, Professor)": "prof_q_tmp = filter_by_tenant(base_prof_q, Professor)",
    "total_professors = prof_q.count()": "total_professors = prof_q_tmp.with_entities(func.count(func.distinct(Professor.id))).scalar() or 0",
    "db.session.query(Student.sex, func.count(Student.id)), Student": "base_student_q.with_entities(Student.sex, func.count(func.distinct(Student.id))), Student",
    "db.session.query(Student.race, func.count(Student.id)), Student": "base_student_q.with_entities(Student.race, func.count(func.distinct(Student.id))), Student",
    "db.session.query(Student.nationality, func.count(Student.id)), Student": "base_student_q.with_entities(Student.nationality, func.count(func.distinct(Student.id))), Student",
    "db.session.query(Student.birth_country, func.count(Student.id).label('total')), Student": "base_student_q.with_entities(Student.birth_country, func.count(func.distinct(Student.id)).label('total')), Student",
    "db.session.query(Student.residential_zone, func.count(Student.id)), Student": "base_student_q.with_entities(Student.residential_zone, func.count(func.distinct(Student.id))), Student",
    "db.session.query(Student.differentiated_location, func.count(Student.id)), Student": "base_student_q.with_entities(Student.differentiated_location, func.count(func.distinct(Student.id))), Student",
    "bolsa_count = filter_by_tenant(Student.query.filter_by(bolsa_familia=True), Student).count()": "bolsa_count = filter_by_tenant(base_student_q.filter(Student.bolsa_familia==True), Student).with_entities(func.count(func.distinct(Student.id))).scalar() or 0",
    "special_needs_count = filter_by_tenant(Student.query.filter_by(special_needs=True), Student).count()": "special_needs_count = filter_by_tenant(base_student_q.filter(Student.special_needs==True), Student).with_entities(func.count(func.distinct(Student.id))).scalar() or 0",
    "db.session.query(Professor.sex, func.count(Professor.id)), Professor": "base_prof_q.with_entities(Professor.sex, func.count(func.distinct(Professor.id))), Professor",
    "db.session.query(Professor.race, func.count(Professor.id)), Professor": "base_prof_q.with_entities(Professor.race, func.count(func.distinct(Professor.id))), Professor"
}

for old, new in replacements.items():
    content = content.replace(old, new)

# And for Unmodulated:
content = content.replace(
    "professors_unmodulated = filter_by_tenant(Professor.query, Professor).filter(",
    "professors_unmodulated = filter_by_tenant(base_prof_q, Professor).filter("
)
content = content.replace(
    "classes_unmodulated = filter_by_tenant(Class.query, Class).filter(",
    "classes_unmodulated = filter_by_tenant(base_class_q, Class).filter("
)
content = content.replace(
    "professors_unmodulated = filter_by_tenant(base_prof_q, Professor).filter(\n        ~Professor.id.in_(db.session.query(TeachingAssignment.professor_id))\n    ).count()",
    "professors_unmodulated = filter_by_tenant(base_prof_q, Professor).filter(\n        ~Professor.id.in_(db.session.query(TeachingAssignment.professor_id))\n    ).with_entities(func.count(func.distinct(Professor.id))).scalar() or 0"
)
content = content.replace(
    "classes_unmodulated = filter_by_tenant(base_class_q, Class).filter(\n        ~Class.id.in_(db.session.query(TeachingAssignment.class_id))\n    ).count()",
    "classes_unmodulated = filter_by_tenant(base_class_q, Class).filter(\n        ~Class.id.in_(db.session.query(TeachingAssignment.class_id))\n    ).with_entities(func.count(func.distinct(Class.id))).scalar() or 0"
)

# And for School Years:
years_q_old = """    years_q = db.session.query(
        SchoolYear.name,
        func.count(func.distinct(Class.id)),
        func.count(Enrollment.id)
    ).select_from(SchoolYear) \\
     .outerjoin(Class, Class.school_year_id == SchoolYear.id) \\
     .outerjoin(Enrollment, Enrollment.class_id == Class.id)"""

years_q_new = """    years_q = db.session.query(
        SchoolYear.name,
        func.count(func.distinct(Class.id)),
        func.count(func.distinct(Enrollment.id))
    ).select_from(SchoolYear)
    if drill_regional or drill_municipio:
        years_q = years_q.join(Class, Class.school_year_id == SchoolYear.id) \\
                         .join(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id) \\
                         .join(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id) \\
                         .outerjoin(Enrollment, Enrollment.class_id == Class.id)
        if drill_regional: years_q = years_q.filter(RegionalUnit.name == drill_regional)
        if drill_municipio: years_q = years_q.filter(SchoolUnit.municipio == drill_municipio)
    else:
        years_q = years_q.outerjoin(Class, Class.school_year_id == SchoolYear.id) \\
                         .outerjoin(Enrollment, Enrollment.class_id == Class.id)
"""
content = content.replace(years_q_old, years_q_new)

# And for Shifts:
shifts_q_old = """    shifts_q = db.session.query(
        Class.shift,
        func.count(func.distinct(Class.id)),
        func.count(Enrollment.id)
    ).select_from(Class) \\
     .outerjoin(Enrollment, Enrollment.class_id == Class.id)"""

shifts_q_new = """    shifts_q = db.session.query(
        Class.shift,
        func.count(func.distinct(Class.id)),
        func.count(func.distinct(Enrollment.id))
    ).select_from(Class)
    if drill_regional or drill_municipio:
        shifts_q = shifts_q.join(SchoolUnit, Class.teaching_unit_id == SchoolUnit.id) \\
                           .join(RegionalUnit, SchoolUnit.parent_id == RegionalUnit.id) \\
                           .outerjoin(Enrollment, Enrollment.class_id == Class.id)
        if drill_regional: shifts_q = shifts_q.filter(RegionalUnit.name == drill_regional)
        if drill_municipio: shifts_q = shifts_q.filter(SchoolUnit.municipio == drill_municipio)
    else:
        shifts_q = shifts_q.outerjoin(Enrollment, Enrollment.class_id == Class.id)
"""
content = content.replace(shifts_q_old, shifts_q_new)

# Make sure we don't break the summary metrics which are located before we process drill down variables.
# Wait, `total_schools`, `total_classes`, etc., are at the very top of `academic_dashboard()`.
# We need to move `drill_regional` and `drill_municipio` parsing to the very top.
# Let's find the def
def_point = "def academic_dashboard():"
moved_vars = """
    drill_regional = request.args.get('drill_regional')
    drill_municipio = request.args.get('drill_municipio')
"""
content = content.replace("    drill_regional = request.args.get('drill_regional')\n    drill_municipio = request.args.get('drill_municipio')\n", "")
content = content.replace(def_point, def_point + moved_vars)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done updating queries for drill down.")
