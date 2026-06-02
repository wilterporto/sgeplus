import os
import sys

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Tenant, ReferenceMatrix, Theme, Descriptor, SchoolYear

app = create_app()

AREAS = [
    "Linguagens, Códigos e suas Tecnologias",
    "Matemática e suas Tecnologias",
    "Ciências da Natureza e suas Tecnologias",
    "Ciências Humanas e suas Tecnologias"
]

YEARS = ["1ª SÉRIE", "2ª SÉRIE", "3ª SÉRIE"]

with app.app_context():
    tenant_name = "SEDUC-TO"
    tenant = Tenant.query.filter_by(name=tenant_name).first()

    if not tenant:
        print(f"Tenant {tenant_name} not found")
        sys.exit(1)

    # 1. Create Matrix
    matrix_name = "ENEM"
    matrix = ReferenceMatrix.query.filter_by(tenant_id=tenant.id, name=matrix_name).first()
    if not matrix:
        matrix = ReferenceMatrix(
            tenant_id=tenant.id,
            name=matrix_name,
            description="Matriz de Referência do Exame Nacional do Ensino Médio"
        )
        db.session.add(matrix)
        db.session.flush()
        print(f"Created matrix '{matrix.name}'")
    else:
        print(f"Matrix '{matrix.name}' already exists.")

    # 2. Get or Create School Years
    school_years = {}
    for year_name in YEARS:
        sy = SchoolYear.query.filter_by(tenant_id=tenant.id, name=year_name).first()
        if not sy:
            sy = SchoolYear(tenant_id=tenant.id, name=year_name)
            db.session.add(sy)
            db.session.flush()
            print(f"Created SchoolYear '{year_name}'")
        school_years[year_name] = sy.id

    # 3. Create Themes and Descriptors
    created_desc_count = 0
    for area in AREAS:
        theme = Theme.query.filter_by(tenant_id=tenant.id, name=area, matrix_id=matrix.id).first()
        if not theme:
            theme = Theme(tenant_id=tenant.id, name=area, matrix_id=matrix.id)
            db.session.add(theme)
            db.session.flush()
            print(f"Created Theme '{area}'")

        for sy_name, sy_id in school_years.items():
            for i in range(1, 31):
                code = f"H{i}"
                desc = Descriptor.query.filter_by(
                    tenant_id=tenant.id, 
                    code=code, 
                    matrix_id=matrix.id, 
                    school_year_id=sy_id, 
                    theme_id=theme.id
                ).first()
                
                if not desc:
                    desc = Descriptor(
                        tenant_id=tenant.id,
                        code=code,
                        type="Habilidade",
                        description=f"Habilidade {i} de {area} - {sy_name}",
                        matrix_id=matrix.id,
                        school_year_id=sy_id,
                        theme_id=theme.id,
                        is_active=True
                    )
                    db.session.add(desc)
                    created_desc_count += 1

    db.session.commit()
    print(f"ENEM matrix created. Added {created_desc_count} descriptors.")
