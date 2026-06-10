
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
            subj_objs[s_name] = s
            
        # Ensure years exist
        year_objs = {}
        for y_name in years_requested:
            y = SchoolYear.query.filter(SchoolYear.name.ilike(y_name), SchoolYear.tenant_id == tenant_id).first()
            year_objs[y_name] = y
            
        # Get descriptors map
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
                descriptors_map[s_name][y_name] = d
                
        # First delete the previous batch to prevent pollution and ensure exact counts
        prev_qs = Question.query.filter(
            Question.statement.like('Questão modelo de % - Simulada estilo ENEM - Número %'), 
            Question.tenant_id == tenant_id
        ).all()
        for q in prev_qs:
            db.session.delete(q)
        db.session.commit()
                
        # Generate 10 questions per subject per year (360 total)
        inserted = 0
        for s_name in subjects_requested:
            for y_name in years_requested:
                for i in range(1, 11):
                    stmt = f'Questão modelo de {s_name} - {y_name} - Simulada estilo ENEM - Número {i}'
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
                        'A': f'Alternativa Correta (A) para {s_name} {y_name} Q{i}',
                        'B': f'Distrator (B) para {s_name} {y_name} Q{i}',
                        'C': f'Distrator (C) para {s_name} {y_name} Q{i}',
                        'D': f'Distrator (D) para {s_name} {y_name} Q{i}',
                        'E': f'Distrator (E) para {s_name} {y_name} Q{i}'
                    })
                    q.descriptors.append(descriptors_map[s_name][y_name])
                    db.session.add(q)
                    inserted += 1
        db.session.commit()
        print(f'Sucesso! {inserted} questoes (10 por componente/serie) geradas.')

run_import()
