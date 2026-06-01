from app import create_app, db
from app.models import User, Question, Descriptor, Exam

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Question': Question, 'Descriptor': Descriptor, 'Exam': Exam}

if __name__ == '__main__':
    # Auto-increment version on startup (only in main process to avoid double increment with reloader)
    import os
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        try:
            with open('app/version.txt', 'r') as f:
                v_str = f.read().strip()
                parts = v_str.split('.')
                if len(parts) == 3:
                    new_patch = int(parts[2]) + 1
                    new_version = f"{parts[0]}.{parts[1]}.{new_patch}"
                    with open('app/version.txt', 'w') as f_out:
                        f_out.write(new_version)
                    print(f" * Build Version Updated: {v_str} -> {new_version}")
        except Exception as e:
            print(f" * Failed to update version: {e}")

    app.run(debug=True)
