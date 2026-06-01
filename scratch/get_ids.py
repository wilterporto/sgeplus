from app import create_app, db
from app.models import Tenant, ReferenceMatrix, Subject, SchoolYear, Descriptor
from sqlalchemy import func

app = create_app()
with app.app_context():
    tenant = Tenant.query.filter(func.lower(Tenant.name).like('%goiânia%')).first()
    print("Tenant:", tenant.id if tenant else None, tenant.name if tenant else "Not found")
    
    matrix = ReferenceMatrix.query.filter(func.lower(ReferenceMatrix.name).like('%saeb%')).first()
    print("Matrix:", matrix.id if matrix else None, matrix.name if matrix else "Not found")
    
    for subj in Subject.query.all():
        print("Subject:", subj.id, subj.name)
        
    for sy in SchoolYear.query.all():
        print("SchoolYear:", sy.id, sy.name)
