from app import create_app, db
from app.models import Student, User

app = create_app()

with app.app_context():
    s_list = Student.query.filter(Student.cpf.like('%.%')).all()
    print(f'{len(s_list)} students to check')
    
    fixed = 0
    not_fixed = 0
    for s in s_list:
        if s.user_id:
            # Query.get is legacy, but works. Use db.session.get for 2.0+
            u = db.session.get(User, s.user_id)
            if u and len(u.username) == 11 and u.username.isdigit():
                s.cpf = u.username
                fixed += 1
            else:
                not_fixed += 1
        else:
            not_fixed += 1
            
        if fixed % 1000 == 0:
            db.session.commit()
            
    db.session.commit()
    print(f'Fixed {fixed} students, {not_fixed} could not be fixed via User.')
