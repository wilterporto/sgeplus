import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import OmbudsmanNature, OmbudsmanSubject, OmbudsmanManifestation

app = create_app()

with app.app_context():
    print("Starting Natures Seed...")
    
    standard_names = ["Reclamação", "Elogio", "Solicitação", "Sugestão", "Denúncia"]
    global_natures = {}
    
    for name in standard_names:
        n = OmbudsmanNature.query.filter_by(name=name, tenant_id=None).first()
        if not n:
            n = OmbudsmanNature(name=name, active=True, tenant_id=None)
            db.session.add(n)
            print(f"Created global nature: {name}")
        global_natures[name] = n
        
    db.session.commit()
    print("Global natures ensured.")
    
    old_natures = OmbudsmanNature.query.filter(OmbudsmanNature.tenant_id != None).all()
    
    for old_n in old_natures:
        target_name = old_n.name if old_n.name in standard_names else "Reclamação"
        target_nature = global_natures[target_name]
        
        print(f"Mapping old nature '{old_n.name}' (ID: {old_n.id}) to '{target_nature.name}' (ID: {target_nature.id})")
        
        OmbudsmanSubject.query.filter_by(nature_id=old_n.id).update({OmbudsmanSubject.nature_id: target_nature.id})
        OmbudsmanManifestation.query.filter_by(nature_id=old_n.id).update({OmbudsmanManifestation.nature_id: target_nature.id})
        
        db.session.delete(old_n)

    db.session.commit()
    print("Migration completed.")