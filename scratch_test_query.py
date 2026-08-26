import sys
import os

# Add app to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Exam, SchoolYear, Subject, TeachingUnit, Class, Enrollment, Student, StudentResult
from sqlalchemy import func

app = create_app()

with app.app_context():
    # 1. Distinct Evaluation Types
    eval_types = db.session.query(Exam.evaluation_type).distinct().all()
    print("Evaluation Types:", eval_types)
    
    # 2. Distinct Academic Years
    acad_years = db.session.query(Exam.academic_year).distinct().all()
    print("Academic Years:", acad_years)
    
    # 3. School Years
    school_years = db.session.query(SchoolYear).all()
    print("School Years:", [(sy.id, sy.name) for sy in school_years])
    
    # 4. Try the aggregate query (just picking first available values if any)
    query = db.session.query(
        TeachingUnit.name.label('school_name'),
        Subject.name.label('subject_name'),
        func.avg(StudentResult.score_percentage).label('avg_score')
    ).join(Class, TeachingUnit.id == Class.teaching_unit_id)\
     .join(Enrollment, Class.id == Enrollment.class_id)\
     .join(Student, Enrollment.student_id == Student.id)\
     .join(StudentResult, Student.id == StudentResult.student_id)\
     .join(Exam, StudentResult.exam_id == Exam.id)\
     .outerjoin(Subject, Exam.subject_id == Subject.id)\
     .filter(StudentResult.absence_reason_id == None)\
     .group_by(TeachingUnit.name, Subject.name)\
     .limit(10)
     
    print("Sample Data:")
    for row in query.all():
        print(f"School: {row.school_name}, Subject: {row.subject_name}, Avg: {row.avg_score}")
