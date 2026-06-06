from flask_wtf import FlaskForm
from wtforms import FloatField, DateField, StringField, TextAreaField, SelectField, BooleanField, SubmitField, FormField, FieldList, DateField, SelectMultipleField, PasswordField, IntegerField, HiddenField
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from app.models import User, Subject, TeachingUnit, Class
import re

def validate_cpf(form, field):
    cpf = field.data
    if not cpf:
        return
    
    # Remove non-digits
    cpf = re.sub(r'[^0-9]', '', cpf)
    
    if len(cpf) != 11:
        raise ValidationError('CPF deve ter 11 dígitos.')
    
    # Check for repeated digits
    if cpf == cpf[0] * len(cpf):
        raise ValidationError('CPF inválido.')
    
    # Validate digits
    for i in range(9, 11):
        value = sum((int(cpf[num]) * ((i + 1) - num) for num in range(0, i)))
        digit = ((value * 10) % 11) % 10
        if digit != int(cpf[i]):
            raise ValidationError('CPF inválido.')

class QuestionForm(FlaskForm):
    type = StringField('Tipo de Questão', validators=[DataRequired()]) # Hidden or handled by JS, but validated
    statement = TextAreaField('Enunciado', validators=[DataRequired()])
    difficulty = SelectField('Nível de Complexidade', choices=[
        ('Facil', 'Fácil'),
        ('Medio', 'Intermediário'),
        ('Dificil', 'Difícil/Complexa')
    ])
    # descriptor_code removed
    descriptors = SelectMultipleField('Descritores/Habilidades', coerce=int, validators=[DataRequired()])
    
    # Alternatives
    alt_a = TextAreaField('A', validators=[DataRequired()])
    alt_b = TextAreaField('B', validators=[DataRequired()])
    alt_c = TextAreaField('C', validators=[DataRequired()])
    alt_d = TextAreaField('D', validators=[DataRequired()])
    alt_e = TextAreaField('E', validators=[DataRequired()])
    
    correct_alternative = SelectField('Alternativa Correta', choices=[
        ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('E', 'E')
    ], validators=[DataRequired()])
    
    submit = SubmitField('Salvar Questão')

from datetime import date

class EvaluationForm(FlaskForm):
    name = StringField('Nome da Avaliação', validators=[DataRequired()])
    type = SelectField('Tipo de Avaliação', choices=[
        ('', 'Selecione...'),
        ('Diagnostica', 'Diagnóstica'),
        ('Processual', 'Processual'),
        ('Saida', 'Saída'),
        ('Indiferente', 'Indiferente')
    ], validators=[DataRequired()])
    multiple_components = SelectField('Múltiplos componentes', choices=[
        ('0', 'Não'),
        ('1', 'Sim')
    ], default='0', validators=[DataRequired()])
    logo = FileField('Logo da Avaliação', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Apenas imagens (JPG, PNG)!')
    ])
    submit = SubmitField('Salvar Avaliação')

