document.addEventListener('DOMContentLoaded', () => {
    const searchTypeSelect = document.getElementById('search-type');
    const sourceItemsSelect = document.getElementById('source-items');
    const similaritySlider = document.getElementById('similarity-slider');
    const sliderValue = document.getElementById('slider-value');
    const analyzeButton = document.getElementById('analyze-button');
    const resultsArea = document.getElementById('results-area');
    const dashboardArea = document.getElementById('dashboard-area');

    let mappingData = {};

    // --- Inicialização do Dashboard ---
    const initDashboard = async () => {
        try {
            const response = await fetch('/api/dashboard-data');
            if (!response.ok) throw new Error('Falha ao carregar dados do dashboard');
            const data = await response.json();
            
            // KPIs
            const kpiContainer = document.getElementById('kpi-container');
            kpiContainer.innerHTML = `
                <div class="kpi-card"><h3>Pedidos em Carteira (Únicos)</h3><p>${data.kpis.pedidos_carteira.toLocaleString('pt-BR')}</p></div>
                <div class="kpi-card"><h3>Lotes Únicos em Estoque</h3><p>${data.kpis.lotes_estoque.toLocaleString('pt-BR')}</p></div>
                <div class="kpi-card"><h3>Peso Total do Estoque (t)</h3><p>${data.kpis.peso_total_estoque.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p></div>
            `;

            // Mapa
            const mapChart = echarts.init(document.getElementById('map-chart'));
            const mapOption = {
                backgroundColor: '#FFFFFF',
                geo: { map: 'world', roam: true, silent: true, center: [-70, 10], zoom: 2.5, itemStyle: { areaColor: '#E0E0E0', borderColor: '#BDBDBD' }, emphasis: { itemStyle: { areaColor: '#C1C1C1' } } },
                tooltip: { trigger: 'item', formatter: params => params.seriesType === 'scatter' ? `${params.name} : ${params.value[2]} pedidos` : params.name },
                series: [
                    { name: 'Rotas', type: 'lines', coordinateSystem: 'geo', zlevel: 2, effect: { show: true, period: 6, trailLength: 0, symbol: 'arrow', symbolSize: 6, color: '#2962FF' }, lineStyle: { color: '#2962FF', width: 1, opacity: 0.6, curveness: 0.2 }, data: data.mapData.routes },
                    { name: 'Pedidos', type: 'scatter', coordinateSystem: 'geo', zlevel: 2, label: { show: true, position: 'right', formatter: '{b}', color: '#333' }, symbolSize: val => 5 + Math.log(val[2] + 1) * 4, itemStyle: { color: '#D32F2F' }, data: data.mapData.cities }
                ]
            };
            mapChart.setOption(mapOption);

            // Radar
            const radarChart = echarts.init(document.getElementById('radar-chart'));
            const radarOption = {
                color: ['#5470C6', '#91CC75'],
                title: { text: 'Estoque vs Demanda', left: 'center' },
                legend: { bottom: 5, data: ['Estoque (Peso)', 'Carteira (Nº Pedidos)'], itemGap: 20 },
                radar: { indicator: data.radarData.labels.map(name => ({ name })), shape: 'circle', splitNumber: 5, axisName: { color: '#666' }, splitLine: { lineStyle: { color: '#ddd' } }, splitArea: { show: false }, axisLine: { lineStyle: { color: '#ccc' } } },
                series: [{ name: 'Comparativo', type: 'radar', emphasis: { lineStyle: { width: 4 } },
                    data: [
                        { value: data.radarData.estoque, name: 'Estoque (Peso)', areaStyle: { color: 'rgba(84, 112, 198, 0.4)' } },
                        { value: data.radarData.carteira, name: 'Carteira (Nº Pedidos)', areaStyle: { color: 'rgba(145, 204, 117, 0.4)' } }
                    ]
                }]
            };
            radarChart.setOption(radarOption);
            
            window.addEventListener('resize', () => {
                mapChart.resize();
                radarChart.resize();
            });

        } catch (error) {
            console.error(error);
            dashboardArea.innerHTML = `<div class="error">Não foi possível carregar o dashboard. Verifique o console para mais detalhes.</div>`;
        }
    };

    // --- Carregamento dos Itens de Origem ---
    const loadSourceItems = async () => {
        const searchType = searchTypeSelect.value;
        sourceItemsSelect.innerHTML = '<option>Carregando...</option>';
        sourceItemsSelect.disabled = true;
        try {
            const response = await fetch(`/api/source-items/${searchType}`);
            if (!response.ok) throw new Error('Falha ao buscar itens de origem');
            const items = await response.json();
            
            sourceItemsSelect.innerHTML = '<option value="">Selecione um item</option>';
            items.forEach(item => {
                const option = document.createElement('option');
                option.value = item;
                option.textContent = item;
                sourceItemsSelect.appendChild(option);
            });
            sourceItemsSelect.disabled = false;
        } catch (error) {
            console.error(error);
            sourceItemsSelect.innerHTML = '<option>Erro ao carregar</option>';
        }
    };

    // --- Renderização dos Resultados ---
    const renderResults = (data) => {
        resultsArea.innerHTML = '';
        if (!data.results || data.results.length === 0) {
            resultsArea.innerHTML = `<div class="no-results">Nenhum item compatível encontrado com os filtros atuais.</div>`;
            return;
        }

        const { results, sourceItem, mapping } = data;
        const targetIdCol = searchTypeSelect.value === 'pedido' ? 'Lote Gsd' : 'OV Item';
        const sourceIdCol = searchTypeSelect.value === 'pedido' ? 'OV Item' : 'Lote Gsd';
        
        const resultItem = document.createElement('div');
        resultItem.className = 'result-item';
        resultItem.innerHTML = `<h3>Análise para o Item de Origem: <code>${sourceItem[sourceIdCol]}</code></h3>`;
        
        // Tabela de resultados
        let tableHTML = `
            <p>${results.length} itens compatíveis encontrados.</p>
            <table><thead><tr>
                <th>${targetIdCol}</th>
                <th>Índice de Similaridade</th>
                ${Object.values(mapping).flat().filter((v, i, a) => a.indexOf(v) === i).map(col => `<th>${col}</th>`).join('')}
            </tr></thead><tbody>`;

        const filteredResults = results.filter(r => r['Índice de Similaridade'] >= similaritySlider.value / 100);
        
        filteredResults.forEach(row => {
            tableHTML += `<tr><td>${row[targetIdCol]}</td><td>${(row['Índice de Similaridade'] * 100).toFixed(0)}%</td>`;
            Object.values(mapping).flat().filter((v, i, a) => a.indexOf(v) === i).forEach(col => {
                 const isMatch = row.match_details[Object.keys(mapping).find(k => (Array.isArray(mapping[k]) ? mapping[k].includes(col) : mapping[k] === col))] ?? true;
                 tableHTML += `<td class="${isMatch ? '' : 'non-match'}">${row[col] ?? '-'}</td>`;
            });
            tableHTML += `</tr>`;
        });
        tableHTML += `</tbody></table>`;
        resultItem.innerHTML += tableHTML;

        // Comparativo Detalhado
        let comparisonHTML = `<div class="form-group" style="margin-top: 1.5rem;">
            <label for="comparison-select">Selecione um '${targetIdCol}' para comparar em detalhe:</label>
            <select id="comparison-select">
                ${filteredResults.map(r => `<option value="${r[targetIdCol]}">${r[targetIdCol]}</option>`).join('')}
            </select>
        </div><div id="comparison-details"></div>`;
        resultItem.innerHTML += comparisonHTML;
        
        resultsArea.appendChild(resultItem);
        
        // Lógica do comparativo
        const comparisonSelect = document.getElementById('comparison-select');
        const comparisonDetailsDiv = document.getElementById('comparison-details');

        const updateComparison = () => {
            const selectedId = comparisonSelect.value;
            const targetRow = filteredResults.find(r => String(r[targetIdCol]) === selectedId);
            if (!targetRow) {
                comparisonDetailsDiv.innerHTML = '';
                return;
            }

            let detailsTable = '<h4>Comparativo Detalhado</h4><table><thead><tr><th>Parâmetro</th><th>Valor Origem</th><th>Valor Encontrado</th><th>Compatível</th></tr></thead><tbody>';
            for (const [s_col, t_cols] of Object.entries(mapping)) {
                if(sourceItem[s_col] !== null && sourceItem[s_col] !== undefined) {
                    const t_cols_list = Array.isArray(t_cols) ? t_cols : [t_cols];
                    const t_vals = t_cols_list.map(tc => targetRow[tc] ?? '-').join(' | ');
                    const isMatch = targetRow.match_details[s_col];
                    detailsTable += `<tr><td>${s_col}</td><td>${sourceItem[s_col]}</td><td>${t_vals}</td><td class="${isMatch ? 'match' : 'non-match'}">${isMatch ? '✅' : '❌'}</td></tr>`;
                }
            }
            detailsTable += '</tbody></table>';
            comparisonDetailsDiv.innerHTML = detailsTable;
        };

        comparisonSelect.addEventListener('change', updateComparison);
        if (filteredResults.length > 0) updateComparison(); // Inicializa
    };
    
    // --- Event Listeners ---
    searchTypeSelect.addEventListener('change', loadSourceItems);
    similaritySlider.addEventListener('input', () => {
        sliderValue.textContent = `${similaritySlider.value}%`;
    });

    analyzeButton.addEventListener('click', async () => {
        const selectedItem = sourceItemsSelect.value;
        if (!selectedItem) {
            alert('Por favor, selecione um item de origem.');
            return;
        }
        
        resultsArea.innerHTML = '<div class="loader">Analisando... Por favor, aguarde.</div>';
        dashboardArea.style.display = 'none';

        try {
            const response = await fetch(`/api/analyze/${searchTypeSelect.value}/${selectedItem}`);
            if (!response.ok) throw new Error(`Erro na análise: ${response.statusText}`);
            const data = await response.json();
            renderResults(data);
        } catch (error) {
            console.error(error);
            resultsArea.innerHTML = `<div class="error">Ocorreu um erro durante a análise. Verifique o console.</div>`;
        }
    });

    // --- Inicialização ---
    initDashboard();
    loadSourceItems();
});
