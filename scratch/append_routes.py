import sys
import os

content = open('app/routes/academic.py', 'r', encoding='utf-8').read()

new_routes = '''

# --- Pedagogical Metrics Section ---

@academic_bp.route('/pedagogical-metrics', methods=['GET'])
@login_required
def list_pedagogical_metrics():
    from app.models import PedagogicalMetric
    form = ImportPedagogicalMetricsForm()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = PedagogicalMetric.query
    query = filter_by_tenant(query, PedagogicalMetric)
    
    if search:
        query = query.filter(PedagogicalMetric.evaluation_name.ilike(f'%{search}%'))
        
    metrics = query.order_by(PedagogicalMetric.created_at.desc()).paginate(page=page, per_page=30)
    
    return render_template('academic/pedagogical_metrics.html', metrics=metrics, form=form)

@academic_bp.route('/pedagogical-metrics/import', methods=['POST'])
@login_required
def import_pedagogical_metrics():
    if current_user.role not in ['admin', 'regional_manager']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('academic.list_pedagogical_metrics'))
        
    if ImportJob.is_any_running():
        flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
        return redirect(url_for('academic.list_pedagogical_metrics'))
        
    form = ImportPedagogicalMetricsForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        task_id = request.form.get('X-Progress-ID')
        
        uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        filepath = os.path.join(uploads_dir, filename)
        file.save(filepath)
        
        job = ImportJob(
            user_id=current_user.id,
            import_type='PedagogicalMetrics',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()
        
        thread = threading.Thread(
            target=_process_pedagogical_metrics_import,
            args=(current_app._get_current_object(), job.id, filepath, task_id)
        )
        thread.start()
        
        flash('A importação de métricas pedagógicas foi iniciada em segundo plano.', 'info')
    else:
        for field, errors in form.errors.items():
            flash(f"Erro em {getattr(form, field).label.text}: {', '.join(errors)}", 'danger')
            
    return redirect(url_for('academic.list_pedagogical_metrics'))

def _process_pedagogical_metrics_import(app, job_id, filepath, task_id=None):
    with app.app_context():
        start_import_task(task_id)
        job = ImportJob.query.get(job_id)
        if not job:
            fail_import_task(task_id, 'Job não encontrado')
            return
            
        job.status = 'processing'
        job.started_at = datetime.utcnow()
        db.session.commit()
        
        try:
            df = pd.read_excel(filepath)
            total_records = len(df)
            
            if total_records == 0:
                job.status = 'completed'
                job.details = 'O arquivo está vazio.'
                job.finished_at = datetime.utcnow()
                db.session.commit()
                finish_import_task(task_id, total_records)
                return
                
            required_columns = ['INEP_ESCOLA', 'AVALIACAO', 'DISCIPLINA', 'ANO', 'NOTA']
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(missing_cols)}")
                
            from app.models import TeachingUnit, PedagogicalMetric
            
            # Map INEP to TeachingUnit ID
            inep_codes = df['INEP_ESCOLA'].dropna().astype(str).unique().tolist()
            units = filter_by_tenant(TeachingUnit.query, TeachingUnit).filter(TeachingUnit.inep_code.in_(inep_codes)).all()
            inep_to_id = {u.inep_code: u.id for u in units}
            
            metrics_to_insert = []
            processed = 0
            
            for index, row in df.iterrows():
                inep = str(row['INEP_ESCOLA']) if pd.notna(row['INEP_ESCOLA']) else None
                if inep and inep in inep_to_id:
                    unit_id = inep_to_id[inep]
                    metrics_to_insert.append(
                        PedagogicalMetric(
                            tenant_id=job.tenant_id,
                            teaching_unit_id=unit_id,
                            evaluation_name=str(row['AVALIACAO']),
                            subject=str(row['DISCIPLINA']) if pd.notna(row['DISCIPLINA']) else None,
                            academic_year=str(row['ANO']) if pd.notna(row['ANO']) else None,
                            score=float(row['NOTA']) if pd.notna(row['NOTA']) else None,
                            created_at=get_brasilia_time()
                        )
                    )
                processed += 1
                if processed % 100 == 0:
                    update_import_progress(task_id, processed, total_records)
            
            if metrics_to_insert:
                db.session.bulk_save_objects(metrics_to_insert)
                db.session.commit()
                
            job.status = 'completed'
            job.details = f"{len(metrics_to_insert)} métricas importadas com sucesso."
            job.finished_at = datetime.utcnow()
            db.session.commit()
            
            finish_import_task(task_id, processed)
            
        except Exception as e:
            job.status = 'failed'
            job.details = str(e)
            job.finished_at = datetime.utcnow()
            db.session.commit()
            fail_import_task(task_id, str(e))
'''

if '# --- Pedagogical Metrics Section ---' not in content:
    content += new_routes
    with open('app/routes/academic.py', 'w', encoding='utf-8') as f:
        f.write(content)
