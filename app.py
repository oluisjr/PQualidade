import streamlit as st
import pandas as pd
import numpy as np
import os
import streamlit.components.v1 as components
from pyecharts import options as opts
from pyecharts.charts import Geo, Liquid, Radar
from pyecharts.globals import ChartType, SymbolType
from pyecharts.commons.utils import JsCode
from collections import Counter

logo_path=r"C:\Users\csp4992\OneDrive - Companhia Siderurgica Nacional\Área de Trabalho\PROJECTS\PQUALIDADE\assets\logoA.png"

# --- Configurações da Aplicação ---
st.set_page_config(layout="wide", page_title="Otimização de Estoque", page_icon=logo_path, initial_sidebar_state="expanded")

# --- Funções de Apoio ---
def to_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '.'), errors='coerce')

@st.cache_data
def load_and_cache_data(path_carteira, path_estoque, numeric_cols_carteira, numeric_cols_estoque):
    if not os.path.exists(path_carteira):
        return None, None, f"Arquivo da Carteira não encontrado: `{path_carteira}`."
    if not os.path.exists(path_estoque):
        return None, None, f"Arquivo de Estoque não encontrado: `{path_estoque}`."
    try:
        df_carteira = pd.read_excel(path_carteira)
        df_estoque = pd.read_excel(path_estoque)
        
        df_carteira = df_carteira.rename(columns={c: c.strip() for c in df_carteira.columns})
        df_estoque = df_estoque.rename(columns={c: c.strip() for c in df_estoque.columns})
        
        if 'Estoque' in df_estoque.columns:
            df_estoque = df_estoque[df_estoque['Estoque'] != 'PROD ACAB'].copy()

        for col in numeric_cols_carteira:
            if col in df_carteira.columns: df_carteira[col] = to_numeric(df_carteira[col])
        for col in numeric_cols_estoque:
            if col in df_estoque.columns: df_estoque[col] = to_numeric(df_estoque[col])

        df_carteira.dropna(subset=['OV Item'], inplace=True)
        df_estoque.dropna(subset=['Lote Gsd'], inplace=True)
        return df_carteira, df_estoque, None
    except Exception as e:
        return None, None, f"Ocorreu um erro ao ler os arquivos Excel: {e}"


@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

# --- Funções de Geração de Gráficos (PYECHARTS) ---

@st.cache_data
def create_pyecharts_map_geo(lines_data, points_data, city_coords):
    """Gera o HTML para o mapa Geo com rotas e pontos animados."""
    c = (
        Geo(init_opts=opts.InitOpts(bg_color="#ffffff", js_host="https://assets.pyecharts.org/assets/v5/"))
        .add_schema(
            maptype="world",
            itemstyle_opts=opts.ItemStyleOpts(color="#374151", border_color="#111827"),
        )
    )
    for city, coord in city_coords.items():
        c.add_coordinate(city, coord[1], coord[0])

    # Adiciona os pontos de destino com animação
    c.add(
        "Destinos",
        points_data,
        type_=ChartType.EFFECT_SCATTER,
        color="#47e2a1",
    )
    # Adiciona as linhas de rota com animação
    c.add(
        "Rotas",
        lines_data,
        type_=ChartType.LINES,
        effect_opts=opts.EffectOpts(
            symbol=SymbolType.ARROW, symbol_size=6, color="#67a0fc"
        ),
        linestyle_opts=opts.LineStyleOpts(curve=0.2),
    )
    c.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
    c.set_global_opts(
        title_opts=opts.TitleOpts(
            pos_left="center",
            title_textstyle_opts=opts.TextStyleOpts(color="#e5e7eb")
        ),
        tooltip_opts=opts.TooltipOpts(
            trigger="item",
            formatter=JsCode("""
                function(params) {
                    if (params.seriesName === 'Destinos') {
                        return params.name + ': ' + params.value[2] + ' menções';
                    }
                    if(params.data.fromName && params.data.toName) {
                        return params.data.fromName + ' -> ' + params.data.toName;
                    }
                    return params.name;
                }
            """)
        )
    )
    return c.render_embed()