class ExamGeneratorForm(FlaskForm):
    evaluation_id = SelectField('Avaliação', coerce=int, validators=[Optional()], choices=[])
    matrix_id = SelectField('Matriz de Referência', coerce=int, validators=[DataRequired()], choices=[])
    school_year_id = SelectField('Ano Escolar', coerce=int, validators=[DataRequired()], choices=[])
    subject_id = SelectField('Componente', coerce=int, validators=[Optional()], choices=[])
    subject_ids = SelectMultipleField('Componentes Curriculares', coerce=int, validators=[Optional()], choices=[])
    application_date = DateField('Data de Aplicação', validators=[DataRequired()])
    
    scope_type = SelectField('Abrangência', choices=[
        ('', 'Selecione...'),
        ('global', 'Todas as Escolas'),
        ('regional', 'Regional Específica'),
        ('school', 'Escolas Específicas')
    ], validators=[Optional()])
    regional_id = SelectMultipleField('Regionais', coerce=int, validators=[Optional()], choices=[])
    teaching_unit_id = SelectMultipleField('Escolas', coerce=int, validators=[Optional()], choices=[])
    target_cities = SelectMultipleField('Municípios', validators=[Optional()], choices=[])
    class_ids = SelectMultipleField('Turmas', coerce=int, validators=[Optional()], choices=[])
    descriptor_ids = SelectMultipleField('Descritores (Opcional)', coerce=int, validators=[Optional()], choices=[])
    difficulty = SelectField('Nível das questões', choices=[
        ('', 'Selecione...'),
        ('Any', 'Qualquer'),
        ('facil', 'Fácil'),
        ('medio', 'Intermediário'),
        ('dificil', 'Difícil')
    ], validators=[DataRequired()])
    quantity = SelectField('Quantidade de Questões', choices=[
        (0, 'Selecione...'), (5, '5'), (10, '10'), (15, '15'), (20, '20'), (25, '25'), (30, '30'),
        (35, '35'), (40, '40'), (45, '45'), (50, '50'), (55, '55'), (60, '60'),
        (65, '65'), (70, '70'), (75, '75'), (80, '80'), (85, '85'), (90, '90'),
        (95, '95'), (100, '100')
    ], coerce=int, validators=[DataRequired()])
    
    # Scoring options
    scoring_type = SelectField('Tipo de Pontuação', choices=[
        ('none', 'Não informar valor'),
        ('fixed', 'Valor fixo por questão'),
        ('total', 'Valor total da prova (Distribuição automática)'),
        ('per_question', 'Valor por questão')
    ], default='none')
    total_value = StringField('Valor (Total ou por Questão)', validators=[Optional()])
    
    allow_teacher_entry = BooleanField('Permitir que o professor registre as respostas dos alunos', default=True)
    
    target_nationality = SelectField('Público por Nacionalidade', choices=[
        ('Todos', 'Todos os Alunos'),
        ('Brasileiro', 'Somente Alunos de Nacionalidade Brasileira')
    ], default='Todos')
    
    special_needs_filter = SelectField('Público por Deficiência', choices=[
        ('all', 'Todos os Alunos'),
        ('only_special', 'Somente Alunos com Deficiência')
    ], default='all')

    submit = SubmitField('Gerar Prova')

    def validate_application_date(self, field):
        if field.data <= date.today():
            raise ValidationError('A data de aplicação deve ser posterior ao dia de hoje.')

class TeachingUnitForm(FlaskForm):
    type = SelectField('Tipo', choices=[('Escola', 'Escola'), ('Regional', 'Regional')], validators=[DataRequired()])
    name = StringField('Nome da Unidade', validators=[DataRequired()])
    parent_id = SelectField('Regional', coerce=int, choices=[(0, 'Nenhuma')]) # 0 for None handling
    
    inep_code = StringField('Código INEP', validators=[Length(max=20)])
    uf = SelectField('UF', choices=[('', 'Selecione...'), ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'), ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'), ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'), ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'), ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'), ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'), ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins')])
    municipio = SelectField('Município', choices=[])
    residential_zone = SelectField('Localização', choices=[
        ('', 'Selecione...'),
        ('Urbana', 'Urbana'),
        ('Rural', 'Rural')
    ])
    differentiated_location = SelectField('Localização diferenciada', choices=[
        ('', 'Selecione...'),
        ('Área de Assentamento', 'Área de Assentamento'),
        ('Terra Indígena', 'Terra Indígena'),
        ('Área remanescente de Quilombos', 'Área remanescente de Quilombos'),
        ('Unidade de Uso Sustentável', 'Unidade de Uso Sustentável'),
        ('Não se aplica', 'Não se aplica')
    ])
    latitude = StringField('Latitude', validators=[Length(max=50)])
    longitude = StringField('Longitude', validators=[Length(max=50)])
    
    submit = SubmitField('Salvar Unidade')

class SchoolYearForm(FlaskForm):
    name = StringField('Nome do Ano Escolar (Ex: 1º Ano)', validators=[DataRequired()])
    submit = SubmitField('Salvar Ano')

class SubjectForm(FlaskForm):
    name = StringField('Nome do Componente', validators=[DataRequired()])
    submit = SubmitField('Salvar Componente')

class AbsenceReasonForm(FlaskForm):
    name = StringField('Motivo', validators=[DataRequired()])
    submit = SubmitField('Salvar Motivo')

class DietaryRestrictionForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired(), Length(max=128)])
    active = BooleanField('Ativo', default=True)
    submit = SubmitField('Salvar Restrição')

# For Curriculum/Class we might need dynamic choices loaded in route, 
# but we define structure here.


class CurriculumForm(FlaskForm):
    name = StringField('Nome da Matriz', validators=[DataRequired()])
    school_year_id = SelectField('Ano Escolar', coerce=int, validators=[DataRequired()])
    subjects = SelectMultipleField('Componentes', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar Matriz')

class ClassForm(FlaskForm):
    name = StringField('Nome da Turma', validators=[DataRequired()])
    shift = SelectField('Turno', choices=[
        ('Matutino', 'Matutino'),
        ('Vespertino', 'Vespertino'),
        ('Noturno', 'Noturno'),
        ('Integral', 'Integral')
    ], validators=[DataRequired()])
    school_year_id = SelectField('Ano Escolar', coerce=int, validators=[DataRequired()])
    structure_id = SelectField('Estrutura Curricular', coerce=int, validators=[DataRequired()])
    teaching_unit_id = SelectField('Unidade de Ensino', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar Turma')

class StudentForm(FlaskForm):
    name = StringField('Nome Completo', validators=[DataRequired()])
    email = StringField('E-mail', validators=[Optional(), Email()])
    cpf = StringField('CPF', validators=[DataRequired(), validate_cpf]) # Formatted loop in template
    sex = SelectField('Sexo', choices=[
        ('Masculino', 'Masculino'),
        ('Feminino', 'Feminino')
    ], validators=[DataRequired()])
    race = SelectField('Cor/Raça', choices=[
        ('Branca', 'Branca'),
        ('Preta', 'Preta'),
        ('Parda', 'Parda'),
        ('Amarela', 'Amarela'),
        ('Indigena', 'Indígena'),
        ('Nao declarada', 'Não declarada')
    ], validators=[DataRequired()])
    
    birth_date = DateField('Data de Nascimento', format='%Y-%m-%d', validators=[DataRequired()])
    
    nationality = SelectField('Nacionalidade', choices=[
        ('Brasileiro', 'Brasileiro'),
        ('Estrangeiro', 'Estrangeiro'),
        ('Brasileiro - naturalizado', 'Brasileiro - naturalizado')
    ], default='Brasileiro')
    birth_country = SelectField('País de Nascimento', choices=[], default='Brasil')
    special_needs = SelectField('Possui Deficiência', choices=[
        (False, 'Não'),
        (True, 'Sim')
    ], coerce=lambda x: str(x).lower() == 'true', default=False)
    family_income = SelectField('Renda Familiar', choices=[
        ('', 'Não informar'),
        ('Ate 1 SM', 'Até 1 Salário Mínimo'),
        ('1 a 2 SM', '1 a 2 Salários Mínimos'),
        ('2 a 5 SM', '2 a 5 Salários Mínimos'),
        ('5 a 10 SM', '5 a 10 Salários Mínimos'),
        ('Mais de 10 SM', 'Mais de 10 Salários Mínimos')
    ], default='')
    
    inep_code = StringField('Código INEP', validators=[Optional(), Length(max=12)])
    sus_card = StringField('Cartão SUS', validators=[Optional(), Length(max=15)])
    
    bolsa_familia = SelectField('Bolsa Família', choices=[
        (False, 'Não'),
        (True, 'Sim')
    ], coerce=lambda x: str(x).lower() == 'true', default=False)
    
    birth_state = SelectField('UF Naturalidade', choices=[
        ('', 'Selecione...'),
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
        ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
        ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
        ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
        ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
        ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins')
    ], validators=[Optional()])
    
    birth_city_id = SelectField('Naturalidade (Município)', coerce=int, choices=[(0, 'Selecione...')], validators=[Optional()])
    
    residential_zone = SelectField('Zona Residencial', choices=[
        ('', 'Selecione...'),
        ('Urbana', 'Urbana'),
        ('Rural', 'Rural')
    ], validators=[Optional()])
    
    differentiated_location = SelectField('Localização Diferenciada de Residência', choices=[
        ('Não está em área de localização diferenciada', 'Não está em área de localização diferenciada'),
        ('Área de assentamento', 'Área de assentamento'),
        ('Terra indígena', 'Terra indígena'),
        ('Comunidade quilombola', 'Comunidade quilombola'),
        ('Área onde se localizam povos e comunidades tradicionais', 'Área onde se localizam povos e comunidades tradicionais')
    ], default='Não está em área de localização diferenciada', validators=[Optional()])
    
    is_quilombola = BooleanField('É Quilombola?', default=False)
    quilombola_community_id = SelectField('Comunidade Quilombola', coerce=int, choices=[(0, 'Selecione...')], validators=[Optional()])
    indigenous_people_id = SelectField('Povo Indígena', coerce=int, choices=[(0, 'Selecione...')], validators=[Optional()])
    
    # Mandatory enrollment fields
    teaching_unit_id = SelectField('Escola', coerce=int, validators=[DataRequired()])
    class_id = SelectField('Turma', coerce=int, validators=[DataRequired()])
    
    dietary_restrictions = SelectMultipleField('Restrições Alimentares', coerce=int, validators=[Optional()])
    
    generate_user = BooleanField('Gerar Usuário e Senha (CPF/Data Nasc.)')
    
    submit = SubmitField('Salvar Aluno')

class ProfessorForm(FlaskForm):
    name = StringField('Nome Completo', validators=[DataRequired()])
    email = StringField('E-mail', validators=[Optional(), Email()])
    cpf = StringField('CPF', validators=[DataRequired(), validate_cpf])
    sex = SelectField('Sexo', choices=[
        ('Masculino', 'Masculino'),
        ('Feminino', 'Feminino')
    ], validators=[DataRequired()])
    race = SelectField('Cor/Raça', choices=[
        ('Branca', 'Branca'),
        ('Preta', 'Preta'),
        ('Parda', 'Parda'),
        ('Amarela', 'Amarela'),
        ('Indigena', 'Indígena'),
        ('Nao declarada', 'Não declarada')
    ], validators=[DataRequired()])
    birth_date = DateField('Data de Nascimento', format='%Y-%m-%d', validators=[DataRequired()])
    
    nationality = SelectField('Nacionalidade', choices=[
        ('Brasileiro', 'Brasileiro'),
        ('Estrangeiro', 'Estrangeiro'),
        ('Brasileiro - naturalizado', 'Brasileiro - naturalizado')
    ], default='Brasileiro')
    birth_country = SelectField('País de Nascimento', choices=[], default='Brasil')
    
    inep_code = StringField('Código INEP', validators=[Optional(), Length(max=12)])
    sus_card = StringField('Cartão SUS', validators=[Optional(), Length(max=15)])
    
    birth_state = SelectField('UF Naturalidade', choices=[
        ('', 'Selecione...'),
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
        ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
        ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
        ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
        ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
        ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins')
    ], validators=[Optional()])
    
    birth_city_id = SelectField('Naturalidade (Município)', coerce=int, choices=[(0, 'Selecione...')], validators=[Optional()])
    
    residential_zone = SelectField('Zona Residencial', choices=[
        ('', 'Selecione...'),
        ('Urbana', 'Urbana'),
        ('Rural', 'Rural')
    ], validators=[Optional()])
    
    differentiated_location = SelectField('Localização Diferenciada de Residência', choices=[
        ('Não está em área de localização diferenciada', 'Não está em área de localização diferenciada'),
        ('Área de assentamento', 'Área de assentamento'),
        ('Terra indígena', 'Terra indígena'),
        ('Comunidade quilombola', 'Comunidade quilombola'),
        ('Área onde se localizam povos e comunidades tradicionais', 'Área onde se localizam povos e comunidades tradicionais')
    ], default='Não está em área de localização diferenciada', validators=[Optional()])
    
    # Assignment - JSON string handling
    assignments_data = HiddenField('Assignments Data') # JSON: [{school_id, class_id, subject_id}]
    
    # UI Helpers (not data)
    teaching_unit_id = SelectField('Escola', coerce=int, validators=[Optional()])
    
    generate_user = BooleanField('Gerar Usuário e Senha (CPF/Data Nasc.)')
    
    submit = SubmitField('Salvar Professor')

class EnrollmentForm(FlaskForm):
    class_id = SelectField('Turma', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Matricular')

class ReferenceMatrixForm(FlaskForm):
    name = StringField('Nome da Matriz', validators=[DataRequired()])
    description = TextAreaField('Descrição')
    submit = SubmitField('Salvar Matriz')

class ThemeForm(FlaskForm):
    name = StringField('Nome do Tema', validators=[DataRequired()])
    matrix_id = SelectField('Matriz de Referência', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar Tema')

# class DescriptorForm(FlaskForm):
class DescriptorForm(FlaskForm):
    type = SelectField('Tipo', choices=[
        ('', 'Selecione...'),
        ('Descritor', 'Descritor'),
        ('Habilidade', 'Habilidade')
    ], validators=[DataRequired()])
    
    code = StringField('Código (Ex: D1)', validators=[DataRequired()])
    description = TextAreaField('Descrição', validators=[DataRequired()])
    
    # New Fields
    school_year_id = SelectField('Ano Escolar', coerce=int, validators=[DataRequired()])
    subject_id = SelectField('Componente', coerce=int, validators=[DataRequired()])
    
    matrix_id = SelectField('Matriz de Referência', coerce=int, validators=[DataRequired()])
    theme_id = SelectField('Tema', coerce=int, validators=[Optional()]) # Validated manually based on type
    submit = SubmitField('Salvar Descritor')

class ImportClassForm(FlaskForm):
    file = FileField('Arquivo Excel (.xlsx)', validators=[
        DataRequired(),
        FileAllowed(['xlsx', 'xls'], 'Apenas arquivos Excel são permitidos.')
    ])
    submit = SubmitField('Importar')

class QuilombolaCommunityForm(FlaskForm):
    name = StringField('Nome da Comunidade', validators=[DataRequired()])
    submit = SubmitField('Salvar Comunidade')

class IndigenousPeopleForm(FlaskForm):
    name = StringField('Nome do Povo', validators=[DataRequired()])
    submit = SubmitField('Salvar Povo Indígena')

class ImportDefinitionForm(FlaskForm):
    file = FileField('Arquivo Excel (.xlsx)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls'], 'Apenas arquivos Excel são permitidos.')
    ])
    submit = SubmitField('Importar')

class ImportUnitForm(FlaskForm):
    file = FileField('Arquivo Excel (.xlsx)', validators=[
        FileRequired(),
        FileAllowed(['xlsx'], 'Apenas arquivos Excel!')
    ])
    submit = SubmitField('Importar Unidades')

class ImportDietaryRestrictionForm(FlaskForm):
    file = FileField('Arquivo Excel (.xlsx)', validators=[
        FileRequired(),
        FileAllowed(['xlsx'], 'Apenas arquivos Excel!')
    ])
    submit = SubmitField('Importar Restrições')

class ImportDescriptorForm(FlaskForm):
    file = FileField('Arquivo (.csv, .xlsx)', validators=[
        FileRequired(),
        FileAllowed(['csv', 'xlsx'], 'Apenas arquivos CSV ou Excel!')
    ])
    submit = SubmitField('Importar Arquivo')

class ImportQuestionForm(FlaskForm):
    file = FileField('Arquivo Excel (.xlsx)', validators=[
        FileRequired(),
        FileAllowed(['xlsx'], 'Apenas arquivos Excel!')
    ])
    submit = SubmitField('Importar Questões')

class SystemSettingsForm(FlaskForm):
    system_name = StringField('Nome do Sistema', validators=[DataRequired()])
    logo = FileField('Logo do Sistema', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Apenas imagens (JPG, PNG, GIF)!')
    ])
    login_background = FileField('Imagem de Fundo Módulo Login', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Apenas imagens (JPG, PNG, GIF)!')
    ])
    favicon = FileField('Favicon do Sistema', validators=[
        FileAllowed(['ico', 'png'], 'Apenas imagens (ICO, PNG)!')
    ])
    
    # SMTP Settings
    smtp_server = StringField('Servidor SMTP', validators=[Optional()])
    smtp_port = IntegerField('Porta SMTP', validators=[Optional()])
    smtp_user = StringField('Usuário SMTP', validators=[Optional()])
    smtp_password = PasswordField('Senha SMTP', validators=[Optional()])
    smtp_security = SelectField('Segurança', choices=[
        ('none', 'Nenhuma'),
        ('tls', 'TLS'),
        ('ssl', 'SSL')
    ], validators=[Optional()])
    smtp_sender = StringField('E-mail Remetente', validators=[Optional()])
    
    submit = SubmitField('Salvar Configurações')

