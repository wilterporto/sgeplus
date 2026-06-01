Created At: 2026-05-29T16:57:20Z
Completed At: 2026-05-29T16:57:20Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/models.py`
Total Lines: 658
Total Bytes: 29198
Showing lines 110 to 165
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
110: 
111: class ReferenceMatrix(db.Model):
112:     id = db.Column(db.Integer, primary_key=True)
113:     name = db.Column(db.String(128), nullable=False) # e.g. "SAEB - Português 9º Ano"
114:     description = db.Column(db.String(256))
115:     descriptors = db.relationship('Descriptor', backref='matrix', lazy='dynamic')
116:     themes = db.relationship('Theme', backref='matrix', lazy='dynamic')
117: 
118:     @property
119:     def questions_count(self):
120:         # Use a subquery or direct SQL to avoid class definition order issues
121:         from sqlalchemy import text
122:         result = db.session.execute(
123:             text("SELECT COUNT(DISTINCT qd.question_id) FROM question_descriptors qd "
124:                  "JOIN descriptor d ON qd.descriptor_id = d.id "
125:                  "WHERE d.matrix_id = :matrix_id"),
126:             {'matrix_id': self.id}
127:         ).scalar()
128:         return result or 0
129: 
130: class Theme(db.Model):
131:     id = db.Column(db.Integer, primary_key=True)
132:     name = db.Column(db.String(128), nullable=False)
133:     matrix_id = db.Column(db.Integer, db.ForeignKey('reference_matrix.id'), nullable=False)
134:     descriptors = db.relationship('Descriptor', backref='theme', lazy='dynamic')
135: 
136: class Descriptor(db.Model):
137:     id = db.Column(db.Integer, primary_key=True)
138:     code = db.Column(db.String(20), nullable=False) # e.g., D1
139:     type = db.Column(db.String(20)) # 'Descritor' or 'Habilidade'
140:     description = db.Column(db.String(256), nullable=False)
141:     # subject legacy string replaced/complemented by ID
142:     subject_legacy = db.Column(db.String(64)) 
143:     
144:     matrix_id = db.Column(db.Integer, db.ForeignKey('reference_matrix.id'), nullable=True)
145:     
146:     # New Mandatory Fields
147:     school_year_id = db.Column(db.Integer, db.ForeignKey('school_year.id'), nullable=True) # Nullable for migration
148:     subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True) # Nullable for migration
149:     is_active = db.Column(db.Boolean, default=True)
150:     theme_id = db.Column(db.Integer, db.ForeignKey('theme.id'), nullable=True) # Nullable for migration, but enforced in form
151:     
152:     # Relationships
153:     school_year = db.relationship('SchoolYear')
154:     subject = db.relationship('Subject')
155:     
156:     # questions relationship is now M2M, backref defined in Question
157: 
158: # Association table for Question <-> Descriptor
159: question_descriptors = db.Table('question_descriptors',
160:     db.Column('question_id', db.Integer, db.ForeignKey('question.id'), primary_key=True),
161:     db.Column('descriptor_id', db.Integer, db.ForeignKey('descriptor.id'), primary_key=True)
162: )
163: 
164: question_unit_validations = db.Table('question_unit_validations',
165:     db.Column('question_id', db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True),
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