@st.cache_data
def create_pyecharts_radar(indicator_data, data1, data2, name1, name2):
    """Gera o HTML para o gráfico de radar usando Pyecharts com eixos dinâmicos e tooltips claros."""
    data1_safe = [float(d) for d in data1]
    data2_safe = [float(d) for d in data2]
    
    max_values = [max(v1, v2) * 1.15 if max(v1, v2) > 0 else 1 for v1, v2 in zip(data1_safe, data2_safe)]

    c = (
        Radar()
        .add_schema(
            schema=[
                opts.RadarIndicatorItem(name=item["name"], max_=max_val) 
                for item, max_val in zip(indicator_data, max_values)
            ],
            shape="circle",
            splitarea_opt=opts.SplitAreaOpts(
                is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=0.1)
            ),
            textstyle_opts=opts.TextStyleOpts(color="#6b7280"),
        )
        .add(
            series_name=name1,
            data=[data1_safe],
            linestyle_opts=opts.LineStyleOpts(color="#3b82f6"),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.4, color="#3b82f6")
        )
        .add(
            series_name=name2,
            data=[data2_safe],
            linestyle_opts=opts.LineStyleOpts(color="#22c55e"),
            areastyle_opts=opts.AreaStyleOpts(opacity=0.4, color="#22c55e")
        )
        .set_series_opts(label_opts=opts.LabelOpts(is_show=False))
        .set_global_opts(
            title_opts=opts.TitleOpts(title="Estoque vs Demanda", pos_left="center"),
            legend_opts=opts.LegendOpts(pos_bottom="5"),
            tooltip_opts=opts.TooltipOpts(trigger="item") # Habilita tooltip detalhado
        )
    )
    return c.render_embed()

# --- ALTERAÇÃO: O liquid exibe a contagem e a porcentagem no tooltip ---
@st.cache_data
def create_pyecharts_liquid_gauge(matches, total):
    """Gera o HTML para o medidor líquido com contagem e tooltip de porcentagem."""
    value = matches / total if total > 0 else 0
    c = (
        Liquid()
        .add(
            "similaridade",
            [value],
            label_opts=opts.LabelOpts(
                font_size=28,
                formatter=f"{matches}/{total}", # Exibe a contagem no centro
                position="inside",
            ),
            is_outline_show=False
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="Itens Compatíveis",
                pos_left="center",
                pos_top="bottom",
                title_textstyle_opts=opts.TextStyleOpts(font_size=16),
            ),
            # Adiciona o tooltip para exibir a porcentagem ao passar o mouse
            tooltip_opts=opts.TooltipOpts(
                formatter=JsCode(
                    """function(param) {
                        return 'Similaridade: ' + (Math.floor(param.value * 10000) / 100) + '%';
                    }"""
                )
            )
        )
    )
    return c.render_embed()


# --- Funções de Análise e Estilização (OTIMIZADAS) ---
@st.cache_data
def calculate_compatibility_vectorized(source_row, target_df, mapping, reverse=False):
    match_matrix = pd.DataFrame(index=target_df.index)
    total_criteria = 0
    checked_criteria = {} # Usado para o liquid de contagem

    for source_col, target_cols in mapping.items():
        target_cols_list = target_cols if isinstance(target_cols, list) else [target_cols]
        if source_row.get(source_col) is None or pd.isna(source_row[source_col]):
            continue
        
        total_criteria += 1
        source_val = source_row[source_col]
        combined_mask = pd.Series(False, index=target_df.index)
        is_range_check = False
        
        if source_col in ['Esp', 'Larg.'] and not reverse:
            tol_inf_col = 'Tol. Inf. Esp.' if source_col == 'Esp' else 'Tol. Inf. Larg'
            tol_sup_col = 'Tol. Sup. Esp.' if source_col == 'Esp' else 'Tol. Sup. Larg'
            min_val, max_val = source_row.get(tol_inf_col), source_row.get(tol_sup_col)
            if pd.notna(min_val) and pd.notna(max_val):
                is_range_check = True
                for tc in target_cols_list:
                    if tc in target_df.columns:
                        combined_mask |= (target_df[tc] >= (source_val - min_val)) & (target_df[tc] <= (source_val + max_val))
        
        if not is_range_check:
            for tc in target_cols_list:
                if tc in target_df.columns:
                    combined_mask |= (target_df[tc].astype(str).str.strip().str.lower() == str(source_val).strip().lower())

        match_matrix[source_col] = combined_mask
        checked_criteria[source_col] = True

    similarity_scores = match_matrix.sum(axis=1) / total_criteria if total_criteria > 0 else 0
    
    results_df = target_df.copy()
    results_df['Índice de Similaridade'] = similarity_scores
    
    def get_match_details(row):
        details = {}
        for col in checked_criteria:
            details[col] = row[col]
        return details

    results_df['match_details'] = match_matrix.apply(get_match_details, axis=1)

    return results_df.sort_values(by='Índice de Similaridade', ascending=False)

