import os
import sys

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Tenant, ReferenceMatrix, Theme, Descriptor, Subject

app = create_app()

COMPONENT_MAPPING = {
    "Matemática e suas Tecnologias": ["MATEMÁTICA"],
    "Ciências Humanas e suas Tecnologias": ["GEOGRAFIA", "HISTÓRIA", "FILOSOFIA", "CIÊNCIAS HUMANAS"], # Adding CIÊNCIAS HUMANAS just in case
    "Ciências da Natureza e suas Tecnologias": ["CIÊNCIAS NATURAIS", "FÍSICA"],
    "Linguagens, Códigos e suas Tecnologias": ["LÍNGUA PORTUGUESA", "EDUCAÇÃO FÍSICA"]
}

with app.app_context():
    tenant = Tenant.query.filter_by(name="SEDUC-TO").first()
    matrix = ReferenceMatrix.query.filter_by(tenant_id=tenant.id, name="ENEM").first()

    if not tenant or not matrix:
        print("Tenant or Matrix not found.")
        sys.exit(1)

    print("Checking and creating components (Subjects)...")
    subject_objects = {}
    for area, comps in COMPONENT_MAPPING.items():
        subject_objects[area] = []
        for comp_name in comps:
            subj = Subject.query.filter_by(tenant_id=tenant.id, name=comp_name).first()
            if not subj:
                subj = Subject(tenant_id=tenant.id, name=comp_name)
                db.session.add(subj)
                db.session.flush()
                print(f"Created Subject '{comp_name}'")
            subject_objects[area].append(subj)

    print("Distributing descriptors among components...")
    
    for area, comps in COMPONENT_MAPPING.items():
        theme = Theme.query.filter_by(tenant_id=tenant.id, matrix_id=matrix.id, name=area).first()
        if not theme:
            print(f"Theme '{area}' not found. Skipping.")
            continue
            
        descriptors = Descriptor.query.filter_by(tenant_id=tenant.id, matrix_id=matrix.id, theme_id=theme.id).all()
        
        # We need to distribute descriptors per school year. 
        # So let's group them by school_year_id to distribute evenly per year.
        desc_by_sy = {}
        for d in descriptors:
            if d.school_year_id not in desc_by_sy:
                desc_by_sy[d.school_year_id] = []
            desc_by_sy[d.school_year_id].append(d)
            
        for sy_id, sy_descs in desc_by_sy.items():
            sy_descs.sort(key=lambda x: int(x.code.replace('H', ''))) # Sort H1, H2...
            
            num_comps = len(subject_objects[area])
            if num_comps == 0:
                continue
                
            chunk_size = len(sy_descs) // num_comps
            
            for i, subj in enumerate(subject_objects[area]):
                start_idx = i * chunk_size
                # the last component takes any remainder
                end_idx = (i + 1) * chunk_size if i < num_comps - 1 else len(sy_descs)
                
                for d in sy_descs[start_idx:end_idx]:
                    d.subject_id = subj.id

    db.session.commit()
    print("Components created and descriptors successfully distributed!")
