import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import CityRegionalMapping, TeachingUnit, City, Tenant

def init_city_regionals():
    app = create_app()
    with app.app_context():
        # Create the new table
        db.create_all()
        print("Table CityRegionalMapping created/verified.")
        
        # Populate based on existing schools
        # For each tenant
        tenants = Tenant.query.all()
        for tenant in tenants:
            print(f"Processing tenant: {tenant.name} (ID: {tenant.id})")
            
            # Find all schools with a parent_id (regional) and a municipio string
            schools = TeachingUnit.query.filter(
                TeachingUnit.tenant_id == tenant.id,
                TeachingUnit.type == 'Escola',
                TeachingUnit.parent_id != None,
                TeachingUnit.municipio != None
            ).all()
            
            # Keep track of mappings we've found to avoid DB roundtrips
            # Map: {city_name_upper: regional_id}
            tenant_mappings = {}
            for school in schools:
                m_name = school.municipio.strip().upper()
                if m_name not in tenant_mappings:
                    tenant_mappings[m_name] = school.parent_id
            
            print(f"Found {len(tenant_mappings)} distinct municipality mappings from schools.")
            
            # Now lookup city_ids
            # Filter cities by Tenant's UF if possible, else just look up by name
            if tenant.uf:
                cities = City.query.filter_by(uf=tenant.uf).all()
            else:
                cities = City.query.all()
                
            city_map = {c.name.strip().upper(): c.id for c in cities}
            
            added = 0
            for m_name, regional_id in tenant_mappings.items():
                city_id = city_map.get(m_name)
                if city_id:
                    # Check if exists
                    existing = CityRegionalMapping.query.filter_by(
                        tenant_id=tenant.id,
                        city_id=city_id
                    ).first()
                    
                    if not existing:
                        new_mapping = CityRegionalMapping(
                            tenant_id=tenant.id,
                            city_id=city_id,
                            regional_id=regional_id
                        )
                        db.session.add(new_mapping)
                        added += 1
            
            db.session.commit()
            print(f"Inserted {added} new mappings for tenant {tenant.name}.")

if __name__ == '__main__':
    init_city_regionals()
