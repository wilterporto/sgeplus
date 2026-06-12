from app import create_app, db
from app.models import Professor, User

app = create_app()

with app.app_context():
    p_list = Professor.query.filter(Professor.cpf.like('%.%')).all()
    print(f'{len(p_list)} professors to check')
    
    fixed = 0
    not_fixed = 0
    for p in p_list:
        if p.user_id:
            u = db.session.get(User, p.user_id)
            if u and len(u.username) == 11 and u.username.isdigit():
                p.cpf = u.username
                fixed += 1
            else:
                not_fixed += 1
        else:
            not_fixed += 1
            
        if fixed % 500 == 0:
            db.session.commit()
            
    db.session.commit()
    print(f'Fixed {fixed} professors, {not_fixed} could not be fixed via User.')
