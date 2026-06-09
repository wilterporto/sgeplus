import re

routes_path = r'c:\Users\pc\source\sgeplus\app\routes\professors.py'
with open(routes_path, 'r', encoding='utf-8') as f:
    routes_content = f.read()

new_routes_code = """# --- TEACHER PORTAL ROUTES ---

@professors_bp.route('/dashboard')
@flask_login.login_required
def dashboard():
    # Check if user is a professor AND has active role professor
    from flask import session
    if not flask_login.current_user.professor_profile or session.get('active_role') != 'professor':
        flask.flash('Acesso restrito a professores.', 'danger')
        return flask.redirect(url_for('main.index'))
        
    professor = flask_login.current_user.professor_profile
    
    # Group by School -> Class
    schools_map = {}
    
    for assignment in professor.assignments:
        c = assignment.enrolled_class
        if not c or not c.teaching_unit:
            continue
            
        school_name = c.teaching_unit.name
        if school_name not in schools_map:
            schools_map[school_name] = {}
            
        if c.id not in schools_map[school_name]:
            schools_map[school_name][c.id] = c.name
            
    sorted_schools = []
    for school_name in sorted(schools_map.keys()):
        sorted_classes = [{'id': cid, 'name': cname} for cid, cname in sorted(schools_map[school_name].items(), key=lambda x: x[1])]
        sorted_schools.append({'name': school_name, 'classes': sorted_classes})
        
    class_id = request.args.get('class_id', type=int)
    students_pagination = None
    klass = None
    
    if class_id:
        has_access = False
        for a in professor.assignments:
            if a.class_id == class_id:
                has_access = True
                break
                
        if not has_access:
            flask.flash('Você não tem acesso a esta turma.', 'danger')
            return flask.redirect(url_for('professors.dashboard'))
            
        from app.models import Class, Student, Enrollment
        class_query = Class.query.filter_by(id=class_id)
        class_query = filter_by_tenant(class_query, Class)
        klass = class_query.first_or_404()
        
        page = request.args.get('page', 1, type=int)
        students_query = Student.query.join(Enrollment)\\
            .filter(Enrollment.class_id == class_id, Enrollment.active == True)
        students_query = filter_by_tenant(students_query, Student)
        students_pagination = students_query.order_by(Student.name)\\
            .paginate(page=page, per_page=30)
            
    return flask.render_template('professors/dashboard.html', 
                                 schools=sorted_schools, 
                                 selected_class_id=class_id,
                                 klass=klass,
                                 students=students_pagination)

@professors_bp.route('/class/<int:class_id>/students')
@flask_login.login_required
def class_students(class_id):
    return redirect(url_for('professors.dashboard', class_id=class_id))
"""

routes_content = re.sub(
    r'# --- TEACHER PORTAL ROUTES ---.*',
    new_routes_code,
    routes_content,
    flags=re.DOTALL
)

with open(routes_path, 'w', encoding='utf-8') as f:
    f.write(routes_content)


template_path = r'c:\Users\pc\source\sgeplus\app\templates\professors\dashboard.html'
new_template_code = """{% extends "base.html" %}

{% block content %}
<div class="row mb-4">
    <div class="col">
        <h2 class="h3">Minhas Turmas</h2>
        <p class="text-muted">Selecione uma turma para visualizar os alunos.</p>
    </div>
</div>

<div class="card shadow-sm border-0 mb-4">
    <div class="card-body bg-light">
        <form method="GET" action="{{ url_for('professors.dashboard') }}" class="row g-3 align-items-end" id="classSelectForm">
            <div class="col-md-6">
                <label for="class_id" class="form-label small fw-bold text-muted mb-1">Selecione a Turma</label>
                <select name="class_id" id="class_id" class="form-select shadow-none" onchange="document.getElementById('classSelectForm').submit();">
                    <option value="">Escolha uma turma...</option>
                    {% for school in schools %}
                        <optgroup label="{{ school.name }}">
                            {% for c in school.classes %}
                                <option value="{{ c.id }}" {% if selected_class_id == c.id %}selected{% endif %}>{{ c.name }}</option>
                            {% endfor %}
                        </optgroup>
                    {% endfor %}
                </select>
            </div>
        </form>
    </div>
</div>

{% if selected_class_id and klass %}
<div class="card shadow-sm border-0">
    <div class="card-header bg-white pt-3 pb-2">
        <h5 class="mb-0 text-primary">{{ klass.name }} <small class="text-muted">({{ klass.teaching_unit.name }})</small></h5>
    </div>
    <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-hover mb-0 align-middle">
                <thead class="table-light">
                    <tr>
                        <th style="width: 20%;">Matrícula</th>
                        <th style="width: 60%;">Nome</th>
                        <th style="width: 20%;">Data de Nascimento</th>
                    </tr>
                </thead>
                <tbody>
                    {% for student in students.items %}
                    <tr>
                        <td class="font-monospace">{{ student.registration_number }}</td>
                        <td class="fw-bold">{{ student.name }}</td>
                        <td>{{ student.birth_date.strftime('%d/%m/%Y') if student.birth_date else '-' }}</td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="3" class="text-center py-5 text-muted">
                            Nenhum aluno matriculado nesta turma.
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

{% if students.pages > 1 %}
<nav aria-label="Page navigation" class="mt-4">
    <ul class="pagination justify-content-center">
        {% if students.has_prev %}
        <li class="page-item">
            <a class="page-link shadow-none"
                href="{{ url_for('professors.dashboard', class_id=klass.id, page=students.prev_num) }}">Anterior</a>
        </li>
        {% endif %}
        <li class="page-item disabled"><span class="page-link shadow-none">{{ students.page }} / {{ students.pages }}</span></li>
        {% if students.has_next %}
        <li class="page-item">
            <a class="page-link shadow-none"
                href="{{ url_for('professors.dashboard', class_id=klass.id, page=students.next_num) }}">Próxima</a>
        </li>
        {% endif %}
    </ul>
</nav>
{% endif %}
{% endif %}
{% endblock %}
"""

with open(template_path, 'w', encoding='utf-8') as f:
    f.write(new_template_code)

print("Dashboard routes and templates updated successfully.")
