from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, SelectMultipleField, PasswordField, SubmitField, DateField, FloatField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Length, EqualTo, Optional, ValidationError
from datetime import date

class LMSUserProfileForm(FlaskForm):
    social_name = StringField('Nome Social', validators=[Length(max=128)])
    show_email = BooleanField('Exibir E-mail publicamente')
    image = FileField('Foto de Perfil', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Apenas imagens (JPG, PNG)!')
    ])
    description = TextAreaField('Apresentação / Biografia')
    
    current_password = PasswordField('Senha Atual')
    new_password = PasswordField('Nova Senha', validators=[
        Optional(), Length(min=8, message='A senha deve ter no mínimo 8 caracteres.')
    ])
    confirm_password = PasswordField('Confirmar Nova Senha', validators=[
        EqualTo('new_password', message='As senhas não coincidem.')
    ])
    submit = SubmitField('Salvar Perfil')

class LMSCategoryForm(FlaskForm):
    name = StringField('Nome da Categoria', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Descrição')
    visible = BooleanField('Visível no Catálogo', default=True)
    coordinators = SelectMultipleField('Coordenadores', coerce=int, validators=[Optional()])
    submit = SubmitField('Salvar Categoria')

class LMSSubjectForm(FlaskForm):
    category_id = SelectField('Categoria', coerce=int, validators=[DataRequired()])
    name = StringField('Nome da Disciplina', validators=[DataRequired(), Length(max=128)])
    description_brief = TextAreaField('Descrição Resumida')
    description = TextAreaField('Descrição Completa')
    
    subscribe_begin = DateField('Início das Inscrições', validators=[DataRequired()])
    subscribe_end = DateField('Fim das Inscrições', validators=[DataRequired()])
    init_date = DateField('Início das Aulas', validators=[DataRequired()])
    end_date = DateField('Término das Aulas', validators=[DataRequired()])
    
    visible = BooleanField('Visível para Alunos', default=True)
    tags = StringField('Marcadores (Tags separadas por vírgula)')
    price = FloatField('Valor (R$)', validators=[Optional()])
    display_avatar = BooleanField('Exibir Imagem', default=True)
    external_access = BooleanField('Acesso Externo', default=False)
    
    professors = SelectMultipleField('Professores', coerce=int, validators=[Optional()])
    submit = SubmitField('Salvar Disciplina')

    def validate_subscribe_end(self, field):
        if self.subscribe_begin.data and field.data < self.subscribe_begin.data:
            raise ValidationError('O fim das inscrições deve ser igual ou posterior ao início.')

    def validate_init_date(self, field):
        if self.subscribe_end.data and field.data < self.subscribe_end.data:
            raise ValidationError('O início das aulas deve ser após o término das inscrições.')

    def validate_end_date(self, field):
        if self.init_date.data and field.data < self.init_date.data:
            raise ValidationError('O término das aulas deve ser igual ou posterior ao início das aulas.')


class LMSStudentGroupForm(FlaskForm):
    subject_id = SelectField('Disciplina', coerce=int, validators=[DataRequired()])
    name = StringField('Nome do Grupo', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Descrição')
    participants = SelectMultipleField('Participantes', coerce=int, validators=[Optional()])
    submit = SubmitField('Salvar Grupo')

class LMSTopicForm(FlaskForm):
    subject_id = SelectField('Disciplina', coerce=int, validators=[DataRequired()])
    name = StringField('Título do Tópico', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Conteúdo / Apresentação')
    repository = BooleanField('Tópico Repositório (Apenas 1 por disciplina)')
    visible = BooleanField('Visível aos Alunos', default=True)
    submit = SubmitField('Salvar Tópico')

class LMSMuralPostForm(FlaskForm):
    action = SelectField('Tipo de Postagem', choices=[('comment', 'Comentário / Dúvida'), ('help', 'Pedido de Ajuda')], validators=[DataRequired()])
    post = TextAreaField('Mensagem', validators=[DataRequired()])
    image = FileField('Anexar Imagem (Opcional)', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Apenas imagens (JPG, PNG)!')
    ])
    submit = SubmitField('Publicar')

class LMSMuralCommentForm(FlaskForm):
    comment = TextAreaField('Seu Comentário', validators=[DataRequired()])
    image = FileField('Anexar Imagem (Opcional)', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Apenas imagens (JPG, PNG)!')
    ])
    submit = SubmitField('Responder')

class LMSResourceForm(FlaskForm):
    topic_id = SelectField('Tópico', coerce=int, validators=[DataRequired()])
    type = SelectField('Tipo de Recurso', choices=[
        ('html', 'Página HTML / Texto Rico'),
        ('youtube', 'Vídeo do YouTube'),
        ('file', 'Arquivo para Download'),
        ('pdf', 'Documento PDF (Visualização na Tela)'),
        ('link', 'Link Externo')
    ], validators=[DataRequired()])
    
    name = StringField('Nome do Recurso', validators=[DataRequired(), Length(max=255)])
    brief_description = TextAreaField('Descrição Curta')
    
    content = TextAreaField('Conteúdo HTML')
    url = StringField('URL (YouTube ou Link Externo)', validators=[Length(max=512)])
    file = FileField('Arquivo (PDF ou outros)', validators=[
        FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'jpg', 'png', 'mp4'], 'Arquivo não permitido.')
    ])
    
    show_window = BooleanField('Exibir na mesma janela (Para PDF/HTML)')
    all_students = BooleanField('Visível para todos os alunos matriculados', default=True)
    visible = BooleanField('Recurso Ativo', default=True)
    
    groups = SelectMultipleField('Restringir a Grupos Específicos', coerce=int, validators=[Optional()])
    tags = StringField('Tags / Marcadores (separados por vírgula)')
    
    submit = SubmitField('Salvar Recurso')

class LMSGoalForm(FlaskForm):
    subject_id = SelectField('Disciplina', coerce=int, validators=[DataRequired()])
    name = StringField('Nome da Meta', validators=[DataRequired(), Length(max=255)])
    presentation = TextAreaField('Apresentação', validators=[DataRequired()])
    brief_description = TextAreaField('Descrição Curta')
    init_date = DateField('Data de Início', validators=[DataRequired()])
    limit_submission_date = DateField('Data Limite de Submissão', validators=[DataRequired()])
    visible = BooleanField('Ativa e Visível', default=True)
    submit = SubmitField('Salvar Meta')

class LMSGoalItemForm(FlaskForm):
    description = StringField('Descrição da Tarefa', validators=[DataRequired(), Length(max=255)])
    ref_value = StringField('Valor de Referência (ex: 50%, 10 pontos)', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Adicionar Item')

class LMSEvaluationForm(FlaskForm):
    subject_id = SelectField('Disciplina', coerce=int, validators=[DataRequired()])
    name = StringField('Nome da Avaliação', validators=[DataRequired(), Length(max=255)])
    type = SelectField('Tipo de Avaliação', choices=[
        ('diagnostica', 'Diagnóstica'),
        ('processual', 'Processual'),
        ('saida', 'Saída'),
        ('indiferente', 'Indiferente')
    ], validators=[DataRequired()])
    date = DateField('Data da Avaliação', validators=[DataRequired()])
    visible = BooleanField('Visível aos Alunos', default=True)
    submit = SubmitField('Salvar Avaliação')


