from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, session, send_from_directory
from flask_login import login_required, current_user
import os
import uuid
from werkzeug.utils import secure_filename
from app import db
from app.models import (
    OmbudsmanSubject, OmbudsmanManifestation, OmbudsmanHistory, User, SystemConfig, OmbudsmanAttachment,
    OmbudsmanNatureEnum, OmbudsmanStatusEnum, OmbudsmanRequesterTypeEnum, OmbudsmanEntryModeEnum
)
from app.forms import (
    OmbudsmanSubjectForm, OmbudsmanPublicManifestationForm,
    OmbudsmanStatusUpdateForm, OmbudsmanSearchForm
)
from app.routes.auth import send_email
from app.utils.tenancy import get_tenant_id
from sqlalchemy import desc, func
from datetime import datetime

ouvidoria_bp = Blueprint('ouvidoria', __name__)

def _send_ouvidoria_email(subject, text_body, html_body, recipients):
    sender = SystemConfig.get_value('smtp_sender')
    if sender and recipients:
        send_email(subject, sender, recipients, text_body, html_body)

# ==========================================
# PUBLIC ROUTES
# ==========================================
@ouvidoria_bp.route('/', methods=['GET', 'POST'])
def portal():
    # Verifica se há tenant na sessão para contexto público
    tenant_id = get_tenant_id()
    if not tenant_id:
        # Tenta pegar um tenant genérico ou obriga estar em um domínio/cliente
        # Como o sistema tem /auth/login para escolher cliente, se for portal aberto
        # precisa tratar. Assumindo que a ouvidoria é do sistema geral ou tenant ativo.
        pass
        
    form = OmbudsmanSearchForm()
    if form.validate_on_submit():
        manifestation = OmbudsmanManifestation.query.filter_by(
            protocol_number=form.protocol_number.data,
            tenant_id=tenant_id
        ).first()
        if manifestation:
            return redirect(url_for('ouvidoria.public_detail', protocol=manifestation.protocol_number))
        else:
            flash('Protocolo não encontrado.', 'danger')
            
    return render_template('ouvidoria/portal.html', form=form)

@ouvidoria_bp.route('/protocolo/<protocol>')
def public_detail(protocol):
    tenant_id = get_tenant_id()
    manifestation = OmbudsmanManifestation.query.filter_by(protocol_number=protocol, tenant_id=tenant_id).first_or_404()
    return render_template('ouvidoria/public_detail.html', manifestation=manifestation)

@ouvidoria_bp.route('/nova', methods=['GET', 'POST'])
def nova():
    tenant_id = get_tenant_id()
    form = OmbudsmanPublicManifestationForm()
    
    # Dynamic Subjects
    if request.method == 'POST' and form.nature.data and form.nature.data > 0:
        subjects = OmbudsmanSubject.query.filter_by(nature=form.nature.data, active=True, tenant_id=tenant_id).order_by(OmbudsmanSubject.name).all()
        form.subject_id.choices = [(s.id, s.name) for s in subjects]
    else:
        form.subject_id.choices = [(0, 'Selecione o Assunto')]

    if form.validate_on_submit():
        if form.nature.data == 0 or form.subject_id.data == 0:
            flash('Por favor, selecione Natureza e Assunto.', 'danger')
            return render_template('ouvidoria/manifestation_form.html', form=form)
            
        attachments = request.files.getlist('attachments')
        valid_extensions = {'.pdf', '.png', '.jpg', '.jpeg'}
        max_size = 10 * 1024 * 1024 # 10MB
        files_to_save = []
        
        for file in attachments:
            if file and file.filename:
                ext = os.path.splitext(file.filename)[1].lower()
                if ext not in valid_extensions:
                    flash(f'Extensão não permitida para o arquivo {file.filename}. Apenas PDF, PNG e JPG são aceitos.', 'danger')
                    return render_template('ouvidoria/manifestation_form.html', form=form)
                
                file_content = file.read()
                if len(file_content) > max_size:
                    flash(f'O arquivo {file.filename} excede o tamanho limite de 10MB.', 'danger')
                    return render_template('ouvidoria/manifestation_form.html', form=form)
                
                file.seek(0)
                files_to_save.append(file)
            
        manifestation = OmbudsmanManifestation(
            tenant_id=tenant_id,
            protocol_number=OmbudsmanManifestation.generate_protocol(),
            title=form.title.data,
            description=form.description.data,
            nature=form.nature.data,
            subject_id=form.subject_id.data,
            is_anonymous=form.is_anonymous.data,
            requester_name=form.requester_name.data,
            requester_email=form.requester_email.data,
            requester_phone=form.requester_phone.data,
            requester_type=form.requester_type.data,
            entry_mode=form.entry_mode.data,
            status='Pendente'
        )
        db.session.add(manifestation)
        db.session.commit()
        
        if files_to_save:
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'ouvidoria')
            os.makedirs(upload_dir, exist_ok=True)
            for file in files_to_save:
                ext = os.path.splitext(file.filename)[1].lower()
                hashed_filename = uuid.uuid4().hex + ext
                file_path = os.path.join(upload_dir, hashed_filename)
                file.save(file_path)
                
                attachment = OmbudsmanAttachment(
                    manifestation_id=manifestation.id,
                    filename=hashed_filename,
                    original_filename=secure_filename(file.filename)
                )
                db.session.add(attachment)
            db.session.commit()

        
        # History
        history = OmbudsmanHistory(
            manifestation_id=manifestation.id,
            new_status='Pendente',
            comment='Manifestação registrada pelo portal.'
        )
        db.session.add(history)
        db.session.commit()
        
        # Send notifications
        _send_ouvidoria_email(
            f"Sua manifestação foi registrada - {manifestation.protocol_number}",
            f"Olá, recebemos sua manifestação protocolo {manifestation.protocol_number}.",
            render_template('ouvidoria/email/created.html', manifestation=manifestation),
            [manifestation.requester_email]
        )
        
        flash(f'Manifestação registrada com sucesso! Seu protocolo é {manifestation.protocol_number}', 'success')
        return redirect(url_for('ouvidoria.portal'))
        
    return render_template('ouvidoria/manifestation_form.html', form=form)

