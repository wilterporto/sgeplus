import os
import sys

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Tenant, ReferenceMatrix, Theme, Descriptor, Question, question_descriptors, Subject, SchoolYear

app = create_app()

with app.app_context():
    source_tenant_name = "SME Goiânia"
    dest_tenant_name = "SEDUC-TO"
    matrix_name = "SAEB"

    source_tenant = Tenant.query.filter_by(name=source_tenant_name).first()
    dest_tenant = Tenant.query.filter_by(name=dest_tenant_name).first()

    if not source_tenant or not dest_tenant:
        print("Tenants not found")
        sys.exit(1)

    source_matrix = ReferenceMatrix.query.filter_by(tenant_id=source_tenant.id, name=matrix_name).first()
    if not source_matrix:
        print(f"Matrix {matrix_name} not found in {source_tenant_name}")
        sys.exit(1)

    print(f"Starting copy of matrix '{source_matrix.name}' from '{source_tenant_name}' to '{dest_tenant_name}'...")

    # 1. Copy Matrix
    dest_matrix = ReferenceMatrix.query.filter_by(tenant_id=dest_tenant.id, name=source_matrix.name).first()
    if not dest_matrix:
        dest_matrix = ReferenceMatrix(
            tenant_id=dest_tenant.id,
            name=source_matrix.name,
            description=source_matrix.description
        )
        db.session.add(dest_matrix)
        db.session.flush()
        print(f"Created matrix '{dest_matrix.name}' (ID: {dest_matrix.id})")
    else:
        print(f"Matrix '{dest_matrix.name}' already exists (ID: {dest_matrix.id})")

    # Mapping dictionaries
    theme_mapping = {} # source_theme_id -> dest_theme_id
    descriptor_mapping = {} # source_descriptor_id -> dest_descriptor_id

    # Helpers for mapping Subject and SchoolYear
    subject_mapping = {}
    school_year_mapping = {}

    def get_dest_subject_id(source_subject_id):
        if not source_subject_id:
            return None
        if source_subject_id in subject_mapping:
            return subject_mapping[source_subject_id]
        
        source_subject = Subject.query.get(source_subject_id)
        if not source_subject:
            return None
            
        dest_subject = Subject.query.filter_by(tenant_id=dest_tenant.id, name=source_subject.name).first()
        if not dest_subject:
            dest_subject = Subject(tenant_id=dest_tenant.id, name=source_subject.name)
            db.session.add(dest_subject)
            db.session.flush()
            print(f"Created Subject '{dest_subject.name}'")
            
        subject_mapping[source_subject_id] = dest_subject.id
        return dest_subject.id

    def get_dest_school_year_id(source_sy_id):
        if not source_sy_id:
            return None
        if source_sy_id in school_year_mapping:
            return school_year_mapping[source_sy_id]
            
        source_sy = SchoolYear.query.get(source_sy_id)
        if not source_sy:
            return None
            
        dest_sy = SchoolYear.query.filter_by(tenant_id=dest_tenant.id, name=source_sy.name).first()
        if not dest_sy:
            dest_sy = SchoolYear(tenant_id=dest_tenant.id, name=source_sy.name)
            db.session.add(dest_sy)
            db.session.flush()
            print(f"Created SchoolYear '{dest_sy.name}'")
            
        school_year_mapping[source_sy_id] = dest_sy.id
        return dest_sy.id

    # 2. Copy Themes
    source_themes = Theme.query.filter_by(matrix_id=source_matrix.id).all()
    for theme in source_themes:
        dest_theme = Theme.query.filter_by(tenant_id=dest_tenant.id, name=theme.name, matrix_id=dest_matrix.id).first()
        if not dest_theme:
            dest_theme = Theme(
                tenant_id=dest_tenant.id,
                name=theme.name,
                matrix_id=dest_matrix.id
            )
            db.session.add(dest_theme)
            db.session.flush()
        theme_mapping[theme.id] = dest_theme.id
    print(f"Processed {len(source_themes)} themes.")

    # 3. Copy Descriptors
    source_descriptors = Descriptor.query.filter_by(matrix_id=source_matrix.id).all()
    for desc in source_descriptors:
        dest_desc = Descriptor.query.filter_by(tenant_id=dest_tenant.id, code=desc.code, matrix_id=dest_matrix.id).first()
        if not dest_desc:
            dest_desc = Descriptor(
                tenant_id=dest_tenant.id,
                code=desc.code,
                type=desc.type,
                description=desc.description,
                subject_legacy=desc.subject_legacy,
                matrix_id=dest_matrix.id,
                school_year_id=get_dest_school_year_id(desc.school_year_id),
                subject_id=get_dest_subject_id(desc.subject_id),
                is_active=desc.is_active,
                theme_id=theme_mapping.get(desc.theme_id) if desc.theme_id else None
            )
            db.session.add(dest_desc)
            db.session.flush()
        descriptor_mapping[desc.id] = dest_desc.id
    print(f"Processed {len(source_descriptors)} descriptors.")

    # 4. Copy Questions
    source_desc_ids = list(descriptor_mapping.keys())
    if not source_desc_ids:
        print("No descriptors found, skipping questions.")
    else:
        # Fetch questions linked to ANY of the source descriptors
        questions_to_copy = Question.query.join(question_descriptors).filter(question_descriptors.c.descriptor_id.in_(source_desc_ids)).all()
        print(f"Found {len(questions_to_copy)} questions linked to the source descriptors.")
        
        copied_count = 0
        for q in questions_to_copy:
            dest_q = Question.query.filter_by(tenant_id=dest_tenant.id, statement=q.statement).first()
            if not dest_q:
                dest_q = Question(
                    tenant_id=dest_tenant.id,
                    statement=q.statement,
                    difficulty=q.difficulty,
                    alternatives=q.alternatives,
                    correct_alternative=q.correct_alternative,
                    image_path=q.image_path,
                    type=q.type,
                    created_by_id=q.created_by_id, 
                    status=q.status,
                    approved_by_secretaria=q.approved_by_secretaria
                )
                db.session.add(dest_q)
                db.session.flush()
                copied_count += 1
                
                # Link descriptors
                for old_desc in q.descriptors:
                    if old_desc.id in descriptor_mapping:
                        new_desc = Descriptor.query.get(descriptor_mapping[old_desc.id])
                        if new_desc not in dest_q.descriptors:
                            dest_q.descriptors.append(new_desc)
            else:
                # Question already exists, ensure it is linked to the correct dest descriptors
                for old_desc in q.descriptors:
                    if old_desc.id in descriptor_mapping:
                        new_desc = Descriptor.query.get(descriptor_mapping[old_desc.id])
                        if new_desc not in dest_q.descriptors:
                            dest_q.descriptors.append(new_desc)

        print(f"Copied {copied_count} new questions.")

    db.session.commit()
    print("Migration completed successfully!")
