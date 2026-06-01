import json
from flask_login import current_user
from app import db
from app.models import AuditLog
from app.utils.timezone import get_brasilia_time

def log_audit(action, target_table, target_id, details=None):
    """
    Registra uma ação do usuário na tabela AuditLog usando o fuso horário de Brasília.
    Evita lançar exceções para não interromper o fluxo principal se a auditoria falhar.
    """
    try:
        user_id = None
        if current_user and current_user.is_authenticated:
            try:
                user_id = current_user.id
            except:
                pass
                
        details_str = None
        if details:
            if isinstance(details, (dict, list)):
                details_str = json.dumps(details, ensure_ascii=False)
            else:
                details_str = str(details)
                
        log = AuditLog(
            user_id=user_id,
            action=action,
            target_table=target_table,
            target_id=target_id,
            details=details_str,
            timestamp=get_brasilia_time()
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        # Silencioso em produção, printa para log local
        print(f"Erro ao gravar log de auditoria: {str(e)}")
