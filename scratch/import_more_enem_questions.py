import os
import sys
import urllib.request
import json
import random
import time

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Tenant, ReferenceMatrix, Theme, Descriptor, Question, SchoolYear

app = create_app()

DISCIPLINE_MAP = {
    "linguagens": "Linguagens, Códigos e suas Tecnologias",
    "espanhol": "Linguagens, Códigos e suas Tecnologias",
    "ingles": "Linguagens, Códigos e suas Tecnologias",
    "humanas": "Ciências Humanas e suas Tecnologias",
    "natureza": "Ciências da Natureza e suas Tecnologias",
    "matematica": "Matemática e suas Tecnologias"
}

with app.app_context():
    tenant = Tenant.query.filter_by(name="SEDUC-TO").first()
    matrix = ReferenceMatrix.query.filter_by(tenant_id=tenant.id, name="ENEM").first()
    sy = SchoolYear.query.filter_by(tenant_id=tenant.id, name="3ª SÉRIE").first()

    if not tenant or not matrix or not sy:
        print("Required entities not found. Run seed script first.")
        sys.exit(1)

    print("Fetching more questions from enem-api (previous years)...")
    
    descriptors_by_theme = {}
    for api_disc, theme_name in DISCIPLINE_MAP.items():
        theme = Theme.query.filter_by(tenant_id=tenant.id, matrix_id=matrix.id, name=theme_name).first()
        if theme:
            descs = Descriptor.query.filter_by(tenant_id=tenant.id, matrix_id=matrix.id, theme_id=theme.id, school_year_id=sy.id).all()
            descriptors_by_theme[api_disc] = descs

    imported_count = 0
    years = [2022, 2021, 2020, 2019, 2018, 2017]
    
    for year in years:
        url = f"https://api.enem.dev/v1/exams/{year}/questions"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            response = urllib.request.urlopen(req)
            data = json.loads(response.read().decode('utf-8'))
            questions_list = data.get('questions', data) if isinstance(data, dict) else data
            
            if not questions_list:
                print(f"No questions for year {year}")
                continue
                
            for q_data in questions_list:
                context = q_data.get('context') or ""
                intro = q_data.get('alternativesIntroduction') or ""
                statement = context + "\n\n" + intro if context else intro
                if not statement:
                    continue
                    
                existing = Question.query.filter_by(tenant_id=tenant.id, statement=statement).first()
                if not existing:
                    alts = q_data.get('alternatives', [])
                    alt_dict = {a['letter']: a['text'] for a in alts}
                    
                    new_q = Question(
                        tenant_id=tenant.id,
                        statement=statement,
                        difficulty="Médio",
                        alternatives=json.dumps(alt_dict, ensure_ascii=False),
                        correct_alternative=q_data.get('correctAlternative'),
                        type="Múltipla Escolha",
                        status="aprovado",
                        approved_by_secretaria=True
                    )
                    
                    api_disc = q_data.get('discipline')
                    if api_disc in descriptors_by_theme and descriptors_by_theme[api_disc]:
                        random_desc = random.choice(descriptors_by_theme[api_disc])
                        new_q.descriptors.append(random_desc)
                        
                    db.session.add(new_q)
                    imported_count += 1
                    
            db.session.commit()
            print(f"Year {year}: Imported questions. Total new so far: {imported_count}")
            time.sleep(1)
        except Exception as e:
            print(f"Error on year {year}: {e}")
                
    print(f"Import completed. Total new questions imported: {imported_count}")
