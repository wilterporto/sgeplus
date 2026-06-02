import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import Tenant, TeachingUnit

app = create_app()
with app.app_context():
    types = db.session.query(TeachingUnit.type).distinct().all()
    print("Distinct types in TeachingUnit:")
    for t in types:
        print(f"'{t[0]}'")
