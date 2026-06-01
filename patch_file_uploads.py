import re
import glob

# Common logic to inject
inject_imports = "from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS\n"

# Patch main.py (logos)
def patch_main():
    with open('app/routes/main.py', 'r', encoding='utf-8') as f:
        c = f.read()
    if 'allowed_file' not in c:
        c = c.replace('from flask import ', inject_imports + 'from flask import ')
        # Find logo upload
        c = re.sub(r'(if form\.logo\.data:)', r'\1\n            if not allowed_file(form.logo.data.filename, ALLOWED_IMAGE_EXTENSIONS):\n                flash("Formato de logo inválido. Apenas PNG, JPG, JPEG e GIF são permitidos.", "danger")\n                return redirect(url_for("main.settings"))', c)
        c = re.sub(r'(if form\.login_background\.data:)', r'\1\n            if not allowed_file(form.login_background.data.filename, ALLOWED_IMAGE_EXTENSIONS):\n                flash("Formato de plano de fundo inválido. Apenas PNG, JPG, JPEG e GIF são permitidos.", "danger")\n                return redirect(url_for("main.settings"))', c)
        with open('app/routes/main.py', 'w', encoding='utf-8') as f:
            f.write(c)

# Patch academic.py (imports and logos)
def patch_academic():
    with open('app/routes/academic.py', 'r', encoding='utf-8') as f:
        c = f.read()
    if 'allowed_file' not in c:
        c = c.replace('from flask import ', inject_imports + 'from flask import ')
        c = re.sub(r'(file = request\.files\[\'file\'\]\s+if file\.filename == \'\'[^\n]+\n[^\n]+\n)', r'\1        if not allowed_file(file.filename, ALLOWED_IMPORT_EXTENSIONS):\n            flash("Formato de arquivo inválido. Apenas XLSX, XLS e CSV são permitidos.", "danger")\n            return redirect(request.url)\n', c)
        # Fix logos in academic (tenant logo)
        c = re.sub(r'(if form\.logo\.data:)', r'\1\n            if not allowed_file(form.logo.data.filename, ALLOWED_IMAGE_EXTENSIONS):\n                flash("Formato de logo inválido.", "danger")\n                return redirect(request.url)', c)
        c = re.sub(r'(if logo_file:)', r'\1\n            if not allowed_file(logo_file.filename, ALLOWED_IMAGE_EXTENSIONS):\n                flash("Formato de logo inválido.", "danger")\n                return redirect(request.url)', c)
        with open('app/routes/academic.py', 'w', encoding='utf-8') as f:
            f.write(c)

# Patch questions.py (imports and images)
def patch_questions():
    with open('app/routes/questions.py', 'r', encoding='utf-8') as f:
        c = f.read()
    if 'allowed_file' not in c:
        c = c.replace('from flask import ', inject_imports + 'from flask import ')
        c = re.sub(r'(file = request\.files\[\'file\'\]\s+if file\.filename == \'\'[^\n]+\n[^\n]+\n)', r'\1        if not allowed_file(file.filename, ALLOWED_IMPORT_EXTENSIONS):\n            flash("Formato de arquivo inválido.", "danger")\n            return redirect(request.url)\n', c)
        with open('app/routes/questions.py', 'w', encoding='utf-8') as f:
            f.write(c)

# Patch exams.py (imports)
def patch_exams():
    with open('app/routes/exams.py', 'r', encoding='utf-8') as f:
        c = f.read()
    if 'allowed_file' not in c:
        c = c.replace('from flask import ', inject_imports + 'from flask import ')
        c = re.sub(r'(file = request\.files\[\'file\'\]\s+if file\.filename == \'\'[^\n]+\n[^\n]+\n)', r'\1        if not allowed_file(file.filename, ALLOWED_IMPORT_EXTENSIONS):\n            flash("Formato de arquivo inválido.", "danger")\n            return redirect(request.url)\n', c)
        with open('app/routes/exams.py', 'w', encoding='utf-8') as f:
            f.write(c)

# Patch admin.py (imports)
def patch_admin():
    with open('app/routes/admin.py', 'r', encoding='utf-8') as f:
        c = f.read()
    if 'allowed_file' not in c:
        c = c.replace('from flask import ', inject_imports + 'from flask import ')
        c = re.sub(r'(file = request\.files\[\'file\'\]\s+if file\.filename == \'\'[^\n]+\n[^\n]+\n)', r'\1        if not allowed_file(file.filename, ALLOWED_IMPORT_EXTENSIONS):\n            flash("Formato de arquivo inválido.", "danger")\n            return redirect(request.url)\n', c)
        with open('app/routes/admin.py', 'w', encoding='utf-8') as f:
            f.write(c)
            
# Patch matrices.py (imports)
def patch_matrices():
    with open('app/routes/matrices.py', 'r', encoding='utf-8') as f:
        c = f.read()
    if 'allowed_file' not in c:
        c = c.replace('from flask import ', inject_imports + 'from flask import ')
        c = re.sub(r'(file = request\.files\[\'file\'\]\s+if file\.filename == \'\'[^\n]+\n[^\n]+\n)', r'\1        if not allowed_file(file.filename, ALLOWED_IMPORT_EXTENSIONS):\n            flash("Formato de arquivo inválido.", "danger")\n            return redirect(request.url)\n', c)
        with open('app/routes/matrices.py', 'w', encoding='utf-8') as f:
            f.write(c)

patch_main()
patch_academic()
patch_questions()
patch_exams()
patch_admin()
patch_matrices()
print("All files patched for secure uploads!")
