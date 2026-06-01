Created At: 2026-05-29T16:57:35Z
Completed At: 2026-05-29T16:57:37Z
The following changes were made by the multi_replace_file_content tool to: c:\Users\pc\source\sgeplus\app\models.py. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -110,6 +110,9 @@
 
 class ReferenceMatrix(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
+    
+    tenant = db.relationship('Tenant')
     name = db.Column(db.String(128), nullable=False) # e.g. "SAEB - Português 9º Ano"
     description = db.Column(db.String(256))
     descriptors = db.relationship('Descriptor', backref='matrix', lazy='dynamic')
@@ -128,6 +128,9 @@
 
 class Theme(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
+    
+    tenant = db.relationship('Tenant')
     name = db.Column(db.String(128), nullable=False)
     matrix_id = db.Column(db.Integer, db.ForeignKey('reference_matrix.id'), nullable=False)
     descriptors = db.relationship('Descriptor', backref='theme', lazy='dynamic')
@@ -134,5 +134,8 @@
 class Descriptor(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
+    
+    tenant = db.relationship('Tenant')
     code = db.Column(db.String(20), nullable=False) # e.g., D1
     type = db.Column(db.String(20)) # 'Descritor' or 'Habilidade'
     description = db.Column(db.String(256), nullable=False)
@@ -312,6 +312,9 @@
 
 class AbsenceReason(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
+    
+    tenant = db.relationship('Tenant')
     name = db.Column(db.String(128), nullable=False, unique=True)
 
 # Academic Management Models
@@ -367,6 +367,9 @@
 
 class SchoolYear(db.Mod
<truncated 344 bytes>
kref='school_year', lazy='dynamic')
     classes = db.relationship('Class', backref='school_year', lazy='dynamic')
@@ -373,5 +373,8 @@
 class Subject(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
+    
+    tenant = db.relationship('Tenant')
     name = db.Column(db.String(128), nullable=False, unique=True)
 
 # Association table for Curriculum <-> Subject
@@ -381,6 +381,9 @@
 
 class CurriculumStructure(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
+    
+    tenant = db.relationship('Tenant')
     name = db.Column(db.String(128), nullable=False)
     school_year_id = db.Column(db.Integer, db.ForeignKey('school_year.id'), nullable=False)
     subjects = db.relationship('Subject', secondary=curriculum_subjects, lazy='subquery',
@@ -473,6 +473,9 @@
 
 class DietaryRestriction(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
+    
+    tenant = db.relationship('Tenant')
     name = db.Column(db.String(128), nullable=False, unique=True)
     active = db.Column(db.Boolean, default=True, server_default='1', nullable=False)
 
@@ -612,6 +612,9 @@
 
 class ImportJob(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)
+    
+    tenant = db.relationship('Tenant')
     user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
     import_type = db.Column(db.String(50), nullable=False) # 'Units', 'Classes', 'Questions'
     filename = db.Column(db.String(255))
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.