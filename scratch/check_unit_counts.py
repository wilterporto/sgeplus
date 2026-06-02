import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import Tenant, TeachingUnit

app = create_app()
with app.app_context():
    units = TeachingUnit.query.all()
    print("Types in DB:")
    for u in units[:5]:
        print(f"Name: {u.name}, Type: {u.type}, classes_count: {u.classes_count}, students_count: {u.students_count}")
    
    escolas = [u for u in units if u.type and u.type.lower() == 'escola']
    regionais = [u for u in units if u.type and u.type.lower() == 'regional']
    
    if escolas:
        print(f"\nExemplo Escola: {escolas[0].name}, Type: {escolas[0].type}, classes_count: {escolas[0].classes_count}, students_count: {escolas[0].students_count}")
    if regionais:
        print(f"\nExemplo Regional: {regionais[0].name}, Type: {regionais[0].type}, classes_count: {regionais[0].classes_count}, students_count: {regionais[0].students_count}")
