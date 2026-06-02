import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import Tenant, TeachingUnit, Class

app = create_app()
with app.app_context():
    regionais = TeachingUnit.query.filter_by(type='Regional').all()
    for r in regionais:
        classes_linked = Class.query.filter_by(teaching_unit_id=r.id).count()
        if classes_linked > 0:
            print(f"ALERTA: Regional {r.name} tem {classes_linked} turmas vinculadas DIRETAMENTE a ela!")
