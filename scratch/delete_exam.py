from app import create_app, db
from app.models import Exam, StudentResult, ExamItem

app = create_app()

with app.app_context():
    exam_title = "Simulado Multidisciplinar Integrado"
    exam = Exam.query.filter_by(title=exam_title).first()
    
    if exam:
        print(f"Found exam: '{exam.title}' (ID: {exam.id})")
        
        # Find and delete student results
        results_count = StudentResult.query.filter_by(exam_id=exam.id).count()
        print(f"Found {results_count} registered answers (StudentResult).")
        
        if results_count > 0:
            StudentResult.query.filter_by(exam_id=exam.id).delete()
            print(f"Deleted {results_count} student results.")
            
        # The ExamItem are handled by cascade in SQLAlchemy, but deleting them explicitly is fine
        items_count = ExamItem.query.filter_by(exam_id=exam.id).count()
        if items_count > 0:
            ExamItem.query.filter_by(exam_id=exam.id).delete()
            print(f"Deleted {items_count} exam items.")
            
        # Delete the exam itself
        db.session.delete(exam)
        db.session.commit()
        
        print(f"Successfully deleted exam '{exam_title}'.")
    else:
        print(f"Exam '{exam_title}' not found.")
        # List other exams with 'Simulado' in the name
        similar = Exam.query.filter(Exam.title.like('%Simulado%')).all()
        if similar:
            print("Found similar exams:")
            for e in similar:
                print(f" - ID: {e.id}, Title: '{e.title}'")
        else:
            print("No similar exams found.")