@ouvidoria_bp.route('/get_subjects/<int:nature_id>')
def get_subjects(nature_id):
    tenant_id = get_tenant_id()
    subjects = OmbudsmanSubject.query.filter_by(nature=nature_id, active=True, tenant_id=tenant_id).order_by(OmbudsmanSubject.name).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in subjects])

@ouvidoria_bp.route('/anexo/<filename>')
def serve_attachment(filename):
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'ouvidoria')
    return send_from_directory(upload_dir, filename)

# ==========================================
# ADMIN ROUTES
# ==========================================



@ouvidoria_bp.route('/assuntos', methods=['GET', 'POST'])
@login_required
def subject_list():
    tenant_id = get_tenant_id()
    subjects = OmbudsmanSubject.query.filter_by(tenant_id=tenant_id).order_by(OmbudsmanSubject.name).all()
    form = OmbudsmanSubjectForm()
    
    
    if form.validate_on_submit():
        subject = OmbudsmanSubject(
            name=form.name.data,
            nature=form.nature.data,
            active=form.active.data,
            tenant_id=tenant_id
        )
        db.session.add(subject)
        db.session.commit()
        flash('Assunto criado com sucesso!', 'success')
        return redirect(url_for('ouvidoria.subject_list'))
        
    return render_template('ouvidoria/subject_list.html', subjects=subjects, form=form, OmbudsmanNatureEnum=OmbudsmanNatureEnum)

