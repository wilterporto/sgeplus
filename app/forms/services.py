from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from wtforms import StringField, SubmitField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError

class SupplierForm(FlaskForm):
    type = SelectField('Tipo', choices=[('PJ', 'Pessoa Jurídica'), ('PF', 'Pessoa Física')], validators=[DataRequired()])
    cpf_cnpj = StringField('CPF / CNPJ', validators=[DataRequired(), Length(max=20)])
    name = StringField('Nome / Razão Social', validators=[DataRequired(), Length(max=255)])
    email = StringField('E-mail de Contato', validators=[Optional(), Email(), Length(max=120)])
    phone = StringField('Telefone', validators=[Optional(), Length(max=20)])
    active = BooleanField('Ativo', default=True)
    submit = SubmitField('Salvar Fornecedor')

class SupplierContactForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired(), Length(max=128)])
    cpf = StringField('CPF', validators=[DataRequired(), Length(min=11, max=18)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField('Salvar Responsável')

class ServiceTypeForm(FlaskForm):
    name = StringField('Nome do Serviço', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Descrição')
    active = BooleanField('Ativo', default=True)
    submit = SubmitField('Salvar Tipo de Serviço')

class ServiceOrderForm(FlaskForm):
    school_id = SelectField('Escola (Unidade)', coerce=int, validators=[DataRequired()])
    service_type_id = SelectField('Serviço Necessário', coerce=int, validators=[DataRequired()])
    description = TextAreaField('Descrição Detalhada do Problema', validators=[DataRequired()])
    photos = MultipleFileField('Anexar Fotos', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Apenas imagens JPG ou PNG são permitidas!')
    ])
    submit = SubmitField('Solicitar Serviço')

class ScheduleServiceOrderForm(FlaskForm):
    scheduled_date = StringField('Data de Atendimento', validators=[Optional()])
    status = SelectField('Status', choices=[
        ('Pendente', 'Pendente'), 
        ('Agendado', 'Agendado'), 
        ('Em Andamento', 'Em Andamento'), 
        ('Concluído', 'Concluído'), 
        ('Cancelado', 'Cancelado')
    ], validators=[DataRequired()])
    supplier_id = SelectField('Fornecedor Designado', coerce=int, validators=[Optional()])
    submit = SubmitField('Atualizar Ordem de Serviço')
