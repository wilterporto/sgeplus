import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import OmbudsmanNature

app = create_app()

with app.app_context():
    names = ['Reclamação', 'Elogio', 'Solicitação', 'Sugestão', 'Denúncia']
    
    # We already have 5 entries. Let's just fix their names based on ID if they match the bad encoding
    natures = OmbudsmanNature.query.order_by(OmbudsmanNature.id).all()
    for i, n in enumerate(natures):
        if i < len(names):
            print(f"Updating {n.name} -> {names[i]}")
            n.name = names[i]
            
    db.session.commit()
    print("Names fixed.")
