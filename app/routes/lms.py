from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import LMSCategory, LMSSubject, LMSStudentGroup, LMSTopic, User, LMSMuralPost, LMSMuralComment, LMSResource, LMSGoal, LMSGoalItem, LMSEvaluation, LMSQuestion, LMSStudentGrade, LMSImportJob
from app.forms_lms import LMSCategoryForm, LMSSubjectForm, LMSStudentGroupForm, LMSTopicForm, LMSUserProfileForm, LMSMuralPostForm, LMSMuralCommentForm, LMSResourceForm, LMSGoalForm, LMSGoalItemForm, LMSEvaluationForm
import threading
import pandas as pd
import os
from werkzeug.utils import secure_filename
from flask import current_app

lms_bp = Blueprint('lms', __name__, url_prefix='/lms')

# --- Profile ---

@lms_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = LMSUserProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.social_name = form.social_name.data
        current_user.show_email = form.show_email.data
        current_user.description = form.description.data
        
        # Save image securely if provided (requires werkzeug.utils.secure_filename in a full implementation)
        if form.image.data:
            # Here you would add logic to securely save the file, resize to 200x200, etc.
            flash('Upload de imagem será processado em breve.', 'info')
            
        if form.current_password.data and form.new_password.data:
            if current_user.check_password(form.current_password.data):
                current_user.set_password(form.new_password.data)
                flash('Senha atualizada com sucesso.', 'success')
            else:
                flash('Senha atual incorreta.', 'danger')
                return render_template('lms/profile.html', form=form)
                
        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('lms.profile'))
        
    return render_template('lms/profile.html', form=form)


# --- Workflow (Guia de Uso) ---

@lms_bp.route('/workflow', methods=['GET'])
@login_required
def workflow():
    return render_template('lms/workflow.html')

@lms_bp.route('/public_portal', methods=['GET'])
def public_portal():
    # Exibe disciplinas que possuem acesso externo/público ou redireciona para login
    return render_template('lms/public_portal.html')

# --- Categories ---

@lms_bp.route('/categories', methods=['GET'])
@login_required
def list_categories():
    page = request.args.get('page', 1, type=int)
    categories = LMSCategory.query.order_by(LMSCategory.name).paginate(page=page, per_page=30)
    return render_template('lms/categories_list.html', categories=categories)

@lms_bp.route('/categories/create', methods=['GET', 'POST'])
@login_required
def create_category():
    form = LMSCategoryForm()
    # Populate coordinators with admin/staff users (example)
    form.coordinators.choices = [(u.id, u.name) for u in User.query.filter(User.roles.contains('admin')).all()]
    
    if form.validate_on_submit():
        category = LMSCategory(
            name=form.name.data,
            description=form.description.data,
            visible=form.visible.data
        )
        if form.coordinators.data:
            category.coordinators = User.query.filter(User.id.in_(form.coordinators.data)).all()
        
        db.session.add(category)
        db.session.commit()
        flash('Categoria criada com sucesso!', 'success')
        return redirect(url_for('lms.list_categories'))
        
    return render_template('lms/category_form.html', form=form)

@lms_bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    category = LMSCategory.query.get_or_404(id)
    try:
        db.session.delete(category)
        db.session.commit()
        flash('Categoria excluída com sucesso.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Erro: Não é possível excluir a categoria pois existem disciplinas vinculadas a ela.', 'danger')
    return redirect(url_for('lms.list_categories'))


# --- Subjects / Courses ---

@lms_bp.route('/subjects', methods=['GET'])
@login_required
def list_subjects():
    page = request.args.get('page', 1, type=int)
    subjects = LMSSubject.query.order_by(LMSSubject.name).paginate(page=page, per_page=30)
    return render_template('lms/subjects_list.html', subjects=subjects)

@lms_bp.route('/subjects/create', methods=['GET', 'POST'])
@login_required
def create_subject():
    form = LMSSubjectForm()
    form.category_id.choices = [(c.id, c.name) for c in LMSCategory.query.order_by(LMSCategory.name).all()]
    form.professors.choices = [(u.id, u.name) for u in User.query.filter(User.roles.contains('professor')).all()]
    
    if form.validate_on_submit():
        subject = LMSSubject(
            category_id=form.category_id.data,
            name=form.name.data,
            description_brief=form.description_brief.data,
            description=form.description.data,
            subscribe_begin=form.subscribe_begin.data,
            subscribe_end=form.subscribe_end.data,
            init_date=form.init_date.data,
            end_date=form.end_date.data,
            visible=form.visible.data,
            tags=form.tags.data,
            price=form.price.data,
            display_avatar=form.display_avatar.data,
            external_access=form.external_access.data
        )
        if form.professors.data:
            subject.professors = User.query.filter(User.id.in_(form.professors.data)).all()
            
        db.session.add(subject)
        db.session.commit()
        flash('Disciplina criada com sucesso!', 'success')
        return redirect(url_for('lms.list_subjects'))
        
    return render_template('lms/subject_form.html', form=form)

