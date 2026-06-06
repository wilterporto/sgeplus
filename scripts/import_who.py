import os
import sys
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from app.models import WHOLmsData

app = create_app()

def generate_approximate_data():
    """Generates approximate WHO LMS values for testing."""
    data = []
    for m in range(0, 229): # 0 to 19 years (228 months)
        m_val = 15.0 + (m / 228.0) * 5.0
        data.append(WHOLmsData(indicator='bmi_for_age', sex='M', age_months=m, l_value=-1.5, m_value=m_val, s_value=0.1))
        data.append(WHOLmsData(indicator='bmi_for_age', sex='F', age_months=m, l_value=-1.5, m_value=m_val - 0.5, s_value=0.1))
        
        h_val = 50.0 + (m / 228.0) * 125.0
        data.append(WHOLmsData(indicator='height_for_age', sex='M', age_months=m, l_value=1.0, m_value=h_val, s_value=0.04))
        data.append(WHOLmsData(indicator='height_for_age', sex='F', age_months=m, l_value=1.0, m_value=h_val - 10.0, s_value=0.04))
    
    return data

if __name__ == '__main__':
    with app.app_context():
        count = WHOLmsData.query.count()
        if count == 0:
            print('Aviso: Arquivos oficiais da OMS nao encontrados. Populando o banco com valores APROXIMADOS (LMS) para demonstracao.')
            db.session.add_all(generate_approximate_data())
            db.session.commit()
            print('Dados importados com sucesso.')
        else:
            print(f'{count} registros da OMS ja existem no banco.')
