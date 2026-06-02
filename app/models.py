from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.utils.timezone import get_brasilia_time

# Association table for User <-> TeachingUnit
user_teaching_units = db.Table('user_teaching_units',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('teaching_unit_id', db.Integer, db.ForeignKey('teaching_unit.id', ondelete='CASCADE'), primary_key=True)
)

class Tenant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    uf = db.Column(db.String(2), nullable=True)
    municipio = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=get_brasilia_time)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20))
    regional = db.Column(db.String(64))
    roles = db.Column(db.String(256), default='professor')
    active = db.Column(db.Boolean, default=True)
    name = db.Column(db.String(128))
    last_login = db.Column(db.DateTime)
    last_agreed_version = db.Column(db.String(20))
    is_system_admin = db.Column(db.Boolean, nullable=False, default=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    
    tenant = db.relationship('Tenant')
    teaching_units = db.relationship('TeachingUnit', secondary=user_teaching_units, lazy='subquery',
        backref=db.backref('users', lazy=True))

    def get_roles(self):
        if self.roles:
            return self.roles.split(',')
        return [self.role] if self.role else []
        
    @property
    def is_admin(self):
        return self.is_system_admin or self.role == 'admin' or 'admin' in self.get_roles()
        
    def add_role(self, role):
        current_roles = self.get_roles()
        if role not in current_roles:
            current_roles.append(role)
            self.roles = ','.join(current_roles)
            
    def remove_role(self, role):
        current_roles = self.get_roles()
        if role in current_roles:
            current_roles.remove(role)
            self.roles = ','.join(current_roles)
            
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def get_reset_password_token(self, expires_in=600):
        from flask import current_app
        import jwt
        import time
        return jwt.encode(
            {'reset_password': self.id, 'exp': time.time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256')
            
    @staticmethod
    def verify_reset_password_token(token):
        from flask import current_app
        import jwt
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return None
        return User.query.get(id)

class ReferenceMatrix(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(256))
    
    tenant = db.relationship('Tenant')
    descriptors = db.relationship('Descriptor', backref='matrix', lazy='dynamic')
    themes = db.relationship('Theme', backref='matrix', lazy='dynamic')
    
    @property
    def questions_count(self):
        from sqlalchemy import text
        result = db.session.execute(
            text("SELECT COUNT(DISTINCT qd.question_id) FROM question_descriptors qd "
                 "JOIN descriptor d ON qd.descriptor_id = d.id "
                 "WHERE d.matrix_id = :matrix_id"),
            {'matrix_id': self.id}
        ).scalar()
        return result or 0

class SchoolYear(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(64), nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_school_year_tenant_name'),
    )
    
    tenant = db.relationship('Tenant')
    curriculums = db.relationship('CurriculumStructure', backref='school_year', lazy='dynamic')
    classes = db.relationship('Class', backref='school_year', lazy='dynamic')

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_subject_tenant_name'),
    )
    
    tenant = db.relationship('Tenant')

class Theme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    matrix_id = db.Column(db.Integer, db.ForeignKey('reference_matrix.id'), nullable=False)
    
    tenant = db.relationship('Tenant')
    descriptors = db.relationship('Descriptor', backref='theme', lazy='dynamic')

class Descriptor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    code = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(20)) # 'Descritor' or 'Habilidade'
    description = db.Column(db.String(256), nullable=False)
    subject_legacy = db.Column(db.String(64))
    matrix_id = db.Column(db.Integer, db.ForeignKey('reference_matrix.id'), nullable=True)
    school_year_id = db.Column(db.Integer, db.ForeignKey('school_year.id'), nullable=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    theme_id = db.Column(db.Integer, db.ForeignKey('theme.id'), nullable=True)
    
    tenant = db.relationship('Tenant')
    school_year = db.relationship('SchoolYear')
    subject = db.relationship('Subject')

# Association table for Question <-> Descriptor
question_descriptors = db.Table('question_descriptors',
    db.Column('question_id', db.Integer, db.ForeignKey('question.id'), primary_key=True),
    db.Column('descriptor_id', db.Integer, db.ForeignKey('descriptor.id'), primary_key=True)
)

# Association table for Question <-> TeachingUnit validation
question_unit_validations = db.Table('question_unit_validations',
    db.Column('question_id', db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True),
    db.Column('teaching_unit_id', db.Integer, db.ForeignKey('teaching_unit.id', ondelete='CASCADE'), primary_key=True)
)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    statement = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20))
    alternatives = db.Column(db.Text, nullable=False) # JSON string
    correct_alternative = db.Column(db.String(1), nullable=False)
    image_path = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=get_brasilia_time)
    type = db.Column(db.String(32))
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='rascunho')
    approved_by_secretaria = db.Column(db.Boolean, default=False)
    
    tenant = db.relationship('Tenant')
    creator = db.relationship('User', backref=db.backref('questions_created', lazy='dynamic'))
    descriptors = db.relationship('Descriptor', secondary=question_descriptors, lazy='subquery',
        backref=db.backref('questions', lazy=True))
    validated_units = db.relationship('TeachingUnit', secondary=question_unit_validations, lazy='subquery',
        backref=db.backref('validated_questions', lazy=True))

    def get_alternatives(self):
        import json
        if not self.alternatives:
            return {}
        try:
            if isinstance(self.alternatives, dict):
                return self.alternatives
            return json.loads(self.alternatives)
        except:
            return {}

class Evaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    logo_path = db.Column(db.String(128))
    type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, default=10, nullable=False)
    scoring_type = db.Column(db.String(20), default='none')
    question_values = db.Column(db.Text)
    multiple_components = db.Column(db.Boolean, default=False)
    
    tenant = db.relationship('Tenant')
    exams = db.relationship('Exam', backref='evaluation', lazy='dynamic')

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    title = db.Column(db.String(128), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=get_brasilia_time)
    academic_year = db.Column(db.String(9), nullable=False)
    application_date = db.Column(db.Date, nullable=False)
    regional_id = db.Column(db.Integer, db.ForeignKey('teaching_unit.id'), nullable=True)
    teaching_unit_id = db.Column(db.Integer, db.ForeignKey('teaching_unit.id'), nullable=True)
    evaluation_id = db.Column(db.Integer, db.ForeignKey('evaluation.id'), nullable=True)
    evaluation_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Rascunho', nullable=False)
    authorized_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    allow_teacher_entry = db.Column(db.Boolean, default=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    school_year_id = db.Column(db.Integer, db.ForeignKey('school_year.id'), nullable=True)
    scoring_type = db.Column(db.String(20), default='none')
    total_value = db.Column(db.Float, default=0.0)
    target_nationality = db.Column(db.String(50), default='Todos')
    target_special_needs = db.Column(db.String(50), default='Todos')
    
    tenant = db.relationship('Tenant')
    creator = db.relationship('User', foreign_keys=[created_by_id], backref=db.backref('exams_created', lazy='dynamic'))
    authorizer = db.relationship('User', foreign_keys=[authorized_by_id], backref=db.backref('exams_authorized', lazy='dynamic'))
    subject = db.relationship('Subject')
    school_year = db.relationship('SchoolYear')
    regional = db.relationship('TeachingUnit', foreign_keys=[regional_id])
    teaching_unit = db.relationship('TeachingUnit', foreign_keys=[teaching_unit_id])
    items = db.relationship('ExamItem', backref='exam', lazy='dynamic', cascade="all, delete-orphan")
    classes = db.relationship('Class', secondary='exam_classes', lazy='dynamic', backref=db.backref('exams', lazy='dynamic'))

# Association table for Exam <-> Class
exam_classes = db.Table('exam_classes',
    db.Column('exam_id', db.Integer, db.ForeignKey('exam.id'), primary_key=True),
    db.Column('class_id', db.Integer, db.ForeignKey('class.id'), primary_key=True)
)

class ExamItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'))
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    value = db.Column(db.Float, default=0.0)
    
    question = db.relationship('Question')

class AbsenceReason(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    
    tenant = db.relationship('Tenant')
    
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_absence_reason_tenant_name'),
    )

class TeachingUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'School' or 'Regional'
    parent_id = db.Column(db.Integer, db.ForeignKey('teaching_unit.id'), nullable=True)
    
    inep_code = db.Column(db.String(20), nullable=True)
    uf = db.Column(db.String(2), nullable=True)
    municipio = db.Column(db.String(128), nullable=True)
    residential_zone = db.Column(db.String(50), nullable=True)
    differentiated_location = db.Column(db.String(128), nullable=True)
    latitude = db.Column(db.String(50), nullable=True)
    longitude = db.Column(db.String(50), nullable=True)
    
    tenant = db.relationship('Tenant')
    parent = db.relationship('TeachingUnit', remote_side=[id], backref='children')
    classes = db.relationship('Class', backref='teaching_unit', lazy='dynamic')
    
    @property
    def classes_count(self):
        from app.models import Class
        if self.type == 'Escola':
            return self.classes.count()
        else:
            return db.session.query(db.func.count(Class.id))\
                .join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)\
                .filter(TeachingUnit.parent_id == self.id)\
                .scalar() or 0
        
    @property
    def students_count(self):
        from app.models import Enrollment, Class
        if self.type == 'Escola':
            return db.session.query(db.func.count(Enrollment.id))\
                .join(Class)\
                .filter(Class.teaching_unit_id == self.id)\
                .scalar() or 0
        else:
            return db.session.query(db.func.count(Enrollment.id))\
                .join(Class)\
                .join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)\
                .filter(TeachingUnit.parent_id == self.id)\
                .scalar() or 0

