import re

filepath = r'c:\Users\pc\source\sgeplus\app\templates\matrices\descriptors.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the "Filtrar por Matriz" dropdown
# It starts with <!-- Filter dropdown --> and ends with </div> right before </div> </div> for the toolbar
filter_dropdown_regex = r'<!-- Filter dropdown -->.*?</div>\s*</div>\s*</div>'
content = re.sub(r'<!-- Filter dropdown -->.*?</ul>\s*</div>', '', content, flags=re.DOTALL)

# 2. Add the filter form right above <div class="row"> (the one that contains the table)
filter_html = """
<!-- Filtros -->
<div class="card mb-4 shadow-sm border-0">
    <div class="card-body bg-light">
        <form method="GET" action="{{ url_for('matrices.list_descriptors') }}" class="row g-3">
            <div class="col-md-3">
                <label for="subject_id" class="form-label small fw-bold text-muted mb-1">Componente Curricular</label>
                <select name="subject_id" id="subject_id" class="form-select shadow-none">
                    <option value="">Todos</option>
                    {% for subj in subjects %}
                    <option value="{{ subj.id }}" {% if current_subject_id == subj.id %}selected{% endif %}>{{ subj.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3">
                <label for="matrix_id" class="form-label small fw-bold text-muted mb-1">Matriz de Referência</label>
                <select name="matrix_id" id="matrix_id" class="form-select shadow-none">
                    <option value="">Todas</option>
                    {% for mat in matrices %}
                    <option value="{{ mat.id }}" {% if current_matrix_id == mat.id %}selected{% endif %}>{{ mat.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3">
                <label for="school_year_id" class="form-label small fw-bold text-muted mb-1">Ano Escolar</label>
                <select name="school_year_id" id="school_year_id" class="form-select shadow-none">
                    <option value="">Todos</option>
                    {% for year in years %}
                    <option value="{{ year.id }}" {% if current_year_id == year.id %}selected{% endif %}>{{ year.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3 d-flex align-items-end gap-2">
                <button type="submit" class="btn btn-primary shadow-none w-100">
                    <i class="bi bi-funnel"></i> Filtrar
                </button>
                {% if current_subject_id or current_matrix_id or current_year_id %}
                <a href="{{ url_for('matrices.list_descriptors') }}" class="btn btn-outline-secondary shadow-none" title="Limpar Filtros">
                    <i class="bi bi-x-circle"></i>
                </a>
                {% endif %}
            </div>
        </form>
    </div>
</div>

<div class="row">"""

# Replace <div class="row"> with the filter + row, but we need to target the correct row
# Since there are multiple <div class="row">, let's target the one right before <!-- List -->
content = content.replace('<div class="row">\n    <!-- List -->', filter_html + '\n    <!-- List -->')

# Update pagination links to include subject_id and school_year_id
content = content.replace(
    "href=\"{{ url_for('matrices.list_descriptors', page=pagination.prev_num, matrix_id=current_matrix_id) }}\"",
    "href=\"{{ url_for('matrices.list_descriptors', page=pagination.prev_num, matrix_id=current_matrix_id, subject_id=current_subject_id, school_year_id=current_year_id) }}\""
)
content = content.replace(
    "href=\"{{ url_for('matrices.list_descriptors', page=pagination.next_num, matrix_id=current_matrix_id) }}\"",
    "href=\"{{ url_for('matrices.list_descriptors', page=pagination.next_num, matrix_id=current_matrix_id, subject_id=current_subject_id, school_year_id=current_year_id) }}\""
)
content = content.replace(
    "value=\"{{ url_for('matrices.list_descriptors', page=p, matrix_id=current_matrix_id) }}\"",
    "value=\"{{ url_for('matrices.list_descriptors', page=p, matrix_id=current_matrix_id, subject_id=current_subject_id, school_year_id=current_year_id) }}\""
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Descriptors template updated successfully.")
