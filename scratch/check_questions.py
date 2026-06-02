import os
import sys

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Tenant, Question, question_descriptors, Descriptor, ReferenceMatrix

app = create_app()
with app.app_context():
    tenant = Tenant.query.filter_by(name="SEDUC-TO").first()
    matrix = ReferenceMatrix.query.filter_by(tenant_id=tenant.id, name="ENEM").first()
    
    # Get all descriptors for this matrix
    desc_ids = [d.id for d in Descriptor.query.filter_by(matrix_id=matrix.id).all()]
    
    q_count = Question.query.join(question_descriptors).filter(
        Question.tenant_id == tenant.id,
        question_descriptors.c.descriptor_id.in_(desc_ids)
    ).count()
    
    print(f"Total questions linked to ENEM in SEDUC-TO: {q_count}")
