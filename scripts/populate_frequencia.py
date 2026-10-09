import random
from app import create_app, db
from app.models import ExternalEvaluationStudent, ExternalEvaluationResult
from sqlalchemy import func

app = create_app()

with app.app_context():
    students = ExternalEvaluationStudent.query.all()
    print(f"Populating frequencia for {len(students)} students...")
    
    count = 0
    for student in students:
        # Generate some mock data for frequency. Let's make it more realistic
        # based on their correct answers ratio if they took the test.
        results = ExternalEvaluationResult.query.filter_by(external_evaluation_student_id=student.id).all()
        total_questions = len(results)
        
        if total_questions > 0:
            correct_answers = sum(1 for r in results if str(r.atr_certo).lower() in ['1', 'true', 'certo', 'True', 'CERTO'])
            pct = (correct_answers / total_questions) * 100
            
            # Simulated frequency based on performance + noise
            freq = min(100, max(0, 50 + (pct * 0.4) + random.uniform(-15, 15)))
        else:
            # If they didn't take it or no results, random lower frequency
            freq = random.uniform(30, 80)
            
        student.alu_frequencia = freq
        count += 1
        if count % 500 == 0:
            db.session.commit()
            print(f"Processed {count}...")
            
    db.session.commit()
    print("Done populating frequencia!")
