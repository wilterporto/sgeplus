import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import Tenant, TeachingUnit

app = create_app()
with app.app_context():
    tenant = Tenant.query.filter_by(name="wilterporto/sgeplus").first()
    if not tenant:
        tenant = Tenant.query.filter_by(name="SME Goiânia").first()

    units = TeachingUnit.query.filter_by(tenant_id=tenant.id).all()
    escolas = [u for u in units if u.type == 'Escola']
    regionais = [u for u in units if u.type == 'Regional']
    
    escolas_com_turmas = [e for e in escolas if e.classes_count > 0]
    regionais_com_turmas = [r for r in regionais if r.classes_count > 0]
    
    print(f"Total Escolas: {len(escolas)}, Escolas com turmas: {len(escolas_com_turmas)}")
    print(f"Total Regionais: {len(regionais)}, Regionais com turmas: {len(regionais_com_turmas)}")
    
    escolas_com_alunos = [e for e in escolas if e.students_count > 0]
    regionais_com_alunos = [r for r in regionais if r.students_count > 0]
    
    print(f"Total Escolas: {len(escolas)}, Escolas com alunos: {len(escolas_com_alunos)}")
    print(f"Total Regionais: {len(regionais)}, Regionais com alunos: {len(regionais_com_alunos)}")
