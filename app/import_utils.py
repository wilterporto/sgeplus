import uuid

# Global dictionary to store import progress
# Key: task_id, Value: { 'status': 'processing|completed|error', 'current': 0, 'total': 0, 'errors': [], 'message': '' }
import_progress = {}

def start_import_task(total, task_id=None):
    if not task_id:
        task_id = str(uuid.uuid4())
    import_progress[task_id] = {
        'status': 'processing',
        'current': 0,
        'total': total,
        'errors': [],
        'log_file': None,
        'message': 'Iniciando importação...'
    }
    return task_id

def update_import_progress(task_id, current, message=None, error=None):
    if task_id in import_progress:
        import_progress[task_id]['current'] = current
        if message:
            import_progress[task_id]['message'] = message
        if error:
            import_progress[task_id]['errors'].append(error)

def finish_import_task(task_id, message='Concluído', log_file=None):
    if task_id in import_progress:
        import_progress[task_id]['status'] = 'completed'
        import_progress[task_id]['message'] = message
        if log_file:
            import_progress[task_id]['log_file'] = log_file

def fail_import_task(task_id, error_message):
    if task_id in import_progress:
        import_progress[task_id]['status'] = 'error'
        import_progress[task_id]['message'] = error_message

def save_error_log(errors):
    if not errors:
        return None
    
    import os
    from flask import current_app
    from datetime import datetime
    
    log_dir = os.path.join(current_app.instance_path, 'import_logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    filename = f"log_erros_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.txt"
    filepath = os.path.join(log_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO DE ERROS DE IMPORTAÇÃO\n")
        f.write(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("-" * 40 + "\n\n")
        for err in errors:
            f.write(f"- {err}\n")
            
    return filename
