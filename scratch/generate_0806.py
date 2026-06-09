import random
import datetime
from app import create_app, db
from app.models import Student, AnthropometricRecord, WHOLmsData
from app.utils.anthropometry import calculate_age_months

app = create_app()
app.app_context().push()

target_date = datetime.date(2026, 6, 8)

# Desired percentages
bmi_targets = [
    ("Eutrofia", 86.0),
    ("Magreza", 2.0),
    ("Magreza Acentuada", 3.0),
    ("Sobrepeso", 2.0),
    ("Obesidade", 3.0),
    ("Obesidade Grave", 4.0),
]

height_targets = [
    ("Muito Baixa Estatura", 3.0),
    ("Baixa Estatura", 7.0),
    ("Estatura Adequada", 90.0),
]

def pick_target(targets):
    r = random.uniform(0, 100)
    cumulative = 0.0
    for name, pct in targets:
        cumulative += pct
        if r <= cumulative:
            return name
    return targets[-1][0]

def get_target_zscore(indicator_type, status, age_months):
    if indicator_type == 'bmi':
        is_young = age_months <= 60
        if status == "Magreza Acentuada":
            return random.uniform(-4.0, -3.1)
        elif status == "Magreza":
            return random.uniform(-2.9, -2.1)
        elif status == "Eutrofia":
            return random.uniform(-1.9, 0.9)
        elif status == "Risco de Sobrepeso" and is_young:
            return random.uniform(1.1, 1.9)
        elif status == "Sobrepeso":
            return random.uniform(2.1, 2.9) if is_young else random.uniform(1.1, 1.9)
        elif status == "Obesidade":
            return random.uniform(3.1, 4.0) if is_young else random.uniform(2.1, 2.9)
        elif status == "Obesidade Grave" and not is_young:
            return random.uniform(3.1, 4.0)
        else:
            return 0.0 # Default
    elif indicator_type == 'height':
        if status == "Muito Baixa Estatura":
            return random.uniform(-4.0, -3.1)
        elif status == "Baixa Estatura":
            return random.uniform(-2.9, -2.1)
        elif status == "Estatura Adequada":
            return random.uniform(-1.9, 2.0)
        else:
            return 0.0

def reverse_value(z, l, m, s):
    if l != 0:
        val = m * ((z * l * s + 1) ** (1 / l))
    else:
        import math
        val = m * math.exp(z * s)
    return val

print("Loading LMS data...")
lms_data = WHOLmsData.query.all()
lms_dict = {}
for d in lms_data:
    lms_dict[(d.indicator, d.sex, d.age_months)] = (d.l_value, d.m_value, d.s_value)

print("Loading students...")
students = Student.query.all()
total = len(students)
print(f"Total students: {total}")

records_to_insert = []
batch_size = 5000

print(f"Generating new records for {target_date}...")
for i, student in enumerate(students):
    if not student.birth_date:
        continue
    
    age_months = calculate_age_months(student.birth_date, target_date)
    sex_char = 'M' if student.sex and str(student.sex).lower().startswith('m') else 'F'
    
    # Check if LMS data exists
    h_lms = lms_dict.get(('height_for_age', sex_char, age_months))
    b_lms = lms_dict.get(('bmi_for_age', sex_char, age_months))
    
    if not h_lms or not b_lms:
        continue
        
    target_bmi_status = pick_target(bmi_targets)
    target_height_status = pick_target(height_targets)
    
    # Z-scores
    z_bmi = get_target_zscore('bmi', target_bmi_status, age_months)
    z_height = get_target_zscore('height', target_height_status, age_months)
    
    # Calculate exact height
    height_cm = reverse_value(z_height, h_lms[0], h_lms[1], h_lms[2])
    
    # Calculate exact BMI
    bmi = reverse_value(z_bmi, b_lms[0], b_lms[1], b_lms[2])
    
    # Calculate exact weight from BMI and height
    height_m = height_cm / 100.0
    weight_kg = bmi * (height_m ** 2)
    
    rec = AnthropometricRecord(
        tenant_id=student.tenant_id,
        student_id=student.id,
        date=target_date,
        weight=round(weight_kg, 2),
        height=round(height_cm, 2)
    )
    # The process_anthropometric_data could be called but we are doing mass insert, 
    # so we calculate them directly here to be fast.
    rec.bmi = round(bmi, 2)
    rec.bmi_zscore = round(z_bmi, 2)
    rec.nutritional_status = target_bmi_status
    rec.height_zscore = round(z_height, 2)
    rec.growth_status = target_height_status
    
    records_to_insert.append(rec)
    
    if len(records_to_insert) >= batch_size:
        db.session.bulk_save_objects(records_to_insert)
        db.session.commit()
        records_to_insert = []
        print(f"Inserted {i+1}/{total} records...")

if records_to_insert:
    db.session.bulk_save_objects(records_to_insert)
    db.session.commit()

print("Done generating new records!")
