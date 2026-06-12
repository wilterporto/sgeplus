from app import create_app, db
app = create_app()
with app.app_context():
    tables = db.metadata.sorted_tables
    for t in tables:
        try:
            count = db.session.execute(db.text(f'SELECT count(*) FROM "{t.name}"')).scalar()
            print(f"{t.name}: {count}")
        except Exception as e:
            print(f"{t.name}: ERROR")
            db.session.rollback()
