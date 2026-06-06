import math
from datetime import date
from dateutil.relativedelta import relativedelta
from app.models import WHOLmsData

def calculate_age_months(birth_date: date, measurement_date: date) -> int:
    """Calculates age in exact months."""
    if not birth_date or not measurement_date:
        return 0
    delta = relativedelta(measurement_date, birth_date)
    return delta.years * 12 + delta.months

def calculate_zscore(value: float, l: float, m: float, s: float) -> float:
    """Calculates z-score using the WHO LMS formula."""
    if value <= 0 or m <= 0 or s <= 0:
        return None
    if l != 0:
        z = (((value / m) ** l) - 1) / (l * s)
    else:
        z = math.log(value / m) / s
    return round(z, 2)

def get_nutritional_status(zscore: float, age_months: int) -> str:
    """Returns WHO nutritional status based on BMI-for-age Z-Score."""
    if zscore is None:
        return "N/A"
    
    if age_months <= 60: # 0 to 5 years
        if zscore < -3:
            return "Magreza Acentuada"
        elif zscore < -2:
            return "Magreza"
        elif zscore <= 1: # -2 to +1 is normal for 0-5y wait, actually > +1 is Risco de Sobrepeso
            return "Eutrofia"
        elif zscore <= 2:
            return "Risco de Sobrepeso"
        elif zscore <= 3:
            return "Sobrepeso"
        else:
            return "Obesidade"
    else: # 5 to 19 years
        if zscore < -3:
            return "Magreza Acentuada"
        elif zscore < -2:
            return "Magreza"
        elif zscore <= 1:
            return "Eutrofia"
        elif zscore <= 2:
            return "Sobrepeso"
        elif zscore <= 3:
            return "Obesidade"
        else:
            return "Obesidade Grave"

def get_growth_status(zscore: float) -> str:
    """Returns WHO growth status based on Height-for-age Z-Score."""
    if zscore is None:
        return "N/A"
    
    if zscore < -3:
        return "Muito Baixa Estatura"
    elif zscore < -2:
        return "Baixa Estatura"
    else:
        return "Estatura Adequada"

def process_anthropometric_data(record):
    """Calculates BMI and Z-scores for a given record, updates it, but does not commit."""
    if not record.student or not record.student.birth_date:
        return
        
    age_months = calculate_age_months(record.student.birth_date, record.date)
    
    if record.height > 0 and record.weight > 0:
        height_m = float(record.height) / 100.0
        record.bmi = round(float(record.weight) / (height_m * height_m), 2)
    else:
        record.bmi = None
        
    sex_char = 'M' if record.student.sex and str(record.student.sex).lower().startswith('m') else 'F'
    
    # BMI Z-score
    bmi_lms = WHOLmsData.query.filter_by(indicator='bmi_for_age', sex=sex_char, age_months=age_months).first()
    if bmi_lms and record.bmi:
        record.bmi_zscore = calculate_zscore(float(record.bmi), bmi_lms.l_value, bmi_lms.m_value, bmi_lms.s_value)
        record.nutritional_status = get_nutritional_status(record.bmi_zscore, age_months)
    else:
        record.bmi_zscore = None
        record.nutritional_status = "N/A"
        
    # Height Z-score
    height_lms = WHOLmsData.query.filter_by(indicator='height_for_age', sex=sex_char, age_months=age_months).first()
    if height_lms and record.height:
        record.height_zscore = calculate_zscore(float(record.height), height_lms.l_value, height_lms.m_value, height_lms.s_value)
        record.growth_status = get_growth_status(record.height_zscore)
    else:
        record.height_zscore = None
        record.growth_status = "N/A"
