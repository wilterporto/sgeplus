from app import create_app, db
from app.models import Subject, SchoolYear

app = create_app()
with app.app_context():
    print("--- Subjects ---")
    for s in Subject.query.all():
        print(f"ID: {s.id} - Name: {s.name}")
        
    print("\n--- School Years ---")
    for sy in SchoolYear.query.all():
        print(f"ID: {sy.id} - Name: {sy.name}")