@lms_bp.route('/subjects/<int:id>/delete', methods=['POST'])
@login_required
def delete_subject(id):
    subject = LMSSubject.query.get_or_404(id)
    try:
        db.session.delete(subject)
        db.session.commit()
        flash('Disciplina excluída com sucesso.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Erro: Não é possível excluir a disciplina pois existem dados dependentes vinculados.', 'danger')
    return redirect(url_for('lms.list_subjects'))


# --- Student Groups ---

@lms_bp.route('/student_groups', methods=['GET'])
@login_required
def list_student_groups():
    page = request.args.get('page', 1, type=int)
    groups = LMSStudentGroup.query.order_by(LMSStudentGroup.name).paginate(page=page, per_page=30)
    # The template might not exist, but we will create a basic one or just handle it if it crashes later
    return render_template('lms/student_groups_list.html', groups=groups)

@lms_bp.route('/student_groups/create', methods=['GET', 'POST'])
@login_required
def create_student_group():
    form = LMSStudentGroupForm()
    form.subject_id.choices = [(s.id, s.name) for s in LMSSubject.query.order_by(LMSSubject.name).all()]
    
    if form.validate_on_submit():
        group = LMSStudentGroup(
            subject_id=form.subject_id.data,
            name=form.name.data,
            description=form.description.data,
            limit_students=form.limit_students.data
        )
        db.session.add(group)
        db.session.commit()
        flash('Turma (Grupo) criada com sucesso!', 'success')
        return redirect(url_for('lms.list_student_groups'))
        
    return render_template('lms/student_group_form.html', form=form)

@lms_bp.route('/student_groups/<int:id>/delete', methods=['POST'])
@login_required
def delete_student_group(id):
    group = LMSStudentGroup.query.get_or_404(id)
    try:
        db.session.delete(group)
        db.session.commit()
        flash('Turma (Grupo) excluída com sucesso.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Erro: Não é possível excluir pois existem dependências.', 'danger')
    return redirect(url_for('lms.list_student_groups'))


# --- Topics ---

@lms_bp.route('/topics', methods=['GET'])
@login_required
def list_topics():
    page = request.args.get('page', 1, type=int)
    topics = LMSTopic.query.order_by(LMSTopic.name).paginate(page=page, per_page=30)
    return render_template('lms/topics_list.html', topics=topics)

@lms_bp.route('/topics/create', methods=['GET', 'POST'])
@login_required
def create_topic():
    form = LMSTopicForm()
    form.subject_id.choices = [(s.id, s.name) for s in LMSSubject.query.order_by(LMSSubject.name).all()]
    
    if form.validate_on_submit():
        if form.repository.data:
            existing_repo = LMSTopic.query.filter_by(subject_id=form.subject_id.data, repository=True).first()
            if existing_repo:
                flash('Já existe um tópico repositório para esta disciplina. Apenas 1 é permitido.', 'danger')
                return render_template('lms/topic_form.html', form=form)
                
        topic = LMSTopic(
            subject_id=form.subject_id.data,
            name=form.name.data,
            description=form.description.data,
            repository=form.repository.data,
            visible=form.visible.data
        )
        db.session.add(topic)
        db.session.commit()
        flash('Tópico criado com sucesso!', 'success')
        return redirect(url_for('lms.list_topics'))
        
    return render_template('lms/topic_form.html', form=form)

@lms_bp.route('/topics/<int:id>/delete', methods=['POST'])
@login_required
def delete_topic(id):
    topic = LMSTopic.query.get_or_404(id)
    try:
        db.session.delete(topic)
        db.session.commit()
        flash('Tópico excluído com sucesso.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Erro: Não é possível excluir o tópico pois existem dados dependentes vinculados.', 'danger')
    return redirect(url_for('lms.list_topics'))


# --- Mural (Fórum) ---

@lms_bp.route('/subjects/<int:subject_id>/mural', methods=['GET', 'POST'])
@login_required
def mural(subject_id):
    subject = LMSSubject.query.get_or_404(subject_id)
    form = LMSMuralPostForm()
    
    if form.validate_on_submit():
        # TODO: Handle image upload
        post = LMSMuralPost(
            subject_id=subject.id,
            action=form.action.data,
            post=form.post.data,
            author_id=current_user.id
        )
        db.session.add(post)
        db.session.commit()
        flash('Publicado no mural!', 'success')
        return redirect(url_for('lms.mural', subject_id=subject.id))
        
    page = request.args.get('page', 1, type=int)
    posts = LMSMuralPost.query.filter_by(subject_id=subject.id).order_by(LMSMuralPost.created_at.desc()).paginate(page=page, per_page=30)
    
    comment_form = LMSMuralCommentForm()
    return render_template('lms/mural.html', subject=subject, posts=posts, form=form, comment_form=comment_form)

