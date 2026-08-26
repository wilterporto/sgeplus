import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import Exam, SchoolYear, Subject, TeachingUnit, Class, Enrollment, Student, StudentResult

app = create_app()
with app.app_context():
    query = db.session.query(
        TeachingUnit, Exam, StudentResult
    ).join(Class, TeachingUnit.id == Class.teaching_unit_id)\
     .join(Enrollment, Class.id == Enrollment.class_id)\
     .join(Student, Enrollment.student_id == Student.id)\
     .join(StudentResult, Student.id == StudentResult.student_id)\
     .join(Exam, StudentResult.exam_id == Exam.id)\
     .filter(StudentResult.absence_reason_id == None, Enrollment.active == True)\
     .limit(50)
     
    results_by_school = {}
    for unit, exam, result in query.all():
        unit_name = unit.name
        if unit_name not in results_by_school:
            results_by_school[unit_name] = {'subjects': {}}
        
        if exam.subject_id:
            s_id = str(exam.subject_id)
            if s_id not in results_by_school[unit_name]['subjects']:
                results_by_school[unit_name]['subjects'][s_id] = {'sum': 0, 'count': 0}
            results_by_school[unit_name]['subjects'][s_id]['sum'] += (result.score_percentage or 0)
            results_by_school[unit_name]['subjects'][s_id]['count'] += 1
        else:
            if result.subject_attendance:
                try:
                    att_dict = json.loads(result.subject_attendance)
                    for s_id, score in att_dict.items():
                        if s_id not in results_by_school[unit_name]['subjects']:
                            results_by_school[unit_name]['subjects'][s_id] = {'sum': 0, 'count': 0}
                        results_by_school[unit_name]['subjects'][s_id]['sum'] += float(score)
                        results_by_school[unit_name]['subjects'][s_id]['count'] += 1
                except Exception as e:
                    pass

    for unit_name, data in results_by_school.items():
        for s_id, s_data in data['subjects'].items():
            s_data['avg'] = s_data['sum'] / s_data['count'] if s_data['count'] > 0 else 0
            
    print(json.dumps(results_by_school, indent=2))
