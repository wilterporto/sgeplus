import re

filepath = r'c:\Users\pc\source\sgeplus\app\templates\questions\list.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

filter_html = """
<!-- Filtros -->
<div class="card mb-4 shadow-sm border-0">
    <div class="card-body bg-light">
        <form method="GET" action="{{ url_for('questions.list_questions') }}" class="row g-3">
            <div class="col-md-3">
                <label for="subject_id" class="form-label small fw-bold text-muted mb-1">Componente Curricular</label>
                <select name="subject_id" id="subject_id" class="form-select shadow-none">
                    <option value="">Todos</option>
                    {% for subj in subjects %}
                    <option value="{{ subj.id }}" {% if filter_subject == subj.id %}selected{% endif %}>{{ subj.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3">
                <label for="matrix_id" class="form-label small fw-bold text-muted mb-1">Matriz de Referência</label>
                <select name="matrix_id" id="matrix_id" class="form-select shadow-none">
                    <option value="">Todas</option>
                    {% for mat in matrices %}
                    <option value="{{ mat.id }}" {% if filter_matrix == mat.id %}selected{% endif %}>{{ mat.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3">
                <label for="school_year_id" class="form-label small fw-bold text-muted mb-1">Ano Escolar</label>
                <select name="school_year_id" id="school_year_id" class="form-select shadow-none">
                    <option value="">Todos</option>
                    {% for year in years %}
                    <option value="{{ year.id }}" {% if filter_year == year.id %}selected{% endif %}>{{ year.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3 d-flex align-items-end gap-2">
                <button type="submit" class="btn btn-primary shadow-none w-100">
                    <i class="bi bi-funnel"></i> Filtrar
                </button>
                {% if filter_subject or filter_matrix or filter_year %}
                <a href="{{ url_for('questions.list_questions') }}" class="btn btn-outline-secondary shadow-none" title="Limpar Filtros">
                    <i class="bi bi-x-circle"></i>
                </a>
                {% endif %}
            </div>
        </form>
    </div>
</div>
"""

# Insert filters right before <!-- Quill Theme -->
content = content.replace("<!-- Quill Theme -->", filter_html + "\n<!-- Quill Theme -->")

# Update pagination
content = content.replace(
    "href=\"{{ url_for('questions.list_questions', page=questions.prev_num) }}\"",
    "href=\"{{ url_for('questions.list_questions', page=questions.prev_num, subject_id=filter_subject, matrix_id=filter_matrix, school_year_id=filter_year) }}\""
)
content = content.replace(
    "href=\"{{ url_for('questions.list_questions', page=questions.next_num) }}\"",
    "href=\"{{ url_for('questions.list_questions', page=questions.next_num, subject_id=filter_subject, matrix_id=filter_matrix, school_year_id=filter_year) }}\""
)
content = content.replace(
    "value=\"{{ url_for('questions.list_questions', page=p) }}\"",
    "value=\"{{ url_for('questions.list_questions', page=p, subject_id=filter_subject, matrix_id=filter_matrix, school_year_id=filter_year) }}\""
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Template updated successfully.")
