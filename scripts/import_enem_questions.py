
import sys
import os

sys.path.append(os.path.abspath(os.path.join('.', '')))

from app import create_app, db
from app.models import Question, Descriptor, User, Tenant, SchoolYear, Subject, ReferenceMatrix

app = create_app()

def run_import():
    with app.app_context():
        tenant_id = 7
        admin = User.query.filter_by(role='admin').first() or User.query.first()
        admin_id = admin.id if admin else None
        
        matrix = ReferenceMatrix.query.filter(ReferenceMatrix.name.ilike('%ENEM%'), ReferenceMatrix.tenant_id == tenant_id).first()
        if not matrix:
            print('Matriz ENEM nao encontrada.')
            return
            
        subjects_requested = [
            'LÍNGUA PORTUGUESA', 'MATEMÁTICA', 'FILOSOFIA', 'QUÍMICA', 'FÍSICA', 
            'ARTE', 'EDUCAÇÃO FÍSICA', 'GEOGRAFIA', 'HISTÓRIA', 'CIÊNCIAS', 
            'CIÊNCIAS FÍSICAS', 'CIÊNCIAS BIOLÓGICAS'
        ]
        
        years_requested = ['1ª SÉRIE', '2ª SÉRIE', '3ª SÉRIE']
        
        # Ensure subjects exist
        subj_objs = {}
        for s_name in subjects_requested:
            s = Subject.query.filter(Subject.name.ilike(s_name), Subject.tenant_id == tenant_id).first()
            if not s:
                s = Subject(name=s_name, tenant_id=tenant_id)
                db.session.add(s)
                db.session.flush()
            subj_objs[s_name] = s
            
        # Ensure years exist
        year_objs = {}
        for y_name in years_requested:
            y = SchoolYear.query.filter(SchoolYear.name.ilike(y_name), SchoolYear.tenant_id == tenant_id).first()
            if not y:
                y = SchoolYear(name=y_name, tenant_id=tenant_id)
                db.session.add(y)
                db.session.flush()
            year_objs[y_name] = y
            
        # Ensure at least 1 descriptor exists for each Subject and Year combination in ENEM
        descriptors_map = {}
        for s_name in subjects_requested:
            descriptors_map[s_name] = {}
            for y_name in years_requested:
                d = Descriptor.query.filter(
                    Descriptor.matrix_id == matrix.id,
                    Descriptor.subject_id == subj_objs[s_name].id,
                    Descriptor.school_year_id == year_objs[y_name].id,
                    Descriptor.tenant_id == tenant_id
                ).first()
                if not d:
                    d = Descriptor(
                        code=f'H-ENEM-{s_name[:3]}-{y_name[0]}',
                        description=f'Habilidade genérica de {s_name} para a {y_name} no ENEM.',
                        matrix_id=matrix.id,
                        subject_id=subj_objs[s_name].id,
                        school_year_id=year_objs[y_name].id,
                        tenant_id=tenant_id,
                        is_active=True
                    )
                    db.session.add(d)
                    db.session.flush()
                descriptors_map[s_name][y_name] = d
                
        # Generate 10 questions per subject
        inserted = 0
        for s_name in subjects_requested:
            # Distribute among the 3 years
            for i in range(1, 11):
                y_name = years_requested[i % 3]
                
                # Check if exists
                stmt = f'Questão modelo de {s_name} - Simulada estilo ENEM - Número {i}'
                existing = Question.query.filter_by(statement=stmt, tenant_id=tenant_id).first()
                if not existing:
                    q = Question(
                        statement=stmt,
                        difficulty='Média',
                        correct_alternative='A',
                        type='Múltipla Escolha',
                        status='Aprovada',
                        created_by_id=admin_id,
                        approved_by_secretaria=True,
                        tenant_id=tenant_id
                    )
                    q.set_alternatives({
                        'A': f'Alternativa Correta para {s_name} {i}',
                        'B': f'Distrator B para {s_name} {i}',
                        'C': f'Distrator C para {s_name} {i}',
                        'D': f'Distrator D para {s_name} {i}',
                        'E': f'Distrator E para {s_name} {i}'
                    })
                    q.descriptors.append(descriptors_map[s_name][y_name])
                    db.session.add(q)
                    inserted += 1
        db.session.commit()
        print(f'Sucesso! {inserted} questoes importadas/geradas.')

run_import()