# --- Interface Gráfica ---
img, title, nada  = st.columns([1, 3, 1])
with img:
    st.image(logo_path, width=80)
with title:
    st.markdown("""
    <style>
        h1, h2, h3, .stMarkdown h1 {
            font-family: 'Montserrat', sans-serif !important;
            font-size: 2.2rem;
            font-weight: 500;
        }
    </style>
""", unsafe_allow_html=True)
    st.markdown("<h1 class='montserrat-title'>Painel de Otimização de Estoque</h1>", unsafe_allow_html=True)
with nada:
    st.write("")

# --- Mapeamentos e Colunas ---
mapping_carteira_to_estoque = { 'Grp Merc': 'Grp Mercadoria', 'Prd': 'Produto Basico Ov', 'Material GSD': 'Material Antigo Gsd', 'Material': 'Material', 'Especificacão': 'Especificaçao LZ', 'Norma Revest.': 'Revestimento Lote 1', 'Esp': ['Esp R', 'Esp C', 'Esp BFF'], 'Larg.': ['Larg R', 'Larg BFF', 'Larg C'], 'Sup': 'Superficie Ov', 'Apara': 'Apara Ov', 'Trat. Quim.': ['Trat Quimico Inf Real', 'Trat Qumico Sup Real'], 'Peso Peça': 'Peso Peca', 'Peso Min': 'Peso Minimo', 'Peso Max': 'Peso Maximo', 'Rota GSD': 'Rota', 'Quant. Óleo': 'Quantidade de Oleo', 'Lam. Encruam.': 'Laminacao Encruamento Real', 'Uso final': 'Uso Final' }
numeric_cols_c = ['Esp', 'Tol. Inf. Esp.', 'Tol. Sup. Esp.', 'Larg.', 'Tol. Inf. Larg', 'Tol. Sup. Larg', 'Peso Peça', 'Peso Min', 'Peso Max', 'Quant. Óleo']
numeric_cols_e = ['Esp R', 'Esp C', 'Esp BFF', 'Larg R', 'Larg BFF', 'Larg C', 'Peso Peca', 'Peso Minimo', 'Peso Maximo', 'Quantidade de Oleo', 'Peso Estoque']

# --- Caminhos e Carregamento ---
PATH_CARTEIRA = r"C:\Users\csp4992\OneDrive - Companhia Siderurgica Nacional\Área de Trabalho\PROJECTS\PROJETO QUALIDADE\Carteira_Geral NOVA_GERAL-pt-br.xlsx"
PATH_ESTOQUE = r"C:\Users\csp4992\OneDrive - Companhia Siderurgica Nacional\Área de Trabalho\PROJECTS\PROJETO QUALIDADE\Estoque CSN Porto Real-pt-br.xlsx"
df_carteira, df_estoque, error_msg = load_and_cache_data(PATH_CARTEIRA, PATH_ESTOQUE, numeric_cols_c, numeric_cols_e)


