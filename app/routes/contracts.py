from app.utils.tenancy import get_tenant_id
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import ContractCategory, FinancialProgram, Contract, Supplier, ServiceType, ContractPurposeEnum, ContractModalityEnum, ContractEvaluationItem, ContractEvaluation, ContractEvaluationGrade, TeachingUnit
from app.forms import ContractCategoryForm, FinancialProgramForm, ContractForm, ContractEvaluationItemForm, ContractEvaluationForm
import datetime

bp = Blueprint('contracts', __name__, url_prefix='/contracts')

# --- Contract Categories ---
@bp.route('/categories')
@login_required
def list_categories():
    categories = ContractCategory.query.filter_by(tenant_id=get_tenant_id()).all()
    return render_template('contracts/categories.html', categories=categories, title="Categorias de Contrato")

@bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
def new_category():
    form = ContractCategoryForm()
    if form.validate_on_submit():
        category = ContractCategory(
            tenant_id=get_tenant_id(),
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(category)
        db.session.commit()
        flash('Categoria cadastrada com sucesso!', 'success')
        return redirect(url_for('contracts.list_categories'))
    return render_template('contracts/category_form.html', form=form, title="Nova Categoria de Contrato")

@bp.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    category = ContractCategory.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    form = ContractCategoryForm(obj=category)
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data
        db.session.commit()
        flash('Categoria atualizada com sucesso!', 'success')
        return redirect(url_for('contracts.list_categories'))
    return render_template('contracts/category_form.html', form=form, title="Editar Categoria de Contrato")

@bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    category = ContractCategory.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    if category.contracts.first():
         flash('Não é possível excluir esta categoria pois ela está vinculada a um ou mais contratos.', 'danger')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Categoria excluída com sucesso!', 'success')
    return redirect(url_for('contracts.list_categories'))


# --- Financial Programs ---
@bp.route('/programs')
@login_required
def list_programs():
    programs = FinancialProgram.query.filter_by(tenant_id=get_tenant_id()).all()
    return render_template('contracts/programs.html', programs=programs, title="Programas Financeiros")

@bp.route('/programs/new', methods=['GET', 'POST'])
@login_required
def new_program():
    form = FinancialProgramForm()
    if form.validate_on_submit():
        program = FinancialProgram(
            tenant_id=get_tenant_id(),
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(program)
        db.session.commit()
        flash('Programa Financeiro cadastrado com sucesso!', 'success')
        return redirect(url_for('contracts.list_programs'))
    return render_template('contracts/program_form.html', form=form, title="Novo Programa Financeiro")

@bp.route('/programs/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_program(id):
    program = FinancialProgram.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    form = FinancialProgramForm(obj=program)
    if form.validate_on_submit():
        program.name = form.name.data
        program.description = form.description.data
        db.session.commit()
        flash('Programa Financeiro atualizado com sucesso!', 'success')
        return redirect(url_for('contracts.list_programs'))
    return render_template('contracts/program_form.html', form=form, title="Editar Programa Financeiro")

@bp.route('/programs/<int:id>/delete', methods=['POST'])
@login_required
def delete_program(id):
    program = FinancialProgram.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    if program.contracts.first():
         flash('Não é possível excluir este programa pois ele está vinculado a um ou mais contratos.', 'danger')
    else:
        db.session.delete(program)
        db.session.commit()
        flash('Programa Financeiro excluído com sucesso!', 'success')
    return redirect(url_for('contracts.list_programs'))


# --- Contracts ---
@bp.route('/')
@login_required
def list_contracts():
    contracts = Contract.query.filter_by(tenant_id=get_tenant_id()).all()
    return render_template('contracts/contracts.html', contracts=contracts, title="Contratos")

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_contract():
    form = ContractForm()
    # Populate choices
    form.supplier_id.choices = [(0, 'Selecione...')] + [(s.id, s.name) for s in Supplier.query.filter_by(tenant_id=get_tenant_id(), active=True).all()]
    form.category_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in ContractCategory.query.filter_by(tenant_id=get_tenant_id()).all()]
    form.program_id.choices = [(0, 'Selecione...')] + [(p.id, p.name) for p in FinancialProgram.query.filter_by(tenant_id=get_tenant_id()).all()]
    form.services.choices = [(s.id, s.name) for s in ServiceType.query.filter_by(tenant_id=get_tenant_id()).all()]

    if form.validate_on_submit():
        if form.supplier_id.data == 0 or form.category_id.data == 0 or form.program_id.data == 0:
            flash('Por favor, selecione opções válidas para Fornecedor, Categoria e Programa Financeiro.', 'danger')
            return render_template('contracts/contract_form.html', form=form, title="Novo Contrato")

        contract = Contract(
            tenant_id=get_tenant_id(),
            supplier_id=form.supplier_id.data,
            purpose=ContractPurposeEnum[form.purpose.data],
            modality=ContractModalityEnum[form.modality.data],
            category_id=form.category_id.data,
            program_id=form.program_id.data,
            contract_number=form.contract_number.data,
            signature_date=form.signature_date.data,
            validity_start=form.validity_start.data,
            validity_end=form.validity_end.data
        )
        
        if contract.purpose == ContractPurposeEnum.SERVICOS and form.services.data:
            selected_services = ServiceType.query.filter(ServiceType.id.in_(form.services.data), ServiceType.tenant_id == get_tenant_id()).all()
            contract.services.extend(selected_services)

        db.session.add(contract)
        db.session.commit()
        flash('Contrato cadastrado com sucesso!', 'success')
        return redirect(url_for('contracts.list_contracts'))

    return render_template('contracts/contract_form.html', form=form, title="Novo Contrato")

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contract(id):
    contract = Contract.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    form = ContractForm(obj=contract)
    
    # Populate choices
    form.supplier_id.choices = [(0, 'Selecione...')] + [(s.id, s.name) for s in Supplier.query.filter_by(tenant_id=get_tenant_id(), active=True).all()]
    form.category_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in ContractCategory.query.filter_by(tenant_id=get_tenant_id()).all()]
    form.program_id.choices = [(0, 'Selecione...')] + [(p.id, p.name) for p in FinancialProgram.query.filter_by(tenant_id=get_tenant_id()).all()]
    form.services.choices = [(s.id, s.name) for s in ServiceType.query.filter_by(tenant_id=get_tenant_id()).all()]

    if request.method == 'GET':
        form.purpose.data = contract.purpose.name
        form.modality.data = contract.modality.name
        if contract.purpose == ContractPurposeEnum.SERVICOS:
            form.services.data = [s.id for s in contract.services]

    if form.validate_on_submit():
        if form.supplier_id.data == 0 or form.category_id.data == 0 or form.program_id.data == 0:
            flash('Por favor, selecione opções válidas para Fornecedor, Categoria e Programa Financeiro.', 'danger')
            return render_template('contracts/contract_form.html', form=form, title="Editar Contrato")

        contract.supplier_id = form.supplier_id.data
        contract.purpose = ContractPurposeEnum[form.purpose.data]
        contract.modality = ContractModalityEnum[form.modality.data]
        contract.category_id = form.category_id.data
        contract.program_id = form.program_id.data
        contract.contract_number = form.contract_number.data
        contract.signature_date = form.signature_date.data
        contract.validity_start = form.validity_start.data
        contract.validity_end = form.validity_end.data

        # Update services list
        contract.services = []
        if contract.purpose == ContractPurposeEnum.SERVICOS and form.services.data:
            selected_services = ServiceType.query.filter(ServiceType.id.in_(form.services.data), ServiceType.tenant_id == get_tenant_id()).all()
            contract.services.extend(selected_services)

        db.session.commit()
        flash('Contrato atualizado com sucesso!', 'success')
        return redirect(url_for('contracts.list_contracts'))

    return render_template('contracts/contract_form.html', form=form, title="Editar Contrato")

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_contract(id):
    contract = Contract.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    contract.services = [] # Clear associations first
    db.session.delete(contract)
    db.session.commit()
    flash('Contrato excluído com sucesso!', 'success')
    return redirect(url_for('contracts.list_contracts'))

# ==========================================
# EVALUATION ITEMS CRUD
# ==========================================

@bp.route('/evaluation-items')
@login_required
def list_evaluation_items():
    items = ContractEvaluationItem.query.filter_by(tenant_id=get_tenant_id()).all()
    return render_template('contracts/evaluation_items.html', items=items, title="Itens de Avaliação de Contratos")

@bp.route('/evaluation-items/new', methods=['GET', 'POST'])
@login_required
def new_evaluation_item():
    form = ContractEvaluationItemForm()
    if form.validate_on_submit():
        item = ContractEvaluationItem(
            tenant_id=get_tenant_id(),
            name=form.name.data,
            description=form.description.data,
            active=form.active.data
        )
        db.session.add(item)
        db.session.commit()
        flash('Item de avaliação criado com sucesso!', 'success')
        return redirect(url_for('contracts.list_evaluation_items'))
    return render_template('contracts/evaluation_item_form.html', form=form, title="Novo Item de Avaliação")

@bp.route('/evaluation-items/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_evaluation_item(id):
    item = ContractEvaluationItem.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    form = ContractEvaluationItemForm(obj=item)
    if form.validate_on_submit():
        item.name = form.name.data
        item.description = form.description.data
        item.active = form.active.data
        db.session.commit()
        flash('Item de avaliação atualizado com sucesso!', 'success')
        return redirect(url_for('contracts.list_evaluation_items'))
    return render_template('contracts/evaluation_item_form.html', form=form, title="Editar Item de Avaliação")

@bp.route('/evaluation-items/<int:id>/delete', methods=['POST'])
@login_required
def delete_evaluation_item(id):
    item = ContractEvaluationItem.query.filter_by(id=id, tenant_id=get_tenant_id()).first_or_404()
    # Check if there are evaluations using this item before deleting
    if ContractEvaluationGrade.query.filter_by(item_id=id).first():
        flash('Não é possível excluir este item pois já existem avaliações vinculadas a ele. Tente inativá-lo.', 'danger')
    else:
        db.session.delete(item)
        db.session.commit()
        flash('Item de avaliação excluído com sucesso!', 'success')
    return redirect(url_for('contracts.list_evaluation_items'))


# ==========================================
# EVALUATIONS
# ==========================================

@bp.route('/evaluations')
@login_required
def list_evaluations():
    evaluations = ContractEvaluation.query.filter_by(tenant_id=get_tenant_id()).order_by(ContractEvaluation.evaluation_date.desc()).all()
    return render_template('contracts/evaluations.html', evaluations=evaluations, title="Avaliações de Contratos")

@bp.route('/<int:contract_id>/evaluate', methods=['GET', 'POST'])
@login_required
def evaluate_contract(contract_id):
    contract = Contract.query.filter_by(id=contract_id, tenant_id=get_tenant_id()).first_or_404()
    form = ContractEvaluationForm()
    
    # Populate schools
    schools = TeachingUnit.query.filter_by(tenant_id=get_tenant_id()).order_by(TeachingUnit.name).all()
    form.school_id.choices = [(0, 'Selecione a Escola...')] + [(s.id, s.name) for s in schools]
    
    # Get active evaluation items
    items = ContractEvaluationItem.query.filter_by(tenant_id=get_tenant_id(), active=True).all()
    if not items:
        flash('Nenhum item de avaliação ativo encontrado. Cadastre itens antes de avaliar um contrato.', 'warning')
        return redirect(url_for('contracts.list_contracts'))

    if request.method == 'GET':
        form.evaluation_date.data = datetime.date.today()

    if form.validate_on_submit():
        if form.school_id.data == 0:
            flash('Por favor, selecione uma escola.', 'danger')
            return render_template('contracts/evaluation_form.html', form=form, contract=contract, items=items, title="Avaliar Contrato")

        # Validate grades and justifications
        grades_data = []
        has_error = False
        
        for item in items:
            grade_val = request.form.get(f'grade_{item.id}')
            justification_val = request.form.get(f'justification_{item.id}')
            
            if not grade_val or not grade_val.strip():
                flash(f'Informe a nota para o item "{item.name}".', 'danger')
                has_error = True
                continue
                
            try:
                grade_int = int(grade_val)
                if grade_int < 0 or grade_int > 10:
                    raise ValueError()
            except ValueError:
                flash(f'Nota inválida para o item "{item.name}". Deve ser de 0 a 10.', 'danger')
                has_error = True
                continue
                
            # Rule: <= 5 requires justification
            if grade_int <= 5 and (not justification_val or not justification_val.strip()):
                flash(f'Justificativa é obrigatória para o item "{item.name}" (nota <= 5).', 'danger')
                has_error = True
                continue
                
            grades_data.append({
                'item_id': item.id,
                'grade': grade_int,
                'justification': justification_val
            })
            
        if has_error:
            # Re-render with existing data to not lose everything (would need JS to repopulate or just let user re-fill)
            # In a real app we'd pass the values back, but here we can just re-render
            return render_template('contracts/evaluation_form.html', form=form, contract=contract, items=items, title="Avaliar Contrato")
            
        # Create evaluation
        evaluation = ContractEvaluation(
            tenant_id=get_tenant_id(),
            contract_id=contract.id,
            school_id=form.school_id.data,
            evaluator_id=current_user.id,
            evaluation_date=form.evaluation_date.data,
            comments=form.comments.data
        )
        db.session.add(evaluation)
        db.session.flush() # get ID
        
        for g in grades_data:
            grade = ContractEvaluationGrade(
                evaluation_id=evaluation.id,
                item_id=g['item_id'],
                grade=g['grade'],
                justification=g['justification']
            )
            db.session.add(grade)
            
        db.session.commit()
        flash('Avaliação de contrato salva com sucesso!', 'success')
        return redirect(url_for('contracts.list_evaluations'))

    return render_template('contracts/evaluation_form.html', form=form, contract=contract, items=items, title="Avaliar Contrato")
