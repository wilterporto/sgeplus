with open('app/templates/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                <li>
                    <a href="{{ url_for('services.list_orders') }}"
                        class="nav-link {% if 'orders' in request.endpoint %}active{% endif %}">
                        <i class="bi bi-tools me-2"></i> <span class="sidebar-text">Ordens de Serviço</span>
                    </a>
                </li>'''

repl = '''                <li>
                    <a href="{{ url_for('services.dashboard') }}"
                        class="nav-link {% if 'dashboard' in request.endpoint and 'services' in request.blueprint %}active{% endif %}">
                        <i class="bi bi-speedometer2 me-2"></i> <span class="sidebar-text">Dashboard de OS</span>
                    </a>
                </li>
                <li>
                    <a href="{{ url_for('services.list_orders') }}"
                        class="nav-link {% if 'orders' in request.endpoint %}active{% endif %}">
                        <i class="bi bi-tools me-2"></i> <span class="sidebar-text">Ordens de Serviço</span>
                    </a>
                </li>'''

content = content.replace(target, repl)

with open('app/templates/base.html', 'w', encoding='utf-8') as f:
    f.write(content)
