import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Migrating data to Enums...")
    
    # Map statuses
    status_map = {
        'Pendente': 1,
        'Aceita': 2,
        'Rejeitada': 3,
        'Tramitando': 4,
        'Resolvida': 5
    }
    
    for old_val, new_val in status_map.items():
        db.session.execute(text("UPDATE ombudsman_manifestation SET status = :new_val WHERE status = :old_val"), {"new_val": str(new_val), "old_val": old_val})
        
    # Map requester_type
    requester_map = {
        'Aluno': 1,
        'Servidor': 2,
        'Responsável aluno': 3,
        'Outro': 4
    }
    
    for old_val, new_val in requester_map.items():
        db.session.execute(text("UPDATE ombudsman_manifestation SET requester_type = :new_val WHERE requester_type = :old_val"), {"new_val": str(new_val), "old_val": old_val})

    # Map entry_mode
    entry_map = {
        'Portal da Comunidade': 1,
        'Site': 1, # fallback
        'E-mail': 2,
        'WhatsApp': 3,
        'Portal do Aluno': 4,
        'Aplicativo': 5,
        'Telefone': 6,
        'Presencial': 7,
        'Call-Center': 8
    }
    
    for old_val, new_val in entry_map.items():
        db.session.execute(text("UPDATE ombudsman_manifestation SET entry_mode = :new_val WHERE entry_mode = :old_val"), {"new_val": str(new_val), "old_val": old_val})

    db.session.commit()
    print("Migration of text to enums complete.")