@ouvidoria_bp.route('/assuntos/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def subject_edit(id):
    tenant_id = get_tenant_id()
    subject = OmbudsmanSubject.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    form = OmbudsmanSubjectForm(obj=subject)
    
    
    if form.validate_on_submit():
        subject.name = form.name.data
        subject.nature = form.nature.data
        subject.active = form.active.data
        db.session.commit()
        flash('Assunto atualizado com sucesso!', 'success')
        return redirect(url_for('ouvidoria.subject_list'))
        
    return render_template('ouvidoria/subject_form.html', form=form, subject=subject)

@ouvidoria_bp.route('/assuntos/<int:id>/delete', methods=['POST'])
@login_required
def subject_delete(id):
    tenant_id = get_tenant_id()
    subject = OmbudsmanSubject.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    if subject.manifestations.count() > 0:
        flash('Não é possível excluir o assunto pois ele já está vinculado a manifestações.', 'danger')
    else:
        db.session.delete(subject)
        db.session.commit()
        flash('Assunto excluído.', 'success')
    return redirect(url_for('ouvidoria.subject_list'))

@ouvidoria_bp.route('/solicitacoes')
@login_required
def manifestation_list():
    tenant_id = get_tenant_id()
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')
    
    query = OmbudsmanManifestation.query.filter_by(tenant_id=tenant_id)
    
    # Sorting logic
    if sort == 'title':
        query = query.order_by(OmbudsmanManifestation.title.desc() if order == 'desc' else OmbudsmanManifestation.title.asc())
    elif sort == 'status':
        query = query.order_by(OmbudsmanManifestation.status.desc() if order == 'desc' else OmbudsmanManifestation.status.asc())
    elif sort == 'updated_at':
        query = query.order_by(OmbudsmanManifestation.updated_at.desc() if order == 'desc' else OmbudsmanManifestation.updated_at.asc())
    else:
        query = query.order_by(OmbudsmanManifestation.created_at.desc() if order == 'desc' else OmbudsmanManifestation.created_at.asc())
        
    manifestations = query.paginate(page=page, per_page=30)
    
    return render_template('ouvidoria/manifestation_list.html', manifestations=manifestations, current_sort=sort, current_order=order)

@ouvidoria_bp.route('/solicitacoes/<int:id>', methods=['GET', 'POST'])
@login_required
def manifestation_detail(id):
    tenant_id = get_tenant_id()
    manifestation = OmbudsmanManifestation.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    
    form = OmbudsmanStatusUpdateForm()
    
    # Populate Users for assignment
    admins = User.query.filter(User.roles.like('%admin%')).all()
    form.assigned_to_id.choices = [(0, 'Não Atribuir / Limpar')] + [(u.id, u.name or u.username) for u in admins]
    
    if request.method == 'GET':
        form.status.data = manifestation.status
        form.assigned_to_id.data = manifestation.assigned_to_id or 0
        
    if form.validate_on_submit():
        old_status = manifestation.status
        manifestation.status = form.status.data
        manifestation.assigned_to_id = form.assigned_to_id.data if form.assigned_to_id.data > 0 else None
        
        # History
        history = OmbudsmanHistory(
            manifestation_id=manifestation.id,
            user_id=current_user.id,
            old_status=old_status,
            new_status=manifestation.status,
            comment=form.comment.data
        )
        db.session.add(history)
        db.session.commit()
        
        # Notification
        if form.comment.data or old_status != manifestation.status:
            _send_ouvidoria_email(
                f"Atualização na manifestação {manifestation.protocol_number}",
                f"Sua manifestação teve uma atualização. Status: {manifestation.status}.",
                render_template('ouvidoria/email/updated.html', manifestation=manifestation, history=history),
                [manifestation.requester_email]
            )
            
            if manifestation.assigned_to:
                _send_ouvidoria_email(
                    f"[Ouvidoria] Atualização na manifestação {manifestation.protocol_number}",
                    f"A manifestação {manifestation.protocol_number} foi atualizada por {current_user.name}.",
                    render_template('ouvidoria/email/updated_admin.html', manifestation=manifestation, history=history),
                    [manifestation.assigned_to.email]
                )
        
        flash('Manifestação atualizada com sucesso!', 'success')
        return redirect(url_for('ouvidoria.manifestation_list'))
    
    return render_template('ouvidoria/manifestation_detail.html', manifestation=manifestation, form=form)

@ouvidoria_bp.route('/dashboard')
@login_required
def dashboard():
    tenant_id = session.get('active_tenant_id')
    if not tenant_id:
        flash('Selecione um cliente para acessar o dashboard da ouvidoria.', 'warning')
        return redirect(url_for('main.index'))
        
    # Fetch available years for the tenant
    available_years_query = db.session.query(
        func.strftime('%Y', OmbudsmanManifestation.created_at).label('year')
    ).filter_by(tenant_id=tenant_id).distinct().order_by(desc('year')).all()
    available_years = [y[0] for y in available_years_query if y[0]]
    
    current_year = request.args.get('year', str(datetime.now().year))
    if current_year not in available_years and str(datetime.now().year) not in available_years and available_years:
        current_year = available_years[0]
    
    # 1. Manifestations by month
    monthly_data = db.session.query(
        func.strftime('%m', OmbudsmanManifestation.created_at).label('month'),
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by('month').all()
    
    # Format monthly data
    months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    month_labels = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    month_counts = {m: 0 for m in months}
    for m, count in monthly_data:
        month_counts[m] = count
    monthly_counts = [month_counts[m] for m in months]
    
    # 2. Quantity by Status
    status_data_raw = db.session.query(
        OmbudsmanManifestation.status,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.status).all()
    status_data = [(OmbudsmanStatusEnum(s).label if s else 'Desconhecido', count) for s, count in status_data_raw]
    
    # 3. Quantity by Nature
    nature_data_raw = db.session.query(
        OmbudsmanManifestation.nature,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.nature).all()
    nature_data = [(OmbudsmanNatureEnum(n).label if n else 'Desconhecida', count) for n, count in nature_data_raw]
    
    # 4. Quantity by Subject
    subject_data = db.session.query(
        OmbudsmanSubject.name,
        func.count(OmbudsmanManifestation.id)
    ).join(OmbudsmanManifestation).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanSubject.name).all()
    
    # 5. Quantity by Requester Type
    requester_type_data_raw = db.session.query(
        OmbudsmanManifestation.requester_type,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.requester_type).all()
    requester_type_data = [(OmbudsmanRequesterTypeEnum(r).label if r else 'Desconhecido', count) for r, count in requester_type_data_raw]
    
    # 6. Quantity by Entry Mode
    entry_mode_data_raw = db.session.query(
        OmbudsmanManifestation.entry_mode,
        func.count(OmbudsmanManifestation.id)
    ).filter(
        OmbudsmanManifestation.tenant_id == tenant_id,
        func.strftime('%Y', OmbudsmanManifestation.created_at) == current_year
    ).group_by(OmbudsmanManifestation.entry_mode).all()
    entry_mode_data = [(OmbudsmanEntryModeEnum(e).label if e else 'Desconhecido', count) for e, count in entry_mode_data_raw]
    
    return render_template('ouvidoria/dashboard.html',
        month_labels=month_labels,
        monthly_counts=monthly_counts,
        status_data=status_data,
        nature_data=nature_data,
        subject_data=subject_data,
        requester_type_data=requester_type_data,
        entry_mode_data=entry_mode_data,
        current_year=current_year,
        available_years=available_years
    )
