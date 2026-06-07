import os
from datetime import datetime, date
from random import shuffle, random
from app import create_app, db
from app.models import Student, AnthropometricRecord
from sqlalchemy import text
from dateutil.relativedelta import relativedelta

app = create_app()

def populate():
    with app.app_context():
        print("Clearing old records...")
        db.session.execute(text("DELETE FROM anthropometric_record"))
        db.session.commit()
        print("Old records cleared.")

        print("Fetching student data...")
        # Only fetch necessary columns to save memory and time
        result = db.session.execute(text("SELECT id, tenant_id, birth_date FROM student")).fetchall()
        print(f"Total students: {len(result)}")

        dates = [
            date(2026, 2, 2),
            date(2026, 3, 2),
            date(2026, 4, 2),
            date(2026, 5, 1),
            date(2026, 6, 2)
        ]
        
        final_date = dates[-1]

        students_0_to_4 = []
        students_5_plus = []

        # Each student is a tuple: (id, tenant_id, birth_date)
        for s_id, t_id, b_date in result:
            student_dict = {'id': s_id, 'tenant_id': t_id}
            if not b_date:
                students_5_plus.append(student_dict)
                continue
            
            # parse date if it's a string, though SQLAlchemy usually returns a datetime.date
            if isinstance(b_date, str):
                try:
                    b_date = datetime.strptime(b_date, '%Y-%m-%d').date()
                except ValueError:
                    # try other formats or fallback
                    students_5_plus.append(student_dict)
                    continue
            
            age = relativedelta(final_date, b_date)
            if age.years < 5:
                students_0_to_4.append(student_dict)
            else:
                students_5_plus.append(student_dict)

        print(f"Students 0-4: {len(students_0_to_4)}")
        print(f"Students 5+: {len(students_5_plus)}")

        dist_0_4 = [
            ("Magreza acentuada", 2),
            ("Magreza", 3),
            ("Eutrofia (Peso normal)", 80),
            ("Risco de sobrepeso", 2),
            ("Sobrepeso", 15),
            ("Obesidade", 4),
            ("sem_afericao", 1)
        ]

        dist_5_plus = [
            ("Magreza acentuada", 3),
            ("Magreza", 2),
            ("Eutrofia (Peso normal)", 85),
            ("Sobrepeso", 2),
            ("Obesidade", 3),
            ("Obesidade grave", 4),
            ("sem_afericao", 1)
        ]

        def assign_status(students_list, distribution):
            total_students = len(students_list)
            if total_students == 0: return []
            
            total_weight = sum([d[1] for d in distribution])
            counts = []
            for status, weight in distribution:
                count = int(round((weight / total_weight) * total_students))
                counts.append([status, count])
                
            current_total = sum(c[1] for c in counts)
            diff = total_students - current_total
            if diff != 0:
                largest_idx = max(range(len(counts)), key=lambda i: counts[i][1])
                counts[largest_idx][1] += diff
                
            status_pool = []
            for status, count in counts:
                status_pool.extend([status] * count)
                
            shuffle(status_pool)
            return list(zip(students_list, status_pool))

        assignments = []
        assignments.extend(assign_status(students_0_to_4, dist_0_4))
        assignments.extend(assign_status(students_5_plus, dist_5_plus))
        
        print("Generating records...")

        # Bulk insert mapping
        records_to_insert = []
        chunk_size = 50000
        total_inserted = 0
        
        for student, status in assignments:
            if status == "sem_afericao":
                continue
                
            base_weight = 20.0
            base_height = 1.10
            # if the student is from 5_plus, we give them different base weight
            if student in students_5_plus:
                base_weight = 40.0
                base_height = 1.50
                
            for dt in dates:
                w = base_weight + (random() * 2)
                h = base_height + (random() * 0.05)
                bmi = w / (h * h)
                
                records_to_insert.append({
                    'tenant_id': student['tenant_id'],
                    'student_id': student['id'],
                    'date': dt,
                    'weight': round(w, 2),
                    'height': round(h, 2),
                    'bmi': round(bmi, 2),
                    'nutritional_status': status,
                    'growth_status': 'Adequado',
                    'created_at': datetime.now()
                })

            if len(records_to_insert) >= chunk_size:
                db.session.execute(
                    AnthropometricRecord.__table__.insert(),
                    records_to_insert
                )
                db.session.commit()
                total_inserted += len(records_to_insert)
                print(f"Inserted {total_inserted} records...")
                records_to_insert = []

        if records_to_insert:
            db.session.execute(
                AnthropometricRecord.__table__.insert(),
                records_to_insert
            )
            db.session.commit()
            total_inserted += len(records_to_insert)
            
        print(f"Finished! Total records inserted: {total_inserted}")

if __name__ == '__main__':
    populate()
