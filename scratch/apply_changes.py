import re

# 2. Update app/models.py
models_path = r'c:\Users\pc\source\sgeplus\app\models.py'
with open(models_path, 'r', encoding='utf-8') as f:
    models_content = f.read()
if 'allow_teacher_view_answers' not in models_content:
    models_content = models_content.replace(
        'allow_teacher_entry = db.Column(db.Boolean, default=False)',
        'allow_teacher_entry = db.Column(db.Boolean, default=False)\n    allow_teacher_view_answers = db.Column(db.Boolean, default=True)'
    )
    with open(models_path, 'w', encoding='utf-8') as f:
        f.write(models_content)
    print('models.py updated.')

# 3. Update app/forms.py
forms_path = r'c:\Users\pc\source\sgeplus\app\forms.py'
with open(forms_path, 'r', encoding='utf-8') as f:
    forms_content = f.read()
if 'allow_teacher_view_answers' not in forms_content:
    forms_content = forms_content.replace(
        "allow_teacher_entry = BooleanField('Permitir que o professor registre as respostas dos alunos', default=True)",
        "allow_teacher_entry = BooleanField('Permitir que o professor registre as respostas dos alunos', default=True)\n    allow_teacher_view_answers = BooleanField('Permitir que o professor veja as respostas corretas?', default=True)"
    )
    with open(forms_path, 'w', encoding='utf-8') as f:
        f.write(forms_content)
    print('forms.py updated.')

# 4. Update app/routes/exams.py
exams_path = r'c:\Users\pc\source\sgeplus\app\routes\exams.py'
with open(exams_path, 'r', encoding='utf-8') as f:
    exams_content = f.read()
if 'allow_teacher_view_answers' not in exams_content:
    exams_content = exams_content.replace(
        "'allow_teacher_entry': form.allow_teacher_entry.data,",
        "'allow_teacher_entry': form.allow_teacher_entry.data,\n            'allow_teacher_view_answers': form.allow_teacher_view_answers.data,"
    )
    exams_content = exams_content.replace(
        "allow_teacher_entry=form_data['allow_teacher_entry'] if not is_teacher else True,",
        "allow_teacher_entry=form_data['allow_teacher_entry'] if not is_teacher else True,\n                    allow_teacher_view_answers=form_data['allow_teacher_view_answers'] if not is_teacher else True,"
    )
    with open(exams_path, 'w', encoding='utf-8') as f:
        f.write(exams_content)
    print('routes/exams.py updated.')

# 5. Update generate.html
generate_path = r'c:\Users\pc\source\sgeplus\app\templates\exams\generate.html'
with open(generate_path, 'r', encoding='utf-8') as f:
    generate_content = f.read()
if 'allow_teacher_view_answers' not in generate_content:
    generate_content = generate_content.replace(
        """                        {% if not is_teacher and not is_unidade %}
                        <div class="form-check">
                            {{ form.allow_teacher_entry(class="form-check-input") }}
                            {{ form.allow_teacher_entry.label(class="form-check-label") }}
                        </div>
                        {% endif %}""",
        """                        {% if not is_teacher and not is_unidade %}
                        <div class="form-check mb-2">
                            {{ form.allow_teacher_entry(class="form-check-input") }}
                            {{ form.allow_teacher_entry.label(class="form-check-label") }}
                        </div>
                        <div class="form-check mb-3">
                            {{ form.allow_teacher_view_answers(class="form-check-input") }}
                            {{ form.allow_teacher_view_answers.label(class="form-check-label") }}
                        </div>
                        {% endif %}"""
    )
    with open(generate_path, 'w', encoding='utf-8') as f:
        f.write(generate_content)
    print('generate.html updated.')

# 6. Update view.html
view_path = r'c:\Users\pc\source\sgeplus\app\templates\exams\view.html'
with open(view_path, 'r', encoding='utf-8') as f:
    view_content = f.read()
    
if "{% set can_view_answers = current_user.is_admin or current_user.id == exam.created_by_id or exam.allow_teacher_view_answers %}" not in view_content:
    view_content = view_content.replace(
        "<!-- TEACHER VIEW: Standard Order, Highlight Correct -->\n    {% for item in exam.items %}",
        "<!-- TEACHER VIEW: Standard Order, Highlight Correct -->\n    {% set can_view_answers = current_user.is_admin or current_user.id == exam.created_by_id or exam.allow_teacher_view_answers %}\n    {% for item in exam.items %}"
    )

if "{% if exam.total_value and exam.total_value > 0.0 %}" not in view_content:
    view_content = view_content.replace(
        """    <div class="mb-4 break-inside-avoid">
        <p><strong>{{ loop.index }}.</strong>
            ({% for d in item.question.descriptors %}{{ d.code }}{% if not loop.last %}, {% endif %}{% endfor %})
            {{ item.question.statement }}
        </p>
        <div class="ms-3">
            {% set alts = item.question.get_alternatives() %}
            {% for key, val in alts.items() %}
            <div class="form-check">
                <input class="form-check-input" type="radio" disabled {% if key==item.question.correct_alternative
                    %}checked{% endif %}>
                <label
                    class="form-check-label {% if key == item.question.correct_alternative %}text-success fw-bold{% endif %}">
                    {{ key }}) {{ val }}
                </label>
            </div>
            {% endfor %}
        </div>""",
        """    <div class="mb-4 break-inside-avoid">
        <p><strong>{{ loop.index }}.</strong>
            {% if exam.total_value and exam.total_value > 0.0 %}
                <span class="badge bg-secondary me-1" title="Valor da questão">{{ "%.2f"|format(item.value) }} pts</span>
            {% endif %}
            ({% for d in item.question.descriptors %}{{ d.code }}{% if not loop.last %}, {% endif %}{% endfor %})
            {{ item.question.statement }}
        </p>
        <div class="ms-3">
            {% set alts = item.question.get_alternatives() %}
            {% for key, val in alts.items() %}
            <div class="form-check">
                <input class="form-check-input" type="radio" disabled {% if can_view_answers and key==item.question.correct_alternative %}checked{% endif %}>
                <label class="form-check-label {% if can_view_answers and key == item.question.correct_alternative %}text-success fw-bold{% endif %}">
                    {{ key }}) {{ val }}
                </label>
            </div>
            {% endfor %}
        </div>"""
    )
    with open(view_path, 'w', encoding='utf-8') as f:
        f.write(view_content)
    print('view.html updated.')