class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember = BooleanField('Lembrar-me')
    submit = SubmitField('Entrar')

class UserForm(FlaskForm):
    name = StringField('Nome Completo', validators=[Optional(), Length(max=128)])
    username = StringField('Usuário', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('E-mail', validators=[Optional(), Email(), Length(max=120)])
    password = PasswordField('Senha', validators=[Length(min=6)]) # Optional in edit handled in route
    # Updated to SelectMultiple for roles
    roles = SelectMultipleField('Perfis de Acesso', choices=[
        ('admin', 'Administrador'),
        ('regional_manager', 'Gestor Regional'),
        ('professor', 'Professor'),
        ('student', 'Aluno'),
        ('unidade', 'Unidade')
    ], validators=[DataRequired()])
    teaching_unit_ids = SelectMultipleField('Unidades Escolares', coerce=int, validators=[Optional()], choices=[])
    regional = StringField('Regional (Opcional)')
    active = BooleanField('Ativo', default=True)
    tenant_id = SelectField('Cliente', coerce=int, validators=[Optional()], choices=[])
    submit = SubmitField('Salvar Usuário')

    def validate_username(self, username):
        # Logic to be handled in route to differentiate create/edit or here with ID context
        pass 

class RequestPasswordResetForm(FlaskForm):
    # Field renamed to identifier to be generic
    identifier = StringField('Usuário ou E-mail', validators=[DataRequired()])
    submit = SubmitField('Enviar Link de Recuperação')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nova Senha', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Redefinir Senha')

