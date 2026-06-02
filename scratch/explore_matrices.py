import os
import sys

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Tenant, ReferenceMatrix, Theme, Descriptor, Question, question_descriptors

app = create_app()

with app.app_context():
    source_tenant = Tenant.query.filter_by(name="SME Goiânia").first()
    dest_tenant = Tenant.query.filter_by(name="SEDUC-TO").first()

    print(f"Source Tenant: {source_tenant.name if source_tenant else 'Not Found'}")
    print(f"Dest Tenant: {dest_tenant.name if dest_tenant else 'Not Found'}")

    if source_tenant:
        matrices = ReferenceMatrix.query.filter(ReferenceMatrix.tenant_id == source_tenant.id).all()
        for m in matrices:
            print(f"Matrix: ID={m.id}, Name='{m.name}'")
