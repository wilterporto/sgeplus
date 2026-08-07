import os
import sys
import random
import json
from flask import Flask
from sqlalchemy import asc
import math

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import StudentResult, Exam, Tenant, Evaluation

app = create_app()

def run_update():
    with app.app_context():
        # Get all student results
        results = StudentResult.query.order_by(StudentResult.score_percentage.asc()).all()
        total_results = len(results)
        
        if total_results == 0:
            print("No StudentResult records found.")
            return

        print(f"Processing {total_results} StudentResult records...")

        # Find SME Goiânia tenant ID
        sme_goiania_tenant = Tenant.query.filter(Tenant.name.ilike('%SME Goiânia%')).first()
        sme_tenant_id = sme_goiania_tenant.id if sme_goiania_tenant else None

        # Determine the number of students for the 40-55% bucket (20%)
        # They will be the first 20% since the array is sorted ascending by score
        n_20 = int(math.ceil(total_results * 0.20))
        low_perf_results = results[:n_20]
        remaining_results = results[n_20:]

        # Shuffle remaining for random distribution
        random.shuffle(remaining_results)

        total_rem = len(remaining_results)
        n_100 = int(math.ceil(total_results * 0.15))
        n_85 = int(math.ceil(total_results * 0.15))
        n_75 = int(math.ceil(total_results * 0.15))
        n_70 = int(math.ceil(total_results * 0.15))
        n_65 = int(math.ceil(total_results * 0.10))
        n_60 = total_rem - (n_100 + n_85 + n_75 + n_70 + n_65) # The rest ~10%

        # Bucket assignments
        assignments = []
        assignments.extend([(r, 100) for r in remaining_results[:n_100]])
        
        idx = n_100
        assignments.extend([(r, 85) for r in remaining_results[idx:idx+n_85]])
        
        idx += n_85
        assignments.extend([(r, 75) for r in remaining_results[idx:idx+n_75]])
        
        idx += n_75
        assignments.extend([(r, 70) for r in remaining_results[idx:idx+n_70]])
        
        idx += n_70
        assignments.extend([(r, 65) for r in remaining_results[idx:idx+n_65]])
        
        idx += n_65
        assignments.extend([(r, 60) for r in remaining_results[idx:]])

        # Assign 40-55% to low performers
        for r in low_perf_results:
            assignments.append((r, random.randint(40, 55)))

        print(f"Total assignments calculated: {len(assignments)}")

        count = 0
        for res, att_pct in assignments:
            # Skip if already has subject_attendance and it's a multi exam
            is_multi = (res.exam and res.exam.evaluation and res.exam.evaluation.multiple_components)
            if is_multi and res.subject_attendance:
                continue

            res.attendance_percentage = float(att_pct)
            
            if is_multi:
                # Find distinct subjects in the exam
                subject_ids = set()
                for item in res.exam.items:
                    if item.question and item.question.descriptors:
                        for desc in item.question.descriptors:
                            if desc.subject_id:
                                subject_ids.add(desc.subject_id)
                
                subject_att = {}
                for sid in subject_ids:
                    # Generate a percentage slightly varying from the general attendance
                    # Ensuring it stays between 0 and 100
                    var = random.randint(-5, 5)
                    sub_att = min(max(att_pct + var, 0), 100)
                    subject_att[str(sid)] = sub_att
                
                if subject_att:
                    res.subject_attendance = json.dumps(subject_att)
            
            count += 1
            if count % 1000 == 0:
                db.session.commit()
                print(f"Committed {count} records...")
                
        db.session.commit()
        print("Attendance update complete!")

if __name__ == "__main__":
    run_update()
