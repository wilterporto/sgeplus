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
    "humanas": "Ciências Humanas e suas Tecnologias",
    "natureza": "Ciências da Natureza e suas Tecnologias",
    "matematica": "Matemática e suas Tecnologias",
    # Mappings that might come from API:
    "espanhol": "Linguagens, Códigos e suas Tecnologias",
    "ingles": "Linguagens, Códigos e suas Tecnologias"
}

with app.app_context():
    tenant_name = "SEDUC-TO"
    tenant = Tenant.query.filter_by(name=tenant_name).first()
    
    matrix = ReferenceMatrix.query.filter_by(tenant_id=tenant.id, name="ENEM").first()
    sy = SchoolYear.query.filter_by(tenant_id=tenant.id, name="3ª SÉRIE").first()
    
    if not tenant or not matrix or not sy:
        print("Required entities not found. Run seed script first.")
        sys.exit(1)

    print("Fetching questions from enem-api (pages 1-20)...")
    
    descriptors_by_theme = {}
    for api_disc, theme_name in DISCIPLINE_MAP.items():
        theme = Theme.query.filter_by(tenant_id=tenant.id, matrix_id=matrix.id, name=theme_name).first()
        if theme:
            descs = Descriptor.query.filter_by(tenant_id=tenant.id, matrix_id=matrix.id, theme_id=theme.id, school_year_id=sy.id).all()
            descriptors_by_theme[api_disc] = descs

    imported_count = 0
    
    for page in range(1, 25):
        url = f"https://api.enem.dev/v1/exams/2023/questions?page={page}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            response = urllib.request.urlopen(req)
            data = json.loads(response.read().decode('utf-8'))
            questions_list = data.get('questions', data) if isinstance(data, dict) else data
            
            if not questions_list:
                break
                
            for q_data in questions_list:
                context = q_data.get('context') or ""
                intro = q_data.get('alternativesIntroduction') or ""
                statement = context + "\n\n" + intro if context else intro
                if not statement:
                    continue
                    
                alts = q_data.get('alternatives', [])
                alt_dict = {}
                for a in alts:
                    alt_dict[a['letter']] = a['text']
                    
                correct_alt = q_data.get('correctAlternative')
                
                # Check if already exists (using statement)
                existing = Question.query.filter_by(tenant_id=tenant.id, statement=statement).first()
                if not existing:
                    new_q = Question(
                        tenant_id=tenant.id,
                        statement=statement,
                        difficulty="Médio",
                        alternatives=json.dumps(alt_dict, ensure_ascii=False),
                        correct_alternative=correct_alt,
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
            print(f"Page {page}: Imported {len(questions_list)} questions...")
            time.sleep(1)
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break
                
    print(f"Import completed. Total new questions imported: {imported_count}")
