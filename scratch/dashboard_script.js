
    const LEVELS = {
        REDE: 0,
        REGIONAL: 1,
        UNIT: 2,
        GRADE: 3,
        CLASS: 4,
        STUDENT: 5
    };

    const levelOrder = [LEVELS.REGIONAL, LEVELS.UNIT, LEVELS.GRADE, LEVELS.CLASS];

    let dashboardState = {
        exam_id: null,
        current_level: LEVELS.REDE,
        selections: {
            [LEVELS.REGIONAL]: [], // {id, name}
            [LEVELS.UNIT]: [],
            [LEVELS.GRADE]: [],
            [LEVELS.CLASS]: []
        }
    };

    let itemChart = null;
    let proficiencyChart = null;
    let skillsRadarChart = null;
    let absenceChart = null;

    document.getElementById('examSelect').addEventListener('change', function () {
        dashboardState.exam_id = this.value;
        resetToLevel(LEVELS.REDE, false);

        const processBtn = document.getElementById('processBtn');
        if (this.value) {
            processBtn.classList.remove('d-none');
            document.getElementById('dashboardContent').style.display = 'none';
            document.getElementById('drilldownControls').style.display = 'none';
            document.getElementById('emptyState').style.display = 'block';
        } else {
            processBtn.classList.add('d-none');
            document.getElementById('emptyState').style.display = 'block';
            document.getElementById('dashboardContent').style.display = 'none';
            document.getElementById('drilldownControls').style.display = 'none';
        }
    });

    // Trigger change event on page load if an exam is already pre-selected
    document.addEventListener('DOMContentLoaded', function () {
        // Inicializar tooltips e outros componentes se necessário
        
        // Listener para redimensionar os gráficos Chart.js quando as abas ficarem visíveis
        const tabElements = document.querySelectorAll('button[data-bs-toggle="tab"]');
        tabElements.forEach(function (tabEl) {
            tabEl.addEventListener('shown.bs.tab', function (event) {
                if (itemChart) itemChart.resize();
                if (proficiencyChart) proficiencyChart.resize();
                if (skillsRadarChart) skillsRadarChart.resize();
                if (absenceChart) absenceChart.resize();
            });
        });

        const examSelect = document.getElementById('examSelect');
        if (examSelect && examSelect.value) {
            examSelect.dispatchEvent(new Event('change'));
        }
    });

    function resetToLevel(level, reload = true) {
        dashboardState.current_level = level;
        // Clear all selections deeper than this level
        for (let key in dashboardState.selections) {
            if (parseInt(key) >= level) {
                dashboardState.selections[key] = [];
            }
        }
        if (reload) startProcessing();
    }

    // Mensagens dinâmicas da IA SUE por estágio de processamento
    const SUE_STAGES = [
        {
            range: [0, 20],
            step: 'Etapa 1 de 4',
            messages: [
                ['Coletando dados dos alunos...', 'A SUE está buscando os resultados de toda a rede.'],
                ['Mapeando matrículas e turmas...', 'Identificando os participantes da avaliação.'],
                ['Carregando registros da prova...', 'A SUE está reunindo as respostas registradas.']
            ]
        },
        {
            range: [20, 50],
            step: 'Etapa 2 de 4',
            messages: [
                ['Calculando desempenho por questão...', 'A SUE analisa acertos, erros e ausências em cada item.'],
                ['Cruzando respostas com os descritores...', 'Identificando habilidades e competências avaliadas.'],
                ['Processando dados de dificuldade...', 'A SUE classifica o desempenho por nível de complexidade.']
            ]
        },
        {
            range: [50, 80],
            step: 'Etapa 3 de 4',
            messages: [
                ['Gerando rankings e comparativos...', 'A SUE está ordenando escolas, turmas e alunos por desempenho.'],
                ['Calculando níveis de proficiência...', 'Distribuindo os alunos nos 4 níveis da escala de aprendizagem.'],
                ['Consolidando indicadores da rede...', 'A SUE agrega os dados de todas as unidades selecionadas.']
            ]
        },
        {
            range: [80, 100],
            step: 'Etapa 4 de 4',
            messages: [
                ['Finalizando a análise inteligente...', 'A SUE está preparando os gráficos e painéis interativos.'],
                ['Verificando consistência dos dados...', 'Garantindo a precisão dos resultados gerados.'],
                ['Quase lá! Renderizando o painel...', 'A SUE está montando sua visão completa do desempenho.']
            ]
        }
    ];

    function getSueMessage(progress) {
        for (const stage of SUE_STAGES) {
            if (progress >= stage.range[0] && progress < stage.range[1]) {
                const idx = Math.floor(Math.random() * stage.messages.length);
                return { main: stage.messages[idx][0], sub: stage.messages[idx][1], step: stage.step };
            }
        }
        return { main: 'Finalizando análise...', sub: 'A SUE está concluindo o processamento.', step: 'Etapa 4 de 4' };
    }

    function startProcessing() {
        if (!dashboardState.exam_id) return;

        const modalEl = document.getElementById('processingModal');
        const progressBar = document.getElementById('processingProgressBar');
        const statusText = document.getElementById('processingStatus');
        const stepText = document.getElementById('processingStep');
        const mainMsg = document.getElementById('sueMainMessage');
        const subMsg = document.getElementById('sueSubMessage');
        const examSelect = document.getElementById('examSelect');
        const processBtn = document.getElementById('processBtn');

        progressBar.style.width = '0%';
        statusText.innerText = '0% concluído';
        examSelect.disabled = true;
        processBtn.disabled = true;

        // Garantir que qualquer instância anterior seja destruída para evitar conflito de estado
        const existingModal = bootstrap.Modal.getInstance(modalEl);
        if (existingModal) {
            existingModal.dispose();
        }
        const modal = new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: false });

        let progressInterval = null;
        let messageInterval = null;
        let dataLoaded = false;
        let modalShown = false;
        let currentProgress = 0;

        function finishProcessing() {
            if (!dataLoaded || !modalShown) return;
            clearInterval(progressInterval);
            clearInterval(messageInterval);
            currentProgress = 100;
            progressBar.style.width = '100%';
            statusText.innerText = '100% concluído';
            stepText.innerText = 'Concluído ✓';
            mainMsg.innerText = 'Análise concluída com sucesso!';
            subMsg.innerText = 'A SUE finalizou o processamento. Seu painel está pronto.';

            setTimeout(() => {
                modal.hide();
                examSelect.disabled = false;
                processBtn.disabled = false;
                document.getElementById('emptyState').style.display = 'none';
                document.getElementById('dashboardContent').style.display = 'block';
                document.getElementById('drilldownControls').style.display = 'block';
            }, 700);
        }

        // Aguarda o modal estar completamente visível antes de iniciar o fetch
        modalEl.addEventListener('shown.bs.modal', function onShown() {
            modalEl.removeEventListener('shown.bs.modal', onShown);
            modalShown = true;

            // Progresso em fases: rápido no início, desacelera no meio, para antes de 90%
            // O fetch liberará o restante ao concluir
            const startTime = Date.now();
            let targetProgress = 0; // alvo suave

            progressInterval = setInterval(() => {
                const elapsed = Date.now() - startTime;

                // Curva de progressão em 3 fases:
                // 0-2s: sobe até ~30% (carregamento inicial)
                // 2-6s: sobe até ~60% (processamento pesado)
                // 6s+:  sobe lentamente até ~88% (aguarda resposta)
                if (elapsed < 2000) {
                    targetProgress = (elapsed / 2000) * 30;
                } else if (elapsed < 6000) {
                    targetProgress = 30 + ((elapsed - 2000) / 4000) * 30;
                } else {
                    // Desacelera muito: +0.3% por intervalo, teto em 88%
                    targetProgress = Math.min(88, targetProgress + 0.3);
                }

                // Suaviza a transição
                currentProgress += (targetProgress - currentProgress) * 0.2;
                const rounded = Math.round(currentProgress * 10) / 10;

                progressBar.style.width = rounded + '%';
                statusText.innerText = Math.round(rounded) + '% concluído';

                // Atualiza step label
                const stg = SUE_STAGES.find(s => rounded >= s.range[0] && rounded < s.range[1]);
                if (stg) stepText.innerText = stg.step;
            }, 150);

            // Rotaciona as mensagens da SUE a cada 2.5 segundos
            function updateMessage() {
                const msg = getSueMessage(currentProgress);
                mainMsg.innerText = msg.main;
                subMsg.innerText = msg.sub;
            }
            updateMessage();
            messageInterval = setInterval(updateMessage, 2500);

            loadDashboardData(() => {
                dataLoaded = true;
                finishProcessing();
            });
        });

        modal.show();
    }

    function loadDashboardData(callback) {
        if (!dashboardState.exam_id) return;

        let url = `/reports/data?exam_id=${dashboardState.exam_id}`;

        // Selection filters
        dashboardState.selections[LEVELS.REGIONAL].forEach(item => url += `&regional_id[]=${item.id}`);
        dashboardState.selections[LEVELS.UNIT].forEach(item => url += `&unit_id[]=${item.id}`);
        dashboardState.selections[LEVELS.GRADE].forEach(item => url += `&school_year_id[]=${item.id}`);
        dashboardState.selections[LEVELS.CLASS].forEach(item => url += `&class_id[]=${item.id}`);

        // Advanced Filters
        const races = Array.from(document.getElementById('filterRace').selectedOptions).map(o => o.value);
        const nationalities = Array.from(document.getElementById('filterNationality').selectedOptions).map(o => o.value);
        const incomes = Array.from(document.getElementById('filterIncome').selectedOptions).map(o => o.value);
        const zones = Array.from(document.getElementById('filterZone').selectedOptions).map(o => o.value);
        const locations = Array.from(document.getElementById('filterLocation').selectedOptions).map(o => o.value);
        const deficiency = Array.from(document.getElementById('filterDeficiency').selectedOptions).map(o => o.value);
        const bolsa = Array.from(document.getElementById('filterBolsa').selectedOptions).map(o => o.value);
        const dietary = Array.from(document.getElementById('filterDietary').selectedOptions).map(o => o.value);

        races.forEach(r => url += `&races[]=${encodeURIComponent(r)}`);
        nationalities.forEach(n => url += `&nationalities[]=${encodeURIComponent(n)}`);
        incomes.forEach(i => url += `&incomes[]=${encodeURIComponent(i)}`);
        zones.forEach(z => url += `&zones[]=${encodeURIComponent(z)}`);
        locations.forEach(l => url += `&locations[]=${encodeURIComponent(l)}`);
        deficiency.forEach(d => url += `&deficiency[]=${encodeURIComponent(d)}`);
        bolsa.forEach(b => url += `&bolsa[]=${encodeURIComponent(b)}`);
        dietary.forEach(dt => url += `&dietary[]=${encodeURIComponent(dt)}`);

        fetch(url)
            .then(res => res.json())
            .then(data => {
                updateKPIs(data.kpis);
                updateRanking(data.ranking);
                updateItemChart(data.items);
                updateProficiencyChart(data.proficiency);
                updateDifficultyPerformance(data.difficulty_performance);
                updateSkillsRadar(data.radar_labels, data.radar_data);
                updateGlobalRankings(data.rankings);
                renderBreadcrumbs();
                updateComponentsPerformance(data.components_performance);
                updateAbsenceReasonsChart(data.absence_reasons);

                if (callback && typeof callback === 'function') {
                    callback();
                }
            })
            .catch(err => {
                console.error("Error loading dashboard data:", err);
                if (callback && typeof callback === 'function') {
                    callback();
                }
            });
    }
    // Gráfico de Motivos de Ausência
    const ABSENCE_COLORS = [
        'rgba(245, 158, 11, 0.85)',   // âmbar — atestado médico (maior)
        'rgba(59, 130, 246, 0.85)',   // azul  — transporte (médio)
        'rgba(239, 68, 68, 0.85)',    // vermelho — viagem (menor)
        'rgba(16, 185, 129, 0.85)',   // verde
        'rgba(139, 92, 246, 0.85)',   // roxo
        'rgba(236, 72, 153, 0.85)',   // rosa
    ];

    function updateAbsenceReasonsChart(reasons) {
        const emptyState    = document.getElementById('absenceEmptyState');
        const chartContent  = document.getElementById('absenceChartContent');
        const totalBadge    = document.getElementById('absenceTotalBadge');
        const legendEl      = document.getElementById('absenceLegend');

        if (!reasons || reasons.length === 0) {
            emptyState.classList.remove('d-none');
            chartContent.classList.add('d-none');
            totalBadge.innerText = '0 ausências';
            if (absenceChart) { absenceChart.destroy(); absenceChart = null; }
            return;
        }

        emptyState.classList.add('d-none');
        chartContent.classList.remove('d-none');

        const totalAbsent = reasons.reduce((s, r) => s + r.count, 0);
        totalBadge.innerText = `${totalAbsent} ausência${totalAbsent !== 1 ? 's' : ''}`;

        const labels = reasons.map(r => r.name);
        const counts = reasons.map(r => r.count);
        const colors = reasons.map((_, i) => ABSENCE_COLORS[i % ABSENCE_COLORS.length]);

        // Legenda detalhada
        legendEl.innerHTML = '';
        reasons.forEach((r, i) => {
            const div = document.createElement('div');
            div.className = 'list-group-item d-flex justify-content-between align-items-center border-0 px-0 py-2';
            div.innerHTML = `
                <div class="d-flex align-items-center" style="min-width:0;">
                    <div class="rounded-circle flex-shrink-0 me-2"
                         style="width:13px;height:13px;background:${colors[i]};box-shadow:0 0 0 2px rgba(0,0,0,0.08);"></div>
                    <span class="small fw-semibold text-truncate" title="${r.name}">${r.name}</span>
                </div>
                <div class="d-flex align-items-center gap-2 flex-shrink-0 ms-3">
                    <span class="badge bg-light text-dark border">${r.count} aluno${r.count !== 1 ? 's' : ''}</span>
                    <span class="fw-bold fs-6" style="color:${colors[i]};">${r.perc}%</span>
                </div>
            `;
            legendEl.appendChild(div);
        });

        // Criar ou atualizar gráfico donut
        const ctx = document.getElementById('absenceChart').getContext('2d');
        if (absenceChart) {
            absenceChart.data.labels = labels;
            absenceChart.data.datasets[0].data = counts;
            absenceChart.data.datasets[0].backgroundColor = colors;
            absenceChart.update();
        } else {
            absenceChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: counts,
                        backgroundColor: colors,
                        borderWidth: 2,
                        borderColor: '#fff',
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const item = reasons[ctx.dataIndex];
                                    return ` ${item.name}: ${item.count} aluno${item.count !== 1 ? 's' : ''} (${item.perc}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    function updateGlobalRankings(rankings) {
        renderSubRanking('schools', rankings.schools);
        renderSubRanking('classes', rankings.classes);
        renderSubRanking('students', rankings.students);
        renderSubRanking('professors', rankings.professors);
    }

    function renderSubRanking(category, data) {
        const topContainer = document.getElementById(`${category}-top`);
        const bottomContainer = document.getElementById(`${category}-bottom`);

        if (!topContainer || !bottomContainer) return;

        topContainer.innerHTML = '';
        bottomContainer.innerHTML = '';

        if (!data || data.length === 0) {
            topContainer.innerHTML = '<div class="text-muted small p-4 text-center">Inexistente</div>';
            bottomContainer.innerHTML = '<div class="text-muted small p-4 text-center">Inexistente</div>';
            return;
        }

        const top = data.slice(0, 10);
        const bottom = data.length > 10 ? data.slice(-10).reverse() : []; // Reverse to show worst at top if displaying in Bottom list

        renderList(topContainer, top);
        renderList(bottomContainer, bottom);
    }

    function renderList(container, list) {
        list.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'mb-3';

            let dynamicColor = 'bg-danger';
            if (item.score >= 70) dynamicColor = 'bg-success';
            else if (item.score >= 50) dynamicColor = 'bg-warning text-dark';

            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <div class="d-flex flex-column text-truncate" style="max-width: 80%;">
                        <span class="small fw-bold" title="${item.name}">${item.name}</span>
                        ${item.sub ? `<span class="x-small text-muted">${item.sub}</span>` : ''}
                    </div>
                    <span class="small fw-bold">${Number(item.score).toFixed(2)}%</span>
                </div>
                <div class="progress" style="height: 4px;">
                    <div class="progress-bar ${dynamicColor}" style="width: ${item.score}%"></div>
                </div>
            `;
            container.appendChild(div);
        });

        if (list.length === 0) {
            container.innerHTML = '<div class="text-muted small py-2 text-center opacity-50">Sem dados suficientes</div>';
        }
    }

    function clearAdvancedFilters() {
        ['filterRace', 'filterNationality', 'filterIncome', 'filterZone', 'filterLocation', 'filterDeficiency', 'filterBolsa', 'filterDietary'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                for (let i = 0; i < el.options.length; i++) {
                    el.options[i].selected = false;
                }
            }
        });
        loadDashboardData();
    }

    function updateKPIs(kpis) {
        document.getElementById('kpi-avg').innerText = Number(kpis.avg_score).toFixed(2) + '%';
        document.getElementById('kpi-part').innerText = Number(kpis.participation).toFixed(2) + '%';
        document.getElementById('kpi-part-raw').innerText = `${kpis.total_participation} realizados`;
        document.getElementById('kpi-alerts').innerText = kpis.alerts;

        // Update Engagement Indicators
        const eng = kpis.engagement;
        document.getElementById('eng-realized').innerText = `${eng.realized} / ${eng.total}`;
        document.getElementById('eng-absent').innerText = eng.absent;
        document.getElementById('eng-fully').innerText = eng.fully_responded;
        document.getElementById('eng-missing').innerText = eng.missing + eng.not_responded_present;

        const status = document.getElementById('kpi-status');
        if (kpis.avg_score >= 70) {
            status.innerText = 'Excelente';
            status.className = 'mt-1 mb-1 text-white fw-bold';
        } else if (kpis.avg_score >= 50) {
            status.innerText = 'Em Evolução';
            status.className = 'mt-1 mb-1 text-white fw-bold';
        } else {
            status.innerText = 'Crítico';
            status.className = 'mt-1 mb-1 text-white fw-bold';
        }
    }

    function updateRanking(items) {
        const list = document.getElementById('rankingList');
        const title = document.getElementById('rankingTitle');
        const drillDownBtn = document.getElementById('drillDownBtn');
        list.innerHTML = '';

        const levelNames = {
            [LEVELS.REDE]: 'Regionais',
            [LEVELS.REGIONAL]: 'Escolas',
            [LEVELS.UNIT]: 'Anos Escolares',
            [LEVELS.GRADE]: 'Turmas',
            [LEVELS.CLASS]: 'Alunos'
        };

        title.innerText = `Comparativo de ${levelNames[dashboardState.current_level] || 'Dados'}`;

        // Show/Hide drill down button based on level
        if (dashboardState.current_level < LEVELS.STUDENT) {
            drillDownBtn.classList.remove('d-none');
        } else {
            drillDownBtn.classList.add('d-none');
        }

        items.forEach(item => {
            const btn = document.createElement('div');
            const isSelected = isItemSelected(item.id);
            btn.className = `list-group-item list-group-item-action d-flex align-items-center py-2 cursor-pointer ${isSelected ? 'active' : ''}`;

            let color = 'bg-danger';
            if (item.score >= 70) color = 'bg-success';
            else if (item.score >= 50) color = 'bg-warning';

            btn.innerHTML = `
                <div class="form-check me-3">
                    <input class="form-check-input" type="checkbox" ${isSelected ? 'checked' : ''} 
                        onclick="event.stopPropagation(); toggleSelection(${item.id}, '${item.name.replace(/'/g, "\\'")}');">
                </div>
                <div class="flex-grow-1" onclick="drillDownFromItem(${item.id}, '${item.name.replace(/'/g, "\\'")}');">
                    <div class="small fw-bold">${item.name}</div>
                    <div class="progress" style="height: 6px; width: 80%;">
                        <div class="progress-bar ${color}" style="width: ${item.score}%"></div>
                    </div>
                </div>
                <div class="fw-bold" onclick="drillDownFromItem(${item.id}, '${item.name.replace(/'/g, "\\'")}');">
                    ${Number(item.score).toFixed(2)}%
                </div>
            `;

            list.appendChild(btn);
        });
    }

    function drillDownFromItem(id, name) {
        const level = dashboardState.current_level + 1;
        if (!dashboardState.selections[level]) return;

        // Reset current level selections and add only this one for a clean drill-down
        dashboardState.selections[level] = [{ id, name }];

        // Advance level
        drillDownNextLevel();
    }

    function isItemSelected(id) {
        const level = dashboardState.current_level + 1;
        if (!dashboardState.selections[level]) return false;
        return dashboardState.selections[level].some(s => s.id == id);
    }

    function toggleSelection(id, name) {
        const level = dashboardState.current_level + 1;
        if (!dashboardState.selections[level]) return;

        const idx = dashboardState.selections[level].findIndex(s => s.id == id);
        if (idx > -1) {
            dashboardState.selections[level].splice(idx, 1);
        } else {
            dashboardState.selections[level].push({ id, name });
        }

        // Refresh UI only, don't reload data yet? 
        // User might want to accumulate then reload? 
        // User request: "possível acumular níveis de dados... clicando em duas regionais"
        // Let's reload to update KPIs/Charts immediately when selection changes
        startProcessing();
    }

    function drillDownNextLevel() {
        if (dashboardState.current_level < LEVELS.CLASS) {
            dashboardState.current_level++;
            startProcessing();
        } else if (dashboardState.current_level === LEVELS.CLASS) {
            dashboardState.current_level = LEVELS.STUDENT;
            startProcessing();
        }
    }

    function renderBreadcrumbs() {
        const container = document.getElementById('breadcrumbList');
        container.innerHTML = `<li class="breadcrumb-item"><a href="#" onclick="resetToLevel(LEVELS.REDE)" class="fw-bold">Rede</a></li>`;

        const plurals = {
            [LEVELS.REGIONAL]: 'Regionais',
            [LEVELS.UNIT]: 'Escolas',
            [LEVELS.GRADE]: 'Anos',
            [LEVELS.CLASS]: 'Turmas'
        };

        levelOrder.forEach(lvl => {
            const list = dashboardState.selections[lvl];
            if (list && list.length > 0) {
                const li = document.createElement('li');
                li.className = 'breadcrumb-item';

                const names = list.map(s => s.name).join(', ');
                const display = list.length > 1 ? `${plurals[lvl]} (${list.length})` : names;

                // Backtrack on click: reset to this level (which clears deeper filters)
                li.innerHTML = `<a href="#" onclick="resetToLevel(${lvl - 1})" title="${names}">${display}</a>`;
                container.appendChild(li);
            }
        });
    }

    function updateProficiencyChart(data) {
        const labels = ['Nível 1 (<25%)', 'Nível 2 (25%-49,9%)', 'Nível 3 (50%-74,9%)', 'Nível 4 (75%-100%)'];
        const counts = [data.level1.count, data.level2.count, data.level3.count, data.level4.count];
        const percentages = [data.level1.perc, data.level2.perc, data.level3.perc, data.level4.perc];
        const colors = [
            'rgba(220, 53, 69, 0.8)',  // Vermelho
            'rgba(255, 193, 7, 0.8)',  // Amarelo
            'rgba(13, 202, 240, 0.8)', // Ciano/Azul claro
            'rgba(25, 135, 84, 0.8)'   // Verde
        ];

        // Update list stats
        const container = document.getElementById('proficiencyStats');
        container.innerHTML = '';
        labels.forEach((label, i) => {
            const div = document.createElement('div');
            div.className = 'list-group-item d-flex justify-content-between align-items-center border-0 px-0 py-2';
            div.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="rounded-circle me-2" style="width: 12px; height: 12px; background-color: ${colors[i]}"></div>
                    <span class="small fw-bold">${label}</span>
                </div>
                <div class="text-end">
                    <span class="badge bg-light text-dark border me-2">${counts[i]} alunos</span>
                    <span class="fw-bold fs-5">${percentages[i]}%</span>
                </div>
            `;
            container.appendChild(div);
        });

        if (proficiencyChart) {
            proficiencyChart.data.datasets[0].data = counts;
            proficiencyChart.update();
        } else {
            const ctx = document.getElementById('proficiencyChart').getContext('2d');
            proficiencyChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: counts,
                        backgroundColor: colors,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    cutout: '75%'
                }
            });
        }
    }

    function updateDifficultyPerformance(data) {
        if (!data) return;
        
        // Fácil
        const easy = data.Facil || { correct_perc: 0, correct_answers: 0, total_answers: 0 };
        document.getElementById('diff-easy-perc').innerText = Number(easy.correct_perc).toFixed(1) + '%';
        document.getElementById('diff-easy-raw').innerText = `${easy.correct_answers} de ${easy.total_answers} respostas`;
        document.getElementById('diff-easy-progress').style.width = easy.correct_perc + '%';
        
        // Média
        const medium = data.Medio || { correct_perc: 0, correct_answers: 0, total_answers: 0 };
        document.getElementById('diff-medium-perc').innerText = Number(medium.correct_perc).toFixed(1) + '%';
        document.getElementById('diff-medium-raw').innerText = `${medium.correct_answers} de ${medium.total_answers} respostas`;
        document.getElementById('diff-medium-progress').style.width = medium.correct_perc + '%';
        
        // Difícil
        const hard = data.Dificil || { correct_perc: 0, correct_answers: 0, total_answers: 0 };
        document.getElementById('diff-hard-perc').innerText = Number(hard.correct_perc).toFixed(1) + '%';
        document.getElementById('diff-hard-raw').innerText = `${hard.correct_answers} de ${hard.total_answers} respostas`;
        document.getElementById('diff-hard-progress').style.width = hard.correct_perc + '%';
    }

    function updateSkillsRadar(labels, data) {
        if (!labels || !data) return;
        
        if (skillsRadarChart) {
            skillsRadarChart.data.labels = labels;
            skillsRadarChart.data.datasets[0].data = data;
            skillsRadarChart.update();
        } else {
            const ctx = document.getElementById('skillsRadarChart').getContext('2d');
            skillsRadarChart = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Domínio (%)',
                        data: data,
                        backgroundColor: 'rgba(99, 102, 241, 0.2)',
                        borderColor: 'rgba(99, 102, 241, 1)',
                        pointBackgroundColor: 'rgba(99, 102, 241, 1)',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: 'rgba(99, 102, 241, 1)',
                        borderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        r: {
                            angleLines: { color: 'rgba(0, 0, 0, 0.05)' },
                            grid: { color: 'rgba(0, 0, 0, 0.05)' },
                            pointLabels: {
                                font: { size: 11, family: "'Inter', sans-serif" },
                                color: '#4b5563'
                            },
                            ticks: {
                                beginAtZero: true,
                                max: 100,
                                stepSize: 25,
                                font: { size: 10 },
                                color: '#9ca3af',
                                backdropColor: 'transparent'
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.9)',
                            titleFont: { size: 13, family: "'Inter', sans-serif" },
                            bodyFont: { size: 12, family: "'Inter', sans-serif" },
                            padding: 10,
                            displayColors: false,
                            callbacks: {
                                label: function(context) {
                                    return context.raw + '% de acerto';
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    function updateComponentsPerformance(components) {
        const row = document.getElementById('componentsPerformanceRow');
        const container = document.getElementById('componentsPerformanceList');
        if (!row || !container) return;

        container.innerHTML = '';

        if (components && components.length > 0) {
            row.style.display = 'block';

            let gridClass = 'col-12';
            if (components.length === 2) {
                gridClass = 'col-md-6';
            } else if (components.length >= 3) {
                gridClass = 'col-md-4';
            }

            components.forEach(comp => {
                const div = document.createElement('div');
                div.className = `${gridClass} mb-2`;

                let colorClass = 'bg-danger';
                if (comp.correct_perc >= 70) {
                    colorClass = 'bg-success';
                } else if (comp.correct_perc >= 50) {
                    colorClass = 'bg-warning text-dark';
                }

                div.innerHTML = `
                    <div class="p-3 bg-light rounded border border-light shadow-sm h-100 d-flex flex-column justify-content-between">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="fw-bold small text-secondary text-truncate" style="max-width: 75%;" title="${comp.name}">
                                ${comp.name}
                            </span>
                            <span class="fw-bold fs-5 ${comp.correct_perc >= 70 ? 'text-success' : (comp.correct_perc >= 50 ? 'text-warning' : 'text-danger')}">
                                ${Number(comp.correct_perc).toFixed(2)}%
                            </span>
                        </div>
                        <div>
                            <div class="progress mb-2" style="height: 10px;">
                                <div class="progress-bar ${colorClass}" role="progressbar" style="width: ${comp.correct_perc}%" 
                                     aria-valuenow="${comp.correct_perc}" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                            <div class="d-flex justify-content-between align-items-center small text-muted">
                                <span>Acertos: <strong class="text-dark">${comp.correct_count}</strong></span>
                                <span>Total de respostas: <strong class="text-dark">${comp.total_count}</strong></span>
                            </div>
                        </div>
                    </div>
                `;
                container.appendChild(div);
            });
        } else {
            row.style.display = 'none';
        }
    }

    function updateQuestionsTable(items) {
        const tbody = document.getElementById('questionsTableBody');
        const countSpan = document.getElementById('questionsTableCount');
        if (!tbody) return;

        tbody.innerHTML = '';
        if (countSpan) countSpan.innerText = `${items.length} questões`;

        if (!items || items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted p-4">Sem dados para as questões da prova</td></tr>';
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            
            // Format descriptor display
            const descTooltip = item.desc_descriptions ? `title="${item.desc_descriptions}"` : '';
            
            tr.innerHTML = `
                <td class="ps-4 fw-bold text-primary">Q${item.num}</td>
                <td>
                    <span class="badge bg-light text-dark border px-2 py-1 fs-6" ${descTooltip} style="cursor: help;">
                        ${item.desc_codes}
                    </span>
                    ${item.desc_descriptions ? `<div class="x-small text-muted text-truncate mt-1" style="max-width: 350px;">${item.desc_descriptions}</div>` : ''}
                </td>
                <td>
                    <div class="d-flex align-items-center justify-content-between mb-1 px-1">
                        <span class="fw-bold text-success">${Number(item.correct_perc).toFixed(2)}%</span>
                        <span class="x-small text-muted">${item.correct_count} de ${item.total_count}</span>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-success" style="width: ${item.correct_perc}%"></div>
                    </div>
                </td>
                <td>
                    <div class="d-flex align-items-center justify-content-between mb-1 px-1">
                        <span class="fw-bold text-danger">${Number(item.incorrect_perc).toFixed(2)}%</span>
                        <span class="x-small text-muted">${item.incorrect_count} de ${item.total_count}</span>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-danger" style="width: ${item.incorrect_perc}%"></div>
                    </div>
                </td>
                <td>
                    <div class="d-flex align-items-center justify-content-between mb-1 px-1">
                        <span class="fw-bold text-secondary">${Number(item.blank_perc).toFixed(2)}%</span>
                        <span class="x-small text-muted">${item.blank_count} de ${item.total_count}</span>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-secondary" style="width: ${item.blank_perc}%"></div>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function updateItemChart(items) {
        try {
            const labels = items.map(i => 'Q' + i.num);
            const correctData = items.map(i => i.correct_perc);
            const incorrectData = items.map(i => i.incorrect_perc);
            const blankData = items.map(i => i.blank_perc);

            if (itemChart) {
                itemChart.destroy();
            }
            
            const ctx = document.getElementById('itemChart').getContext('2d');
            itemChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: '% de Acertos',
                            data: correctData,
                            backgroundColor: 'rgba(25, 135, 84, 0.7)',
                            borderColor: 'rgb(25, 135, 84)',
                            borderWidth: 1
                        },
                        {
                            label: '% de Erros',
                            data: incorrectData,
                            backgroundColor: 'rgba(220, 53, 69, 0.7)',
                            borderColor: 'rgb(220, 53, 69)',
                            borderWidth: 1
                        },
                        {
                            label: '% de Ausências',
                            data: blankData,
                            backgroundColor: 'rgba(108, 117, 125, 0.7)',
                            borderColor: 'rgb(108, 117, 125)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { 
                            stacked: true,
                            beginAtZero: true, 
                            max: 100,
                            ticks: {
                                callback: function(value) { return value + '%'; }
                            }
                        },
                        y: {
                            stacked: true
                        }
                    },
                    plugins: { 
                        legend: { display: true, position: 'bottom' },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const item = items[context.dataIndex];
                                    if (!item) return '';
                                    if (context.datasetIndex === 0) {
                                        return ` Acertos: ${Number(item.correct_perc).toFixed(2)}% (${item.correct_count}/${item.total_count})`;
                                    } else if (context.datasetIndex === 1) {
                                        return ` Erros: ${Number(item.incorrect_perc).toFixed(2)}% (${item.incorrect_count}/${item.total_count})`;
                                    } else {
                                        return ` Sem Resposta: ${Number(item.blank_perc).toFixed(2)}% (${item.blank_count}/${item.total_count})`;
                                    }
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error("Erro ao renderizar gráfico de itens:", error);
        }
        
        // Render detailed questions table
        if (typeof updateQuestionsTable === 'function') {
            updateQuestionsTable(items);
        }
    }
