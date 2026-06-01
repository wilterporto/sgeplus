import os

# Get base directory
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-idebmais-secret'
    # Use absolute path for the database file
    db_path = os.path.join(basedir, 'instance', 'idebmais.db')
    
    # Render's PostgreSQL URL starts with postgres://, replace with postgresql:// for compatibility with SQLAlchemy >= 1.4
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = db_url or 'sqlite:///' + db_path
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True
    
    # Security Configs
    SESSION_COOKIE_HTTPONLY = True
    # Em produção, usar Secure (HTTPS obrigatório). Em desenvolvimento, permitir HTTP para acesso remoto.
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_DEBUG', '0') != '1'
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Configure engine options conditionally
    if SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "connect_args": {
                "timeout": 30,
                "check_same_thread": False
            }
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 1800
        }


