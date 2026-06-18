import os
import uuid
import re
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from app import db
from app.models import Supplier, SupplierContact, ServiceType, ServiceOrder, ServiceOrderAttachment, TeachingUnit, User
from app.forms import SupplierForm, SupplierContactForm, ServiceTypeForm, ServiceOrderForm, ScheduleServiceOrderForm
from app.utils.tenancy import get_tenant_id

services_bp = Blueprint('services', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_cpf(cpf):
    return re.sub(r'[^0-9]', '', cpf) if cpf else ''

# --- SUPPLIERS ---

@services_bp.route('/suppliers', methods=['GET'])
def list_suppliers():
    tenant_id = get_tenant_id()
    page = request.args.get('page', 1, type=int)
    query = Supplier.query.filter_by(tenant_id=tenant_id)
    
    search = request.args.get('search')
    if search:
        query = query.filter(Supplier.name.ilike(f'%{search}%') | Supplier.cpf_cnpj.ilike(f'%{search}%'))
        
    pagination = query.order_by(Supplier.name).paginate(page=page, per_page=30, error_out=False)
    return render_template('services/suppliers.html', suppliers=pagination.items, pagination=pagination)

@services_bp.route('/suppliers/new', methods=['GET', 'POST'])
def new_supplier():
    tenant_id = get_tenant_id()
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = Supplier(
            tenant_id=tenant_id,
            type=form.type.data,
            cpf_cnpj=form.cpf_cnpj.data,
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            active=form.active.data
        )
        db.session.add(supplier)
        try:
            db.session.commit()
            flash('Fornecedor cadastrado com sucesso!', 'success')
            return redirect(url_for('services.list_suppliers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar: {str(e)}', 'danger')
            
    return render_template('services/supplier_form.html', form=form, title="Novo Fornecedor")

@services_bp.route('/suppliers/<int:id>/edit', methods=['GET', 'POST'])
def edit_supplier(id):
    tenant_id = get_tenant_id()
    supplier = Supplier.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    form = SupplierForm(obj=supplier)
    
    if form.validate_on_submit():
        supplier.type = form.type.data
        supplier.cpf_cnpj = form.cpf_cnpj.data
        supplier.name = form.name.data
        supplier.email = form.email.data
        supplier.phone = form.phone.data
        supplier.active = form.active.data
        try:
            db.session.commit()
            flash('Fornecedor atualizado com sucesso!', 'success')
            return redirect(url_for('services.list_suppliers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
            
    return render_template('services/supplier_form.html', form=form, title="Editar Fornecedor")

@services_bp.route('/suppliers/<int:id>/delete', methods=['POST'])
def delete_supplier(id):
    tenant_id = get_tenant_id()
    supplier = Supplier.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    
    # Validação de deleção
    if supplier.orders.count() > 0:
        flash('Não é possível excluir este fornecedor pois existem ordens de serviço vinculadas a ele.', 'danger')
        return redirect(url_for('services.list_suppliers'))
        
    try:
        db.session.delete(supplier)
        db.session.commit()
        flash('Fornecedor excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao excluir fornecedor.', 'danger')
    return redirect(url_for('services.list_suppliers'))

# --- SUPPLIER CONTACTS (USERS) ---

@services_bp.route('/suppliers/<int:id>/contacts', methods=['GET', 'POST'])
def supplier_contacts(id):
    tenant_id = get_tenant_id()
    supplier = Supplier.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    form = SupplierContactForm()
    
    if form.validate_on_submit():
        cpf_limpo = clean_cpf(form.cpf.data)
        if len(cpf_limpo) != 11:
            flash('CPF deve conter 11 dígitos.', 'danger')
            return redirect(url_for('services.supplier_contacts', id=id))
            
        # Verifica se o usuário já existe
        existing_user = User.query.filter_by(username=cpf_limpo).first()
        if existing_user:
            flash('Este CPF já está em uso no sistema por outro usuário.', 'danger')
            return redirect(url_for('services.supplier_contacts', id=id))
            
        senha_inicial = cpf_limpo[:6]
        
        user = User(
            username=cpf_limpo,
            email=form.email.data,
            name=form.name.data,
            role='fornecedor',
            roles='fornecedor',
            tenant_id=tenant_id,
            active=True
        )
        user.set_password(senha_inicial)
        db.session.add(user)
        db.session.flush() # Para pegar o user_id
        
        contact = SupplierContact(
            supplier_id=supplier.id,
            user_id=user.id,
            name=form.name.data,
            cpf=form.cpf.data,
            email=form.email.data
        )
        db.session.add(contact)
        
        try:
            db.session.commit()
            flash(f'Responsável cadastrado! Login: {cpf_limpo} | Senha inicial: {senha_inicial}', 'success')
            return redirect(url_for('services.supplier_contacts', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {str(e)}', 'danger')
            
    return render_template('services/supplier_contacts.html', supplier=supplier, form=form)

@services_bp.route('/contacts/<int:contact_id>/delete', methods=['POST'])
def delete_contact(contact_id):
    contact = SupplierContact.query.get_or_404(contact_id)
    supplier_id = contact.supplier_id
    
    try:
        user = contact.user
        db.session.delete(contact)
        if user:
            db.session.delete(user)
        db.session.commit()
        flash('Responsável removido com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao remover responsável.', 'danger')
        
    return redirect(url_for('services.supplier_contacts', id=supplier_id))

# --- SERVICE TYPES ---

@services_bp.route('/types', methods=['GET'])
def list_types():
    tenant_id = get_tenant_id()
    page = request.args.get('page', 1, type=int)
    pagination = ServiceType.query.filter_by(tenant_id=tenant_id).order_by(ServiceType.name).paginate(page=page, per_page=30, error_out=False)
    return render_template('services/types.html', types=pagination.items, pagination=pagination)

@services_bp.route('/types/new', methods=['GET', 'POST'])
def new_type():
    tenant_id = get_tenant_id()
    form = ServiceTypeForm()
    if form.validate_on_submit():
        svc = ServiceType(tenant_id=tenant_id, name=form.name.data, description=form.description.data, active=form.active.data)
        db.session.add(svc)
        try:
            db.session.commit()
            flash('Tipo de serviço cadastrado!', 'success')
            return redirect(url_for('services.list_types'))
        except Exception:
            db.session.rollback()
            flash('Erro ao cadastrar tipo de serviço. Pode já existir um com este nome.', 'danger')
    return render_template('services/type_form.html', form=form, title="Novo Tipo de Serviço")

@services_bp.route('/types/<int:id>/edit', methods=['GET', 'POST'])
def edit_type(id):
    tenant_id = get_tenant_id()
    svc = ServiceType.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    form = ServiceTypeForm(obj=svc)
    if form.validate_on_submit():
        svc.name = form.name.data
        svc.description = form.description.data
        svc.active = form.active.data
        try:
            db.session.commit()
            flash('Tipo de serviço atualizado!', 'success')
            return redirect(url_for('services.list_types'))
        except Exception:
            db.session.rollback()
            flash('Erro ao atualizar.', 'danger')
    return render_template('services/type_form.html', form=form, title="Editar Tipo de Serviço")

@services_bp.route('/types/<int:id>/delete', methods=['POST'])
def delete_type(id):
    tenant_id = get_tenant_id()
    svc = ServiceType.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    
    orders_count = ServiceOrder.query.filter_by(service_type_id=id).count()
    if orders_count > 0:
        flash('Não é possível excluir este tipo de serviço pois existem ordens vinculadas.', 'danger')
        return redirect(url_for('services.list_types'))
        
    db.session.delete(svc)
    db.session.commit()
    flash('Tipo de serviço excluído.', 'success')
    return redirect(url_for('services.list_types'))

# --- SERVICE ORDERS ---

@services_bp.route('/orders/dashboard', methods=['GET'])
def dashboard():
    tenant_id = get_tenant_id()
    
    query = ServiceOrder.query.filter_by(tenant_id=tenant_id)
    
    # Se for fornecedor logado, mostra apenas as ordens que ele pode ver
    if 'fornecedor' in current_user.get_roles():
        contact = getattr(current_user, 'supplier_contact', None)
        if contact:
            query = query.filter((ServiceOrder.supplier_id == contact.supplier_id) | (ServiceOrder.supplier_id == None))

    # Obter todos os resultados para calcular as estatísticas
    # Em produção com milhões de registros, faríamos queries agrupadas por count().
    # Como as tabelas são pequenas, puxar os dados não é tão custoso, 
    # mas o ideal é fazer a contagem agrupada via banco.
    from sqlalchemy import func
    
    # Contagens por status
    status_counts = db.session.query(
        ServiceOrder.status, func.count(ServiceOrder.id)
    ).filter_by(tenant_id=tenant_id)
    
    if 'fornecedor' in current_user.get_roles():
        contact = getattr(current_user, 'supplier_contact', None)
        if contact:
            status_counts = status_counts.filter((ServiceOrder.supplier_id == contact.supplier_id) | (ServiceOrder.supplier_id == None))
            
    status_counts = status_counts.group_by(ServiceOrder.status).all()
    
    stats = {
        'Pendente': 0,
        'Agendado': 0,
        'Concluído': 0,
        'Cancelado': 0,
        'Total': 0
    }
    for status, count in status_counts:
        if status in stats:
            stats[status] = count
        stats['Total'] += count

    # Cálculos de agendamento (7, 15, 30 dias)
    from datetime import date, timedelta
    hoje = date.today()
    dia_7 = hoje + timedelta(days=7)
    dia_15 = hoje + timedelta(days=15)
    dia_30 = hoje + timedelta(days=30)
    
    # Filtro apenas para agendamentos futuros não concluídos nem cancelados
    scheduled_query = query.filter(
        ServiceOrder.scheduled_date.isnot(None),
        ServiceOrder.status.in_(['Pendente', 'Agendado']),
        db.func.date(ServiceOrder.scheduled_date) >= hoje
    )
    
    # Executamos a query dos próximos 30 dias ordenados por data
    upcoming_30_days = scheduled_query.filter(db.func.date(ServiceOrder.scheduled_date) <= dia_30).order_by(ServiceOrder.scheduled_date).all()
    
    schedules = {
        '7_dias': 0,
        '15_dias': 0,
        '30_dias': 0
    }
    
    for order in upcoming_30_days:
        s_date = order.scheduled_date.date()
        if s_date <= dia_7:
            schedules['7_dias'] += 1
        if s_date <= dia_15:
            schedules['15_dias'] += 1
        if s_date <= dia_30:
            schedules['30_dias'] += 1
            
    return render_template('services/dashboard.html', stats=stats, schedules=schedules, upcoming=upcoming_30_days[:15])


@services_bp.route('/orders', methods=['GET'])
def list_orders():
    tenant_id = get_tenant_id()
    page = request.args.get('page', 1, type=int)
    
    query = ServiceOrder.query.filter_by(tenant_id=tenant_id)
    
    # Se for fornecedor logado, mostra apenas as ordens que ele pode ver (ainda pendentes ou dele)
    if 'fornecedor' in current_user.get_roles():
        contact = getattr(current_user, 'supplier_contact', None)
        if contact:
            query = query.filter((ServiceOrder.supplier_id == contact.supplier_id) | (ServiceOrder.supplier_id == None))
            
    pagination = query.order_by(ServiceOrder.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template('services/orders.html', orders=pagination.items, pagination=pagination)

@services_bp.route('/orders/new', methods=['GET', 'POST'])
def new_order():
    tenant_id = get_tenant_id()
    form = ServiceOrderForm()
    
    # Preencher combos
    schools = TeachingUnit.query.filter_by(tenant_id=tenant_id, type='Escola').order_by(TeachingUnit.name).all()
    types = ServiceType.query.filter_by(tenant_id=tenant_id, active=True).order_by(ServiceType.name).all()
    
    form.school_id.choices = [(s.id, s.name) for s in schools]
    form.service_type_id.choices = [(t.id, t.name) for t in types]
    
    if form.validate_on_submit():
        order = ServiceOrder(
            tenant_id=tenant_id,
            school_id=form.school_id.data,
            service_type_id=form.service_type_id.data,
            description=form.description.data,
            status='Pendente',
            created_by_id=current_user.id
        )
        db.session.add(order)
        db.session.flush() # pega o ID da order
        
        # Upload de arquivos
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'services')
        os.makedirs(upload_folder, exist_ok=True)
        
        files = request.files.getlist(form.photos.name)
        for file in files:
            if file and file.filename != '':
                if not allowed_file(file.filename):
                    flash(f'Arquivo {file.filename} inválido. Apenas JPG/PNG.', 'danger')
                    continue
                    
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                if size > MAX_FILE_SIZE:
                    flash(f'Arquivo {file.filename} muito grande (Máx 5MB).', 'danger')
                    continue
                    
                ext = file.filename.rsplit('.', 1)[1].lower()
                safe_name = f"{uuid.uuid4().hex}.{ext}"
                save_path = os.path.join(upload_folder, safe_name)
                
                file.save(save_path)
                
                attachment = ServiceOrderAttachment(
                    service_order_id=order.id,
                    file_path=f"uploads/services/{safe_name}",
                    filename=secure_filename(file.filename)
                )
                db.session.add(attachment)
                
        try:
            db.session.commit()
            flash('Ordem de serviço aberta com sucesso!', 'success')
            return redirect(url_for('services.list_orders'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao abrir ordem: {str(e)}', 'danger')
            
    return render_template('services/order_form.html', form=form)

@services_bp.route('/orders/<int:id>', methods=['GET', 'POST'])
def view_order(id):
    tenant_id = get_tenant_id()
    order = ServiceOrder.query.filter_by(id=id, tenant_id=tenant_id).first_or_404()
    
    # Form para o Fornecedor agendar
    form = ScheduleServiceOrderForm(obj=order)
    
    # Apenas admin ou escola pode alterar o fornecedor designado
    suppliers = Supplier.query.filter_by(tenant_id=tenant_id, active=True).order_by(Supplier.name).all()
    form.supplier_id.choices = [(0, '--- Nenhum ---')] + [(s.id, s.name) for s in suppliers]
    
    if not form.supplier_id.data and order.supplier_id:
        form.supplier_id.data = order.supplier_id
        
    if request.method == 'POST' and form.validate_on_submit():
        # Se for fornecedor, ele pode agendar e colocar o status como "Agendado"
        if 'fornecedor' in current_user.get_roles():
            contact = getattr(current_user, 'supplier_contact', None)
            if contact:
                order.supplier_id = contact.supplier_id
                
        if form.supplier_id.data and form.supplier_id.data != 0:
            order.supplier_id = form.supplier_id.data
        elif form.supplier_id.data == 0:
            order.supplier_id = None
            
        if form.scheduled_date.data:
            try:
                order.scheduled_date = datetime.strptime(form.scheduled_date.data, '%Y-%m-%dT%H:%M')
            except:
                pass # ou tentar tratar outros formatos
                
        order.status = form.status.data
        db.session.commit()
        flash('Ordem atualizada com sucesso.', 'success')
        return redirect(url_for('services.view_order', id=order.id))
        
    return render_template('services/order_detail.html', order=order, form=form)