class CurriculumStructure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    school_year_id = db.Column(db.Integer, db.ForeignKey('school_year.id'), nullable=False)
    
    tenant = db.relationship('Tenant')
    subjects = db.relationship('Subject', secondary='curriculum_subjects', lazy='subquery',
        backref=db.backref('curriculums', lazy=True))
    classes = db.relationship('Class', backref='structure', lazy='dynamic')

# Association table for Curriculum <-> Subject
curriculum_subjects = db.Table('curriculum_subjects',
    db.Column('curriculum_id', db.Integer, db.ForeignKey('curriculum_structure.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subject.id'), primary_key=True)
)

class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(64), nullable=False)
    shift = db.Column(db.String(20))
    school_year_id = db.Column(db.Integer, db.ForeignKey('school_year.id'), nullable=False)
    structure_id = db.Column(db.Integer, db.ForeignKey('curriculum_structure.id'), nullable=False)
    teaching_unit_id = db.Column(db.Integer, db.ForeignKey('teaching_unit.id'), nullable=False)
    
    tenant = db.relationship('Tenant')
    enrollments = db.relationship('Enrollment', backref='enrolled_class', lazy='dynamic')

class Professor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    cpf = db.Column(db.String(11), unique=True)
    sex = db.Column(db.String(10))
    race = db.Column(db.String(20))
    birth_date = db.Column(db.Date)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    email = db.Column(db.String(120))
    nationality = db.Column(db.String(50))
    birth_country = db.Column(db.String(50))
    inep_code = db.Column(db.String(12))
    sus_card = db.Column(db.String(15))
    birth_state = db.Column(db.String(2))
    birth_city_id = db.Column(db.Integer, db.ForeignKey('city.id'))
    residential_zone = db.Column(db.String(20))
    differentiated_location = db.Column(db.String(100))
    
    tenant = db.relationship('Tenant')
    user = db.relationship('User', backref=db.backref('professor_profile', uselist=False))
    birth_city = db.relationship('City')
    assignments = db.relationship('TeachingAssignment', backref='professor', lazy='dynamic', cascade="all, delete-orphan")
    
    @property
    def formatted_cpf(self):
        if self.cpf and len(self.cpf) == 11:
            return f"{self.cpf[:3]}.{self.cpf[3:6]}.{self.cpf[6:9]}-{self.cpf[9:]}"
        return self.cpf or ""
        
    @property
    def primary_school(self):
        first_assignment = self.assignments.first()
        if first_assignment and first_assignment.enrolled_class:
            return first_assignment.enrolled_class.teaching_unit
        return None
        
    @property
    def primary_school_classes_count(self):
        school = self.primary_school
        return school.classes_count if school else 0
        
    @property
    def teaching_units_count(self):
        from app.models import Class
        return db.session.query(db.func.count(db.func.distinct(Class.teaching_unit_id)))\
            .join(TeachingAssignment, TeachingAssignment.class_id == Class.id)\
            .filter(TeachingAssignment.professor_id == self.id)\
            .scalar() or 0

class TeachingAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('professor.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    
    enrolled_class = db.relationship('Class', backref=db.backref('assignments', lazy='dynamic'))
    subject = db.relationship('Subject')

class DietaryRestriction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True, server_default='1', nullable=False)
    
    tenant = db.relationship('Tenant')