if error_msg:
    st.error(error_msg)
    st.stop()

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'analysis_triggered' not in st.session_state: st.session_state.analysis_triggered = False
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = None
if 'source_row' not in st.session_state: st.session_state.source_row = None
if 'selected_item' not in st.session_state: st.session_state.selected_item = None
if 'min_similarity_pct' not in st.session_state: st.session_state.min_similarity_pct = 75
if 'selected_comparison' not in st.session_state: st.session_state.selected_comparison = None
if 'results_search_type' not in st.session_state: st.session_state.results_search_type = None
if 'current_search_type' not in st.session_state: st.session_state.current_search_type = "Por Pedido (OV)"


# --- APLICAÇÃO PRINCIPAL ---
if df_carteira is not None and df_estoque is not None:
    tab1, tab2 = st.tabs(["Dashboard Geral", "Análise de Compatibilidade"])

    with tab1:
        st.header("Dashboard Geral da Operação")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            with st.container(border=True): st.metric("Pedidos em Carteira (Únicos)", f"{df_carteira['OV Item'].nunique():,}".replace(",", "."))
        
        tipo_counts = df_estoque['Tipo'].value_counts()
        bobinas_count = tipo_counts.get('BOBINA', 0)
        blanks_count = tipo_counts.get('BLANK', 0)

        with col2:
            with st.container(border=True): st.metric("Quantidade de Bobinas", f"{bobinas_count:,}".replace(",", "."))
        with col3:
            with st.container(border=True): st.metric("Quantidade de Blanks", f"{blanks_count:,}".replace(",", "."))
        with col4:
            peso_total_ton = df_estoque['Peso Estoque'].sum() / 1000
            with st.container(border=True): st.metric("Peso Total em Estoque (ton)", f"{peso_total_ton:,.2f}".replace(",", "#").replace(".", ",").replace("#", "."))

        st.markdown("<br>", unsafe_allow_html=True)
        
        col_graf1, col_graf2 = st.columns(2) 

        with col_graf1:
            with st.container():
                st.markdown("#### Mapa de Distribuição de Cidades")
                city_coords = {
                    'AGUA DOCE': [-26.9972, -51.5544], 'ALDEIA DE PAIO PIRES': [38.6035, -9.0939], 'ALMIRANTE TAMANDARE': [-25.325, -49.3094], 
                    'ARACATUBA': [-21.2086, -50.4328], 'ARAUCARIA': [-25.5931, -49.4125], 'ARUJA': [-23.3961, -46.5219], 'BARRA DO PIRAI': [-22.4703, -43.8258], 
                    'BARRA MANSA': [-22.5444, -44.1714], 'BELFORD ROXO': [-22.7642, -43.3989], 'BETIM': [-19.9678, -44.1983], 'BOTUCATU': [-22.8864, -48.445], 
                    'BRASILIA': [-15.7942, -47.8825], 'CABREUVA': [-23.3072, -47.1333], 'CACAPAVA': [-23.1022, -45.7061], 'CAMACARI': [-12.6978, -38.3242], 
                    'CAMANDUCAIA': [-22.7533, -46.1425], 'CAMPINA GRANDE DO SUL': [-25.305, -49.055], 'CANOAS': [-29.9178, -51.1831], 
                    'CATANDUVA': [-21.1375, -48.9714], 'CAXIAS DO SUL': [-29.1678, -51.1789], 'CERES': [-15.3086, -49.5978], 'CHICAGO': [41.8781, -87.6298], 
                    'CONDOR': [-28.2081, -53.4864], 'CONTAGEM': [-19.9322, -44.0531], 'CORUPA': [-26.4264, -49.245], 'COSMORAMA': [-20.4789, -50.1133], 
                    'CRICIUMA': [-28.6775, -49.3697], 'CRUZEIRO': [-22.5761, -44.9686], 'CURITIBA': [-25.4284, -49.2733], 'DIADEMA': [-23.686, -46.623], 
                    'DIAS D\'AVILA': [-12.6103, -38.1583], 'DUQUE DE CAXIAS': [-22.7858, -43.3117], 'ERECHIM': [-27.6344, -52.2739], 'EXTREMA': [-22.8556, -46.3189], 
                    'FARROUPILHA': [-29.2256, -51.3486], 'FAZENDA RIO GRANDE': [-25.6611, -49.3094], 'FERRAZ DE VASCONCELOS': [-23.5422, -46.3664], 
                    'GARUVA': [-26.0267, -48.8544], 'GOIANA': [-7.5583, -35.0022], 'GRAVATAI': [-29.9419, -50.9936], 'GUARATINGUETA': [-22.8167, -45.1911], 
                    'GUARULHOS': [-23.4536, -46.5331], 'IGARASSU': [-7.8347, -34.9064], 'ITAQUAQUECETUBA': [-23.4864, -46.3483], 'ITUMBIARA': [-18.4183, -49.215], 
                    'JACAREI': [-23.3053, -45.9658], 'JARINU': [-23.0994, -46.7303], 'JOINVILLE': [-26.3031, -48.8456], 'JUATUBA': [-19.9519, -44.3486], 
                    'JUNDIAI': [-23.1867, -46.8842], 'LIMEIRA': [-22.565, -47.4072], 'LONDRINA': [-23.3103, -51.1628], 'MANDAGUARI': [-23.5461, -51.6703], 
                    'MANAUS': [-3.119, -60.0217], 'MARACANAU': [-3.8647, -38.6258], 'MAUA': [-23.6678, -46.4614], 'MOGI DAS CRUZES': [-23.5236, -46.1889], 
                    'MOGI MIRIM': [-22.4311, -46.9561], 'NAVEGANTES': [-26.8986, -48.6531], 'NOSSA SENHORA DO SOCORRO': [-10.8506, -37.1264], 
                    'PANAMBI': [-28.2917, -53.5011], 'PARACAMBI': [-22.6083, -43.7125], 'PINHAIS': [-25.445, -49.1931], 'PINHEIRAL': [-22.5133, -44.0044], 
                    'PIRACICABA': [-22.7253, -47.6492], 'PONTA GROSSA': [-25.0945, -50.1633], 'PORTO REAL': [-22.4208, -44.2928], 'POUSO ALEGRE': [-22.23, -45.9342], 
                    'PROVÍNCIA DE BUENOS AIRES': [-36.676, -60.556], 'QUEIMADOS': [-22.7158, -43.5558], 'RESENDE': [-22.4686, -44.4469], 
                    'RIBEIRAO PIRES': [-23.7125, -46.4131], 'SALVADOR': [-12.9777, -38.5016], 'SANTA ISABEL': [-23.3183, -46.2239], 
                    'SANTANA DE PARNAIBA': [-23.4439, -46.9172], 'SANTO ANDRE': [-23.6644, -46.5381], 'SAO BERNARDO DO CAMPO': [-23.6939, -46.5542], 
                    'SAO CAETANO DO SUL': [-23.6228, -46.5736], 'SAO CARLOS': [-22.0178, -47.8919], 'SAO JOSE DO RIO PRETO': [-20.8203, -49.3792], 
                    'SAO JOSE DOS CAMPOS': [-23.1791, -45.8869], 'SAO JOSE DOS PINHAIS': [-25.5342, -49.2069], 'SAO LEOPOLDO': [-29.7594, -51.1469], 
                    'SAO MATEUS': [-18.7161, -39.8583], 'SAO PAULO': [-23.5505, -46.6333], 'SAQUAREMA': [-22.9208, -42.5103], 'SENADOR CANEDO': [-16.7083, -49.0919], 
                    'SERRA': [-20.1286, -40.3078], 'SETE LAGOAS': [-19.4661, -44.2475], 'SUMARE': [-22.8219, -47.2669], 'SUZANO': [-23.5431, -46.3106], 
                    'TAUBATE': [-23.0261, -45.5553], 'TRES CORACOES': [-21.6917, -45.2536], 'TRES LAGOAS': [-20.785, -51.7075], 'TRES RIOS': [-22.1169, -43.2089], 
                    'UBA': [-21.1206, -42.9425], 'VALENCA': [-22.2464, -43.7008], 'VARGEM GRANDE PAULISTA': [-23.6033, -47.0278], 'VASSOURAS': [-22.4044, -43.6625], 
                    'VOLTA REDONDA': [-22.5231, -44.1044], 'C1001AAF-BUENOS AIRES': [-34.6037, -58.3816]
                }
                
                # Lista completa de cidades do arquivo
                static_cities_from_file = [
                    'PORTO REAL', 'SAO JOSE DOS PINHAIS', 'GRAVATAI', 'SAO CAETANO DO SUL', 'SAO JOSE DOS CAMPOS', 'MOGI DAS CRUZES', 'SAO PAULO', 'SAO LEOPOLDO',
                    'JUATUBA', 'SUZANO', 'ARAUCARIA', 'CHICAGO', 'BETIM', 'CONTAGEM', 'PINHEIRAL', 'MANAUS', 'DIADEMA', 'LIMEIRA', 'CANOAS', 'CORUPA',
                    'PROVÍNCIA DE BUENOS AIRES', 'SETE LAGOAS', 'QUEIMADOS', 'VALENCA', 'CAMACARI', 'DIAS D\'AVILA', 'SAO BERNARDO DO CAMPO',
                    'JOINVILLE', 'PIRACICABA', 'ERECHIM', 'MAUA', 'TRES RIOS', 'CRUZEIRO', 'PANAMBI', 'CURITIBA', 'ALDEIA DE PAIO PIRES', 'GOIANA',
                    'PONTA GROSSA', 'GARUVA', 'ALMIRANTE TAMANDARE', 'FARROUPILHA', 'DUQUE DE CAXIAS', 'JACAREI', 'BARRA DO PIRAI', 'VASSOURAS', 'ITUMBIARA',
                    'CACAPAVA', 'BOTUCATU', 'SUMARE', 'JUNDIAI', 'MOGI MIRIM', 'CATANDUVA', 'ARACATUBA', 'SAO CARLOS', 'SAO JOSE DO RIO PRETO',
                    'VOLTA REDONDA', 'BARRA MANSA', 'RESENDE', 'GUARULHOS', 'ITAQUAQUECETUBA', 'SANTA ISABEL', 'ARUJA', 'JARINU', 'SANTANA DE PARNAIBA',
                    'FERRAZ DE VASCONCELOS', 'CABREUVA', 'VARGEM GRANDE PAULISTA', 'BELFORD ROXO', 'PARACAMBI', 'SAQUAREMA', 'AGUA DOCE', 'NAVEGANTES',
                    'CRICIUMA', 'SAO MATEUS', 'SERRA', 'MARACANAU', 'IGARASSU', 'SALVADOR', 'NOSSA SENHORA DO SOCORRO', 'BRASILIA', 'SENADOR CANEDO',
                    'TRES LAGOAS', 'LONDRINA', 'PINHAIS', 'FAZENDA RIO GRANDE', 'CAMPINA GRANDE DO SUL', 'MANDAGUARI', 'UBA', 'TRES CORACOES', 'EXTREMA',
                    'CAMANDUCAIA', 'C1001AAF-BUENOS AIRES'
                ] * 50 

                city_counts = Counter(static_cities_from_file)
                
                points_data = []
                lines_data = []
                for city, value in city_counts.items():
                    if city in city_coords:
                        points_data.append((city, value))
                        if city != 'PORTO REAL':
                            lines_data.append(("PORTO REAL", city))

                map_html = create_pyecharts_map_geo(lines_data, points_data, city_coords)
                centered_map_html = f"""
                <div style="display: flex; justify-content: center; align-items: center; height: 100%; width: 100%;">
                    {map_html}
                </div>
                """
                components.html(centered_map_html, height=520)

        with col_graf2:
            with st.container():
                grp_merc_estoque_col = 'Grp Mercadoria'
                grp_merc_carteira_col = 'Grp Merc'

                if (grp_merc_estoque_col in df_estoque.columns and
                    grp_merc_carteira_col in df_carteira.columns):

                    top_grp_estoque = df_estoque[grp_merc_estoque_col].value_counts().nlargest(5)
                    top_grp_carteira = df_carteira[grp_merc_carteira_col].value_counts().nlargest(5)
                    combined_labels = sorted(list(set(top_grp_estoque.index) | set(top_grp_carteira.index)))
                    radar_data_estoque = [int(top_grp_estoque.get(label, 0)) for label in combined_labels]
                    radar_data_carteira = [int(top_grp_carteira.get(label, 0)) for label in combined_labels]
                    indicator_data = [{"name": label} for label in combined_labels]
                    radar_html = create_pyecharts_radar(indicator_data, radar_data_estoque, radar_data_carteira, "Estoque (Qtd. Itens)", "Carteira (Qtd. Pedidos)")
                    
                    centered_radar_html = f"""
                    <div style="display: flex; justify-content: center; align-items: center; height: 100%; width: 100%;">
                        {radar_html}
                    </div>
                    """
                    components.html(centered_radar_html, height=500)

    with st.sidebar:
        st.header("⚙️ Controles de Análise")
        
        search_type = st.radio(
            "1. Tipo de Pesquisa",
            ["Por Pedido (OV)", "Por Lote (Estoque)"],
            key="search_type_selector"
        )
        
        if st.session_state.current_search_type != search_type:
            st.session_state.analysis_triggered = False
            st.session_state.analysis_results = None
            st.session_state.selected_item = None
            st.session_state.current_search_type = search_type
            st.rerun()

        with st.form(key='analysis_form'):
            if search_type == "Por Pedido (OV)":
                source_items = sorted(df_carteira['OV Item'].astype(str).unique())
                placeholder = "Selecione um Pedido (OV)"
            else: 
                source_items = sorted(df_estoque['Lote Gsd'].astype(str).unique())
                placeholder = "Selecione um Lote (GSD)"

            selected_item = st.selectbox("2. Selecione o Item de Origem", options=source_items, placeholder=placeholder, index=None)
            min_similarity_pct = st.slider("3. Índice Mínimo de Similaridade", 0, 100, 75, step=5, format="%d%%")
            
            analyze_button = st.form_submit_button("Analisar Compatibilidade")

    if analyze_button:
        st.session_state.analysis_triggered = True
        st.session_state.selected_item = selected_item
        st.session_state.min_similarity_pct = min_similarity_pct

        if selected_item:
            if search_type == "Por Pedido (OV)":
                source_df, target_df = df_carteira, df_estoque
                source_id_col = "OV Item"
                mapping = mapping_carteira_to_estoque
            else:
                source_df, target_df = df_estoque, df_carteira
                source_id_col = "Lote Gsd"
                mapping = {v_single: k for k, v_list in mapping_carteira_to_estoque.items() for v_single in (v_list if isinstance(v_list, list) else [v_list])}
            
            source_row = source_df[source_df[source_id_col].astype(str) == selected_item].iloc[0].to_dict()
            resultados_df = calculate_compatibility_vectorized(source_row, target_df.copy(), mapping, (search_type != "Por Pedido (OV)"))
            
            st.session_state.analysis_results = resultados_df
            st.session_state.source_row = source_row
            st.session_state.selected_comparison = None
            st.session_state.results_search_type = search_type
        else:
            st.session_state.analysis_results = pd.DataFrame()
            st.warning("Nenhum item de origem selecionado.")


    with tab2:
        if not st.session_state.analysis_triggered:
            st.info("Utilize o painel de controles na barra lateral para iniciar uma análise.")
        
        elif st.session_state.analysis_results is not None:
            resultados_df = st.session_state.analysis_results
            source_row = st.session_state.source_row
            results_search_type = st.session_state.results_search_type
            selected_item = st.session_state.selected_item
            min_similarity_pct = st.session_state.min_similarity_pct
            
            resultados_df = resultados_df[resultados_df['Índice de Similaridade'] >= (min_similarity_pct / 100.0)].copy()

            st.subheader(f"Análise para o Item de Origem: `{selected_item}`")

            if resultados_df.empty:
                st.warning("Nenhum item compatível encontrado com os filtros atuais.")
            else:
                st.success(f"Encontrados **{len(resultados_df)}** itens compatíveis.")
                
                if results_search_type == "Por Pedido (OV)":
                    display_cols, target_id_col, mapping = ['Lote Gsd', 'Índice de Similaridade', 'Situacao Estoque', 'Posicao Deposito', 'Decisao Prod', 'Qualidade Lote'], "Lote Gsd", mapping_carteira_to_estoque
                else:
                    display_cols, target_id_col, mapping = ['OV Item', 'Índice de Similaridade', 'Status', 'Material', 'Norma Revest.'], "OV Item", {v_single: k for k, v_list in mapping_carteira_to_estoque.items() for v_single in (v_list if isinstance(v_list, list) else [v_list])}
                
                final_cols = [col for col in display_cols if col in resultados_df.columns]
                st.dataframe(resultados_df[final_cols].style.format({'Índice de Similaridade': '{:.0%}'}).background_gradient(cmap='Greens', subset=['Índice de Similaridade']), use_container_width=True, hide_index=True)

                st.markdown("---")
                
                select_options = [f"{row[target_id_col]} - {(row['Índice de Similaridade'] * 100):.0f}%" for _, row in resultados_df.iterrows()]
                
                if st.session_state.selected_comparison not in select_options:
                    st.session_state.selected_comparison = select_options[0] if select_options else None
                
                selected_for_comparison_label = st.selectbox(
                    "Selecione um item para ver o comparativo detalhado:", 
                    options=select_options, 
                    key='selected_comparison'
                )

                if selected_for_comparison_label:
                    try:
                        selected_id_str = selected_for_comparison_label.split(' - ')[0]
                        filtered_df = resultados_df[resultados_df[target_id_col].astype(str) == selected_id_str]

                        if not filtered_df.empty:
                            target_row_details = filtered_df.iloc[0]
                            
                            with st.expander("🔍 Comparativo Detalhado", expanded=True):
                                col_liquid, col_table = st.columns([0.4, 0.6]) 

                                with col_liquid:
                                    match_details = target_row_details['match_details']
                                    num_matches = sum(1 for v in match_details.values() if v)
                                    total_criteria = len(match_details)
                                    
                                    liquid_html_raw = create_pyecharts_liquid_gauge(num_matches, total_criteria)
                                    centered_liquid_html = f"""<div style="display: flex; justify-content: center; align-items: center; height: 100%; width: 100%;">{liquid_html_raw}</div>"""
                                    components.html(centered_liquid_html, height=400)

                                with col_table:
                                    comparison_data = []
                                    if source_row is not None:
                                        for s_col, t_cols in mapping.items():
                                            if s_col in source_row and pd.notna(source_row[s_col]):
                                                t_vals = [str(target_row_details.get(tc, "-")) for tc in (t_cols if isinstance(t_cols, list) else [t_cols])]
                                                is_match = target_row_details['match_details'].get(s_col, False)
                                                comparison_data.append({ "Parâmetro": s_col, "Valor Origem": str(source_row[s_col]), "Valor Encontrado": ' | '.join(t_vals), "Compatível": "✅" if is_match else "❌"})
                                    st.dataframe(pd.DataFrame(comparison_data), height=400) 
                    except (IndexError, KeyError) as e:
                        st.error(f"Ocorreu um erro ao selecionar o item para comparação: {e}. Por favor, execute a análise novamente.")

                csv = convert_df_to_csv(resultados_df)
                st.download_button(label="📥 Baixar Resultados em CSV", data=csv, file_name=f'compatibilidade_{selected_item}.csv', mime='text/csv')
        elif st.session_state.selected_item is None and st.session_state.analysis_triggered:
             st.error("Nenhum item de origem selecionado. Por favor, preencha o formulário na barra lateral e clique em analisar.")

st.markdown("---")
st.markdown("Desenvolvido por *Luis Ignacio*")