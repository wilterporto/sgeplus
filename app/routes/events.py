from app.utils.tenancy import get_tenant_id
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import CertificateTemplate, Event, Participant
from app.forms import CertificateTemplateForm, EventForm, ParticipantForm
from werkzeug.utils import secure_filename
import os
import uuid
import pandas as pd

events_bp = Blueprint('events', __name__)

# --- Certificate Templates ---
@events_bp.route('/templates')
@login_required
def list_templates():
    page = request.args.get('page', 1, type=int)
    pagination = CertificateTemplate.query.filter_by(tenant_id=get_tenant_id()).paginate(page=page, per_page=30, error_out=False)
    return render_template('events/templates_list.html', pagination=pagination, title="Modelos de Certificado")

@events_bp.route('/templates/new', methods=['GET', 'POST'])
@login_required
def new_template():
    form = CertificateTemplateForm()
    if form.validate_on_submit():
        template = CertificateTemplate(
            tenant_id=get_tenant_id(),
            name=form.name.data,
            content_html=form.content_html.data
        )
        if form.background_image.data:
            filename = secure_filename(form.background_image.data.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'certificates', unique_filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            form.background_image.data.save(filepath)
            template.background_image = unique_filename

        db.session.add(template)
        db.session.commit()
        flash('Modelo cadastrado com sucesso!', 'success')
        return redirect(url_for('events.list_templates'))
    return render_template('events/template_form.html', form=form, title="Novo Modelo de Certificado")

@events_bp.route('/templates/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(id):
    template = CertificateTemplate.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    form = CertificateTemplateForm(obj=template)
    if form.validate_on_submit():
        template.name = form.name.data
        template.content_html = form.content_html.data
        if form.background_image.data:
            filename = secure_filename(form.background_image.data.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'certificates', unique_filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            form.background_image.data.save(filepath)
            template.background_image = unique_filename
        
        db.session.commit()
        flash('Modelo atualizado com sucesso!', 'success')
        return redirect(url_for('events.list_templates'))
    return render_template('events/template_form.html', form=form, title="Editar Modelo de Certificado")

@events_bp.route('/templates/<int:id>/delete', methods=['POST'])
@login_required
def delete_template(id):
    template = CertificateTemplate.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    if template.events:
        flash('Não é possível excluir este modelo pois ele está vinculado a um ou mais eventos.', 'danger')
    else:
        db.session.delete(template)
        db.session.commit()
        flash('Modelo excluído com sucesso!', 'success')
    return redirect(url_for('events.list_templates'))

# --- Events ---
@events_bp.route('/')
@login_required
def list_events():
    page = request.args.get('page', 1, type=int)
    pagination = Event.query.filter_by(tenant_id=get_tenant_id()).order_by(Event.date.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template('events/list.html', pagination=pagination, title="Eventos")

@events_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_event():
    form = EventForm()
    templates = CertificateTemplate.query.filter_by(tenant_id=get_tenant_id()).all()
    form.certificate_template_id.choices = [(0, 'Nenhum')] + [(t.id, t.name) for t in templates]
    if form.validate_on_submit():
        event = Event(
            tenant_id=get_tenant_id(),
            name=form.name.data,
            date=form.date.data,
            type=form.type.data,
            certificate_template_id=form.certificate_template_id.data if form.certificate_template_id.data != 0 else None
        )
        db.session.add(event)
        db.session.commit()
        flash('Evento cadastrado com sucesso!', 'success')
        return redirect(url_for('events.list_events'))
    return render_template('events/form.html', form=form, title="Novo Evento")

@events_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(id):
    event = Event.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    form = EventForm(obj=event)
    templates = CertificateTemplate.query.filter_by(tenant_id=get_tenant_id()).all()
    form.certificate_template_id.choices = [(0, 'Nenhum')] + [(t.id, t.name) for t in templates]
    
    if request.method == 'GET' and event.certificate_template_id is None:
        form.certificate_template_id.data = 0

    if form.validate_on_submit():
        event.name = form.name.data
        event.date = form.date.data
        event.type = form.type.data
        event.certificate_template_id = form.certificate_template_id.data if form.certificate_template_id.data != 0 else None
        db.session.commit()
        flash('Evento atualizado com sucesso!', 'success')
        return redirect(url_for('events.list_events'))
    return render_template('events/form.html', form=form, title="Editar Evento")

@events_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_event(id):
    event = Event.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    if event.participants.first():
        flash('Não é possível excluir este evento pois existem participantes inscritos.', 'danger')
    else:
        db.session.delete(event)
        db.session.commit()
        flash('Evento excluído com sucesso!', 'success')
    return redirect(url_for('events.list_events'))

# --- Participants ---
@events_bp.route('/<int:id>/participants')
@login_required
def list_participants(id):
    event = Event.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = event.participants.order_by(Participant.name.asc()).paginate(page=page, per_page=30, error_out=False)
    form = ParticipantForm()
    return render_template('events/participants.html', event=event, pagination=pagination, form=form, title=f"Participantes - {event.name}")

@events_bp.route('/<int:id>/participants/add', methods=['POST'])
@login_required
def add_participant(id):
    event = Event.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    form = ParticipantForm()
    if form.validate_on_submit():
        existing = Participant.query.filter_by(event_id=id, cpf=form.cpf.data).first()
        if existing:
            flash('Este CPF já está inscrito neste evento.', 'warning')
        else:
            participant = Participant(
                event_id=id,
                name=form.name.data,
                birth_date=form.birth_date.data,
                cpf=form.cpf.data,
                email=form.email.data
            )
            db.session.add(participant)
            db.session.commit()
            flash('Participante adicionado com sucesso!', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
                
    return redirect(url_for('events.list_participants', id=id))

@events_bp.route('/participants/<int:id>/delete', methods=['POST'])
@login_required
def delete_participant(id):
    participant = Participant.query.get_or_404(id)
    event = Event.query.filter_by(id=participant.event_id, tenant_id=get_tenant_id()).first_or_404()
    db.session.delete(participant)
    db.session.commit()
    flash('Participante removido com sucesso!', 'success')
    return redirect(url_for('events.list_participants', id=event.id))

@events_bp.route('/<int:id>/import', methods=['POST'])
@login_required
def import_participants(id):
    event = Event.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado.'}), 400
        
    if not file.filename.endswith(('.xls', '.xlsx')):
        return jsonify({'error': 'Formato de arquivo inválido. Envie um arquivo Excel.'}), 400
        
    try:
        df = pd.read_excel(file)
        
        if 'Nome' not in df.columns or 'CPF' not in df.columns:
            return jsonify({'error': 'A planilha deve conter as colunas "Nome" e "CPF".'}), 400
            
        participants_to_insert = []
        total_rows = len(df)
        inserted_count = 0
        
        import re
        for index, row in df.iterrows():
            nome = str(row['Nome']).strip()
            cpf = str(row['CPF']).strip()
            
            cpf = re.sub(r'[^0-9]', '', cpf)
            
            if nome and cpf and len(cpf) == 11 and nome.lower() != 'nan':
                participants_to_insert.append(Participant(
                    event_id=event.id,
                    name=nome,
                    cpf=cpf,
                    email=str(row['Email']).strip() if 'Email' in df.columns and str(row['Email']).lower() != 'nan' else None
                ))
                inserted_count += 1
                
        if participants_to_insert:
            db.session.bulk_save_objects(participants_to_insert)
            db.session.commit()
            
        return jsonify({'success': f'{inserted_count} participantes importados com sucesso de um total de {total_rows} registros.'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@events_bp.route('/<int:event_id>/certificate/<int:participant_id>')
def view_certificate(event_id, participant_id):
    event = Event.query.filter_by(id=event_id).first_or_404()
    participant = Participant.query.filter_by(id=participant_id, event_id=event_id).first_or_404()
    
    if not event.certificate_template_id:
        return "Este evento não possui modelo de certificado configurado.", 404
        
    template = event.certificate_template
    
    html = template.content_html
    if html:
        html = html.replace('{{ nome_participante }}', participant.name)
        html = html.replace('{{ cpf_participante }}', participant.cpf)
        html = html.replace('{{ nome_evento }}', event.name)
        html = html.replace('{{ data_evento }}', event.date.strftime('%d/%m/%Y'))
        
    return render_template('events/certificate_view.html', template=template, content=html, participant=participant, event=event)