# Association table for Student <-> DietaryRestriction
student_dietary_restrictions = db.Table('student_dietary_restrictions',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True),
    db.Column('dietary_restriction_id', db.Integer, db.ForeignKey('dietary_restriction.id'), primary_key=True)
)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    registration_number = db.Column(db.String(20), unique=True, nullable=False)
    birth_date = db.Column(db.Date)
    cpf = db.Column(db.String(11), unique=True)
    sex = db.Column(db.String(10))
    race = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    email = db.Column(db.String(120))
    nationality = db.Column(db.String(50))
    family_income = db.Column(db.String(50))
    special_needs = db.Column(db.Boolean, default=False)
    birth_country = db.Column(db.String(50))
    inep_code = db.Column(db.String(12))
    sus_card = db.Column(db.String(15))
    bolsa_familia = db.Column(db.Boolean, default=False)
    birth_state = db.Column(db.String(2))
    birth_city_id = db.Column(db.Integer, db.ForeignKey('city.id'))
    residential_zone = db.Column(db.String(20))
    differentiated_location = db.Column(db.String(100))
    
    tenant = db.relationship('Tenant')
    user = db.relationship('User', backref=db.backref('student_profile', uselist=False))
    birth_city = db.relationship('City')
    enrollments = db.relationship('Enrollment', backref='student', lazy='dynamic')
    dietary_restrictions = db.relationship('DietaryRestriction', secondary=student_dietary_restrictions, lazy='subquery', backref=db.backref('students', lazy=True))
    
    @property
    def formatted_cpf(self):
        if self.cpf and len(self.cpf) == 11:
            return f"{self.cpf[:3]}.{self.cpf[3:6]}.{self.cpf[6:9]}-{self.cpf[9:]}"
        return self.cpf or ""
        
    @staticmethod
    def generate_registration_number():
        from datetime import datetime
        import random
        year = datetime.now().year
        prefix = f"{year}"
        last_student = Student.query.filter(Student.registration_number.like(f"{prefix}%")).order_by(Student.registration_number.desc()).first()
        if last_student:
            try:
                last_seq = int(last_student.registration_number[4:])
                new_seq = last_seq + 1
            except:
                new_seq = random.randint(10000, 99999)
        else:
            new_seq = 10001
        return f"{prefix}{new_seq}"

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_brasilia_time)

class StudentResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    answers = db.Column(db.Text) # JSON string
    score_percentage = db.Column(db.Float)
    finished_at = db.Column(db.DateTime, default=get_brasilia_time)
    absence_reason_id = db.Column(db.Integer, db.ForeignKey('absence_reason.id'), nullable=True)
    
    exam = db.relationship('Exam', backref=db.backref('results', lazy='dynamic'))
    student = db.relationship('Student', backref=db.backref('exam_results', lazy='dynamic'))
    absence_reason = db.relationship('AbsenceReason')
    
    @property
    def score_points(self):
        if not self.exam or not self.exam.total_value:
            return None
        import json
        answers = json.loads(self.answers) if self.answers else {}
        points = 0.0
        exam = self.exam
        for item in exam.items:
            if not item.question:
                continue
            if str(item.question.id) in answers and answers.get(str(item.question.id)) == item.question.correct_alternative:
                points += (item.value or 0.0)
        return points

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.String(256))
    data = db.Column(db.LargeBinary)
    
    @staticmethod
    def get_value(key, default=None):
        item = SystemConfig.query.filter_by(key=key).first()
        if item:
            return item.value
        return default
        
    @staticmethod
    def set_value(key, value):
        item = SystemConfig.query.filter_by(key=key).first()
        if not item:
            item = SystemConfig(key=key)
            db.session.add(item)
        item.value = value
        db.session.commit()
        
    @staticmethod
    def get_data(key):
        item = SystemConfig.query.filter_by(key=key).first()
        if item:
            return item.data
        return None
        
    @staticmethod
    def set_data(key, data_blob):
        item = SystemConfig.query.filter_by(key=key).first()
        if not item:
            item = SystemConfig(key=key)
            db.session.add(item)
        item.data = data_blob
        db.session.commit()

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(64), nullable=False)
    target_table = db.Column(db.String(64))
    target_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=get_brasilia_time)
    
    user = db.relationship('User', backref=db.backref('audit_logs', lazy='dynamic'))

class AccessLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(256))
    platform = db.Column(db.String(64))
    browser = db.Column(db.String(64))
    login_time = db.Column(db.DateTime, default=get_brasilia_time)
    logout_time = db.Column(db.DateTime)
    logout_type = db.Column(db.String(20))
    
    user = db.relationship('User', backref=db.backref('access_logs', lazy='dynamic'))

class ImportJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    import_type = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')
    total_rows = db.Column(db.Integer, default=0)
    processed_rows = db.Column(db.Integer, default=0)
    errors = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_brasilia_time)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    
    tenant = db.relationship('Tenant')
    user = db.relationship('User', backref=db.backref('import_jobs', lazy='dynamic'))
    
    @property
    def progress_percentage(self):
        if not self.total_rows or self.total_rows == 0:
            return 0
        return min(int((self.processed_rows / self.total_rows) * 100), 100)
        
    @staticmethod
    def is_any_running():
        return ImportJob.query.filter_by(status='running').first() is not None

class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ibge_code = db.Column(db.String(20), unique=True, nullable=False)
    uf = db.Column(db.String(2), nullable=False)
    name = db.Column(db.String(128), nullable=False)

class Country(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ibge_code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
