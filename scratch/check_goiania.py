import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import Tenant, TeachingUnit

app = create_app()
with app.app_context():
    tenant = Tenant.query.filter_by(name="SME Goiânia").first()
    if tenant:
        units = TeachingUnit.query.filter_by(tenant_id=tenant.id).all()
        print(f"Total units in SME Goiânia: {len(units)}")
        units_without_inep = [u for u in units if not u.inep_code]
        print(f"Units without INEP: {len(units_without_inep)}")
        if units_without_inep:
            for u in units_without_inep[:10]:
                print(f" - {u.name}")
    else:
        print("Tenant SME Goiânia not found.")