@lms_bp.route('/mural/<int:post_id>/comment', methods=['POST'])
@login_required
def add_mural_comment(post_id):
    post = LMSMuralPost.query.get_or_404(post_id)
    form = LMSMuralCommentForm()
    
    if form.validate_on_submit():
        comment = LMSMuralComment(
            post_id=post.id,
            comment=form.comment.data,
            author_id=current_user.id
        )
        db.session.add(comment)
        db.session.commit()
        flash('Comentário enviado!', 'success')
        
    return redirect(url_for('lms.mural', subject_id=post.subject_id))

# --- Recursos Educacionais ---

@lms_bp.route('/resources', methods=['GET'])
@login_required
def list_resources():
    page = request.args.get('page', 1, type=int)
    resources = LMSResource.query.order_by(LMSResource.created_at.desc()).paginate(page=page, per_page=30)
    return render_template('lms/resources_list.html', resources=resources)

@lms_bp.route('/resources/create', methods=['GET', 'POST'])
@login_required
def create_resource():
    form = LMSResourceForm()
    form.topic_id.choices = [(t.id, t.name) for t in LMSTopic.query.order_by(LMSTopic.name).all()]
    form.groups.choices = [(g.id, g.name) for g in LMSStudentGroup.query.order_by(LMSStudentGroup.name).all()]
    
    if form.validate_on_submit():
        # TODO: Handle file upload if type is file or pdf
        resource = LMSResource(
            topic_id=form.topic_id.data,
            type=form.type.data,
            name=form.name.data,
            brief_description=form.brief_description.data,
            content=form.content.data,
            url=form.url.data,
            show_window=form.show_window.data,
            all_students=form.all_students.data,
            visible=form.visible.data,
            tags=form.tags.data
        )
        if form.groups.data:
            resource.groups = LMSStudentGroup.query.filter(LMSStudentGroup.id.in_(form.groups.data)).all()
            
        db.session.add(resource)
        db.session.commit()
        flash('Recurso criado com sucesso!', 'success')
        return redirect(url_for('lms.list_resources'))
        
    return render_template('lms/resource_form.html', form=form)

@lms_bp.route('/resources/<int:id>/delete', methods=['POST'])
@login_required
def delete_resource(id):
    resource = LMSResource.query.get_or_404(id)
    try:
        db.session.delete(resource)
        db.session.commit()
        flash('Recurso excluído com sucesso.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Erro ao excluir recurso.', 'danger')
    return redirect(url_for('lms.list_resources'))

# --- Metas de Aprendizagem ---

@lms_bp.route('/goals', methods=['GET'])
@login_required
def list_goals():
    page = request.args.get('page', 1, type=int)
    goals = LMSGoal.query.order_by(LMSGoal.init_date.desc()).paginate(page=page, per_page=30)
    return render_template('lms/goals_list.html', goals=goals)

@lms_bp.route('/goals/create', methods=['GET', 'POST'])
@login_required
def create_goal():
    form = LMSGoalForm()
    form.subject_id.choices = [(s.id, s.name) for s in LMSSubject.query.order_by(LMSSubject.name).all()]
    
    if form.validate_on_submit():
        goal = LMSGoal(
            subject_id=form.subject_id.data,
            name=form.name.data,
            presentation=form.presentation.data,
            brief_description=form.brief_description.data,
            init_date=form.init_date.data,
            limit_submission_date=form.limit_submission_date.data,
            visible=form.visible.data
        )
        db.session.add(goal)
        db.session.commit()
        flash('Meta de aprendizagem criada.', 'success')
        return redirect(url_for('lms.list_goals'))
        
    return render_template('lms/goal_form.html', form=form)

@lms_bp.route('/goals/<int:id>/delete', methods=['POST'])
@login_required
def delete_goal(id):
    goal = LMSGoal.query.get_or_404(id)
    try:
        db.session.delete(goal)
        db.session.commit()
        flash('Meta excluída com sucesso.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Erro ao excluir meta.', 'danger')
    return redirect(url_for('lms.list_goals'))

# --- Avaliações e Importação Assíncrona ---

@lms_bp.route('/evaluations', methods=['GET'])
@login_required
def list_evaluations():
    page = request.args.get('page', 1, type=int)
    evaluations = LMSEvaluation.query.order_by(LMSEvaluation.date.desc()).paginate(page=page, per_page=30)
    return render_template('lms/evaluations_list.html', evaluations=evaluations)