class TenantForm(FlaskForm):
    name = StringField('Nome do Cliente', validators=[DataRequired(), Length(max=255)])
    type = SelectField('Tipo', choices=[
        ('', 'Selecione...'),
        ('Estadual', 'Estadual'),
        ('Municipal', 'Municipal')
    ], validators=[DataRequired()])
    uf = SelectField('UF', choices=[('', 'Selecione a UF')], validators=[Optional()])
    municipio = SelectField('Município', choices=[('', 'Selecione o Município')], validators=[Optional()])
    map_url = StringField('URL para o arquivo GeoJSON que você deseja usar', validators=[Optional(), Length(max=512)])
    submit = SubmitField('Salvar Cliente')

    def validate(self, extra_validators=None):
        initial_validation = super(TenantForm, self).validate(extra_validators=extra_validators)
        if not initial_validation:
            return False
            
        success = True
        if self.type.data == 'Estadual':
            if not self.uf.data:
                self.uf.errors.append('UF é obrigatório para clientes Estaduais.')
                success = False
        elif self.type.data == 'Municipal':
            if not self.uf.data:
                self.uf.errors.append('UF é obrigatório para clientes Municipais.')
                success = False
            if not self.municipio.data:
                self.municipio.errors.append('Município é obrigatório para clientes Municipais.')
                success = False
                
        return success


class AnthropometricForm(FlaskForm):
    date = DateField('Data da Aferição', validators=[DataRequired()])
    weight = FloatField('Peso (Kg)', validators=[DataRequired()])
    height = FloatField('Altura (cm)', validators=[DataRequired()])
    submit = SubmitField('Salvar')

class AnthropometricBatchForm(FlaskForm):
    regional_id = SelectField('Regional', coerce=int, validators=[DataRequired()], choices=[])
    teaching_unit_id = SelectField('Unidade de Ensino', coerce=int, validators=[DataRequired()], choices=[])
    class_id = SelectField('Turma', coerce=int, validators=[DataRequired()], choices=[])
    date = DateField('Data da Aferição', validators=[DataRequired()])
    submit = SubmitField('Buscar Turma')
