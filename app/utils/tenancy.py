from flask import session
from flask_login import current_user

def filter_by_tenant(query, model):
    """
    Filters a SQLAlchemy query by the current user's tenant_id.
    If the user is a system admin (Super Admin), filters by the active_tenant_id in session.
    If they are a system admin and haven't selected a tenant, blocks access (returns empty).
    Additionally, hides system admin users from any tenant-specific User lists.
    """
    try:
        if not current_user or not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
            return query
            
        # Ocultação automática de Super Admins globais em listagens de usuários do tenant
        if model.__name__ == 'User':
            # Se for usuário comum do tenant, ou Super Admin autenticado em algum tenant
            is_sys_admin = hasattr(current_user, 'is_system_admin') and current_user.is_system_admin
            if not is_sys_admin or session.get('active_tenant_id'):
                query = query.filter(model.is_system_admin == False)
            
        # Tratamento de Super Admin (is_system_admin == True)
        if hasattr(current_user, 'is_system_admin') and current_user.is_system_admin:
            active_tenant_id = session.get('active_tenant_id')
            if active_tenant_id:
                # Se autenticado em um tenant, filtra os dados por ele
                if hasattr(model, 'tenant_id'):
                    return query.filter(model.tenant_id == active_tenant_id)
            else:
                # Global context: no tenant selected
                if model.__name__ == 'User':
                    return query.filter(model.tenant_id == None)
            return query
            
        # Tratamento de usuários comuns do tenant
        if hasattr(model, 'tenant_id') and hasattr(current_user, 'tenant_id'):
            return query.filter(model.tenant_id == current_user.tenant_id)
    except Exception:
        # Fallback in case of runtime proxy resolution issues outside request context
        pass
        
    return query

def get_tenant_id():
    """
    Returns the current active tenant_id.
    If system admin is authenticated into a tenant, returns the active tenant_id in session.
    """
    try:
        if not current_user or not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
            return None
            
        if hasattr(current_user, 'is_system_admin') and current_user.is_system_admin:
            return session.get('active_tenant_id')
            
        if hasattr(current_user, 'tenant_id'):
            return current_user.tenant_id
    except Exception:
        pass
    return None