@lms_bp.route('/evaluations/create', methods=['GET', 'POST'])
@login_required
def create_evaluation():
    form = LMSEvaluationForm()
    form.subject_id.choices = [(s.id, s.name) for s in LMSSubject.query.order_by(LMSSubject.name).all()]
    
    if form.validate_on_submit():
        evaluation = LMSEvaluation(
            subject_id=form.subject_id.data,
            name=form.name.data,
            type=form.type.data,
            date=form.date.data,
            visible=form.visible.data
        )
        db.session.add(evaluation)
        db.session.commit()
        flash('Avaliação criada com sucesso.', 'success')
        return redirect(url_for('lms.list_evaluations'))
        
    return render_template('lms/evaluation_form.html', form=form)

@lms_bp.route('/evaluations/<int:id>/delete', methods=['POST'])
@login_required
def delete_evaluation(id):
    evaluation = LMSEvaluation.query.get_or_404(id)
    try:
        db.session.delete(evaluation)
        db.session.commit()
        flash('Avaliação excluída com sucesso.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Erro ao excluir avaliação.', 'danger')
    return redirect(url_for('lms.list_evaluations'))

def _process_import_job(app, job_id, current_user_id):
    with app.app_context():
        job = LMSImportJob.query.get(job_id)
        if not job:
            return
        
        job.status = 'processing'
        db.session.commit()
        
        log_messages = []
        try:
            # Ler arquivo excel
            df = pd.read_excel(job.file_path)
            total_rows = len(df)
            job.total_records = total_rows
            db.session.commit()
            
            # Assumindo Coluna A = Email/CPF (Identificador), Coluna B = Nota
            if df.empty or len(df.columns) < 2:
                raise ValueError("Planilha inválida. O arquivo deve ter pelo menos 2 colunas.")
                
            identificadores = df.iloc[:, 0].astype(str).str.strip().tolist()
            notas = df.iloc[:, 1].tolist()
            
            # Buscar alunos de uma vez para otimização
            users = User.query.filter(db.or_(User.email.in_(identificadores), User.username.in_(identificadores))).all()
            user_map = {u.email: u.id for u in users if u.email}
            user_map.update({u.username: u.id for u in users if u.username})
            
            grades_to_insert = []
            
            for i in range(total_rows):
                ident = identificadores[i]
                nota_raw = notas[i]
                
                try:
                    nota_val = float(nota_raw)
                except (ValueError, TypeError):
                    log_messages.append(f"Linha {i+2}: Nota inválida '{nota_raw}' para identificador {ident}.")
                    job.processed_records += 1
                    continue
                
                user_id = user_map.get(ident)
                if not user_id:
                    log_messages.append(f"Linha {i+2}: Aluno não encontrado com identificador '{ident}'.")
                    job.processed_records += 1
                    continue
                
                grades_to_insert.append(LMSStudentGrade(
                    evaluation_id=job.evaluation_id,
                    student_id=user_id,
                    grade=nota_val
                ))
                
                job.processed_records += 1
                
                # Update progress every 50 records
                if i % 50 == 0:
                    db.session.commit()
            
            # Inserção em massa otimizada
            if grades_to_insert:
                db.session.bulk_save_objects(grades_to_insert)
            
            job.status = 'completed'
            job.log = "\n".join(log_messages) if log_messages else "Importação concluída sem erros."
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            job.status = 'error'
            job.log = f"Erro fatal: {str(e)}\n" + "\n".join(log_messages)
            db.session.commit()
        finally:
            # Limpar arquivo temporário
            if os.path.exists(job.file_path):
                try:
                    os.remove(job.file_path)
                except:
                    pass

@lms_bp.route('/evaluations/<int:id>/import_grades', methods=['POST'])
@login_required
def import_grades(id):
    evaluation = LMSEvaluation.query.get_or_404(id)
    
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Arquivo vazio.'}), 400
        
    if not file.filename.endswith(('.xls', '.xlsx')):
        return jsonify({'error': 'Apenas arquivos Excel (.xls, .xlsx) são permitidos.'}), 400
        
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'temp')
    os.makedirs(upload_dir, exist_ok=True)
    filename = secure_filename(f"import_{current_user.id}_{file.filename}")
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    
    # Criar Job
    job = LMSImportJob(
        evaluation_id=evaluation.id,
        file_path=filepath,
        status='pending'
    )
    db.session.add(job)
    db.session.commit()
    
    # Iniciar Thread
    app = current_app._get_current_object()
    thread = threading.Thread(target=_process_import_job, args=(app, job.id, current_user.id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job.id, 'message': 'Importação iniciada com sucesso.'}), 202

@lms_bp.route('/api/job_status/<int:job_id>', methods=['GET'])
@login_required
def job_status(job_id):
    job = LMSImportJob.query.get_or_404(job_id)
    return jsonify({
        'status': job.status,
        'total_records': job.total_records,
        'processed_records': job.processed_records,
        'log': job.log
    })
