import pandas as pd
from flask import Flask, jsonify, render_template
import os
import traceback

# --- Configurações Iniciais ---
app = Flask(__name__)

# --- Constantes de Configuração (Melhora a Manutenibilidade) ---
PATH_CARTEIRA = r"C:\Users\csp4992\OneDrive - Companhia Siderurgica Nacional\Área de Trabalho\PROJECTS\PROJETO QUALIDADE\Carteira_Geral NOVA_GERAL-pt-br.xlsx"
PATH_ESTOQUE = r"C:\Users\csp4992\OneDrive - Companhia Siderurgica Nacional\Área de Trabalho\PROJECTS\PROJETO QUALIDADE\Estoque CSN Porto Real-pt-br.xlsx"

MAPPING_C_E = { 'Grp Merc': 'Grp Mercadoria', 'Prd': 'Produto Basico Ov', 'Material GSD': 'Material Antigo Gsd', 'Material': 'Material', 'Especificacão': 'Especificaçao LZ', 'Norma Revest.': 'Revestimento Lote 1', 'Esp': ['Esp R', 'Esp C', 'Esp BFF'], 'Larg.': ['Larg R', 'Larg BFF', 'Larg C'], 'Sup': 'Superficie Ov', 'Apara': 'Apara Ov', 'Trat. Quim.': ['Trat Quimico Inf Real', 'Trat Qumico Sup Real'], 'Peso Peça': 'Peso Peca', 'Peso Min': 'Peso Minimo', 'Peso Max': 'Peso Maximo', 'Rota GSD': 'Rota', 'Quant. Óleo': 'Quantidade de Oleo', 'Lam. Encruam.': 'Laminacao Encruamento Real', 'Uso final': 'Uso Final' }
NUMERIC_COLS_C = ['Esp', 'Tol. Inf. Esp.', 'Tol. Sup. Esp.', 'Larg.', 'Tol. Inf. Larg', 'Tol. Sup. Larg', 'Peso Peça', 'Peso Min', 'Peso Max', 'Quant. Óleo']
NUMERIC_COLS_E = ['Esp R', 'Esp C', 'Esp BFF', 'Larg R', 'Larg BFF', 'Larg C', 'Peso Peca', 'Peso Minimo', 'Peso Maximo', 'Quantidade de Oleo', 'Peso Estoque']

# --- Funções de Apoio ---
def to_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '.'), errors='coerce')

_cache = {}

def validate_dataframes(df_carteira, df_estoque):
    """Verifica se todas as colunas necessárias existem nos dataframes."""
    required_cols_c = set(MAPPING_C_E.keys()) | set(NUMERIC_COLS_C)
    required_cols_e = set(v for v_list in MAPPING_C_E.values() for v in (v_list if isinstance(v_list, list) else [v_list])) | set(NUMERIC_COLS_E)
    
    missing_c = [col for col in required_cols_c if col not in df_carteira.columns]
    missing_e = [col for col in required_cols_e if col not in df_estoque.columns]

    errors = []
    if missing_c:
        errors.append(f"Colunas faltando no arquivo Carteira: {', '.join(missing_c)}")
    if missing_e:
        errors.append(f"Colunas faltando no arquivo Estoque: {', '.join(missing_e)}")
    
    if errors:
        raise ValueError(" | ".join(errors))

def load_and_cache_data():
    """Carrega, valida, pré-processa e armazena os dados em cache."""
    if 'df_carteira' in _cache and 'df_estoque' in _cache:
        return _cache['df_carteira'], _cache['df_estoque'], None

    if not os.path.exists(PATH_CARTEIRA): return None, None, f"Arquivo não encontrado: {PATH_CARTEIRA}"
    if not os.path.exists(PATH_ESTOQUE): return None, None, f"Arquivo não encontrado: {PATH_ESTOQUE}"

    try:
        df_carteira = pd.read_excel(PATH_CARTEIRA)
        df_estoque = pd.read_excel(PATH_ESTOQUE)

        df_carteira = df_carteira.rename(columns={c: c.strip() for c in df_carteira.columns})
        df_estoque = df_estoque.rename(columns={c: c.strip() for c in df_estoque.columns})

        validate_dataframes(df_carteira, df_estoque)

        for col in NUMERIC_COLS_C:
            if col in df_carteira.columns: df_carteira[col] = to_numeric(df_carteira[col])
        for col in NUMERIC_COLS_E:
            if col in df_estoque.columns: df_estoque[col] = to_numeric(df_estoque[col])
        
        df_carteira.dropna(subset=['OV Item'], inplace=True)
        df_estoque.dropna(subset=['Lote Gsd'], inplace=True)

        _cache['df_carteira'] = df_carteira
        _cache['df_estoque'] = df_estoque
        return df_carteira, df_estoque, None
    except Exception as e:
        return None, None, f"Erro ao processar arquivos: {e}"

# --- Lógica de Análise (Vetorizada para Performance) ---
def calculate_compatibility_vectorized(source_row, target_df, mapping):
    match_matrix = pd.DataFrame(index=target_df.index)
    total_criteria = 0

    for source_col, target_cols in mapping.items():
        target_cols_list = target_cols if isinstance(target_cols, list) else [target_cols]
        if source_col not in source_row or pd.isna(source_row[source_col]): continue
        
        total_criteria += 1
        source_val = source_row[source_col]
        
        combined_mask = pd.Series(False, index=target_df.index)
        
        if source_col in ['Esp', 'Larg.']:
            tol_inf_col = 'Tol. Inf. Esp.' if source_col == 'Esp' else 'Tol. Inf. Larg'
            tol_sup_col = 'Tol. Sup. Esp.' if source_col == 'Esp' else 'Tol. Sup. Larg'
            if tol_inf_col in source_row and tol_sup_col in source_row:
                min_val = source_val - source_row[tol_inf_col]
                max_val = source_val + source_row[tol_sup_col]
                if pd.notna(min_val) and pd.notna(max_val):
                    for tc in target_cols_list:
                        if tc in target_df.columns:
                            combined_mask |= (target_df[tc] >= min_val) & (target_df[tc] <= max_val)
        else:
            for tc in target_cols_list:
                if tc in target_df.columns:
                    combined_mask |= (target_df[tc].astype(str).str.strip().str.lower() == str(source_val).strip().lower())
        
        match_matrix[source_col] = combined_mask

    similarity_scores = match_matrix.sum(axis=1) / total_criteria if total_criteria > 0 else 0
    
    results_df = target_df.copy()
    results_df['Índice de Similaridade'] = similarity_scores
    results_df['match_details'] = match_matrix.to_dict(orient='records')
    
    return results_df

# --- Rotas da Aplicação ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/dashboard-data')
def get_dashboard_data():
    try:
        df_carteira, df_estoque, error = load_and_cache_data()
        if error or df_carteira is None or df_estoque is None:
            return jsonify({"error": error or "Dados não carregados corretamente."}), 500

        kpis = { "pedidos_carteira": int(df_carteira['OV Item'].nunique()), "lotes_estoque": int(df_estoque['Lote Gsd'].nunique()), "peso_total_estoque": float(df_estoque['Peso Estoque'].sum() / 1000) }
        city_coords = { 'PORTO REAL': [-44.2928, -22.4208], 'SAO PAULO': [-46.6333, -23.5505], 'SAO JOSE DOS PINHAIS': [-49.206, -25.5342], 'GRAVATAI': [-50.9936, -29.9419], 'SAO CAETANO DO SUL': [-46.5736, -23.6142], 'SAO JOSE DOS CAMPOS': [-45.8869, -23.1791], 'MOGI DAS CRUZES': [-46.1889, -23.5236], 'SAO LEOPOLDO': [-51.1469, -29.7594], 'JUATUBA': [-44.3486, -19.9519], 'SUZANO': [-46.3106, -23.5431], 'ARAUCARIA': [-49.4125, -25.5931], 'CHICAGO': [-87.6298, 41.8781], 'BETIM': [-44.1983, -19.9678], 'CONTAGEM': [-44.0531, -19.9322], 'PINHEIRAL': [-44.0044, -22.5133], 'VALENCA': [-43.7008, -22.2464], 'SAO JOSE DO RIO PRETO': [-49.3792, -20.8203], 'MAUA': [-46.4614, -23.6678], 'ITAQUAQUECETUBA': [-46.3483, -23.4864], 'QUEIMADOS': [-43.5558, -22.7158], 'POUSO ALEGRE': [-45.9342, -22.23], 'LIMEIRA': [-47.4072, -22.565], 'ARUJA': [-46.5219, -23.3961], 'JARINU': [-46.7303, -23.0994], 'CRUZEIRO': [-44.9686, -22.5761], 'JOINVILLE': [-48.8456, -26.3031], 'RESENDE': [-44.4469, -22.4686], 'VASSOURAS': [-43.6625, -22.4044], 'SANTA ISABEL': [-46.2239, -23.3183], 'SAO BERNARDO DO CAMPO': [-46.5542, -23.6939] }
        cidades_carteira = df_carteira['Cidade'].str.upper().value_counts()
        map_data, scatter_data = [], []
        for city, value in cidades_carteira.items():
            if city in city_coords:
                map_data.append([{'coord': city_coords['PORTO REAL']}, {'coord': city_coords[str(city)]}])
                scatter_data.append({'name': str(city).title(), 'value': city_coords[str(city)] + [int(value)]})

        top_grp_estoque = df_estoque.groupby('Grp Mercadoria').agg(total_peso=('Peso Estoque', 'sum')).nlargest(5, 'total_peso')
        top_grp_carteira = df_carteira['Grp Merc'].value_counts().nlargest(5)
        combined_labels = sorted(list(set(top_grp_estoque.index) | set(top_grp_carteira.index)))
        def safe_float(val):
            try:
                # Only convert if not complex and not None
                if val is None or isinstance(val, complex):
                    return 0.0
                return float(val)
            except Exception:
                return 0.0

        radar_data = {
            "labels": combined_labels,
            "estoque": [safe_float(top_grp_estoque.loc[label, 'total_peso']) if label in top_grp_estoque.index else 0.0 for label in combined_labels],
            "carteira": [int(top_grp_carteira.get(label, 0)) for label in combined_labels]
        }
        
        return jsonify({ "kpis": kpis, "mapData": {"routes": map_data, "cities": scatter_data}, "radarData": radar_data })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro interno no servidor: {e}"}), 500

@app.route('/api/source-items/<search_type>')
def get_source_items(search_type):
    try:
        df_carteira, df_estoque, error = load_and_cache_data()
        if error or df_carteira is None: 
            return jsonify({"error": error or "Dados não carregados corretamente."}), 500
        
        items = sorted(df_carteira['OV Item' if search_type == "pedido" else 'Lote Gsd'].astype(str).unique())
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": f"Erro ao carregar itens de origem: {e}"}), 500

@app.route('/api/analyze/<search_type>/<item_id>')
def analyze(search_type, item_id):
    try:
        df_carteira, df_estoque, error = load_and_cache_data()
        if error: return jsonify({"error": error}), 500

        if search_type == "pedido":
            source_df, target_df = df_carteira, df_estoque
            if source_df is None:
                return jsonify({"error": "Dados de origem não carregados corretamente."}), 500
            filtered = source_df[source_df['OV Item'].astype(str) == item_id]
            if filtered.empty:
                return jsonify({"error": f"Item de origem '{item_id}' não encontrado."}), 404
            source_row = filtered.iloc[0]
            results = calculate_compatibility_vectorized(source_row, target_df, MAPPING_C_E)
        else: # Lote
            source_df, target_df = df_estoque, df_carteira
            if source_df is None:
                return jsonify({"error": "Dados de origem não carregados corretamente."}), 500
            filtered = source_df[source_df['Lote Gsd'].astype(str) == item_id]
            if filtered.empty:
                return jsonify({"error": f"Lote de origem '{item_id}' não encontrado."}), 404
            source_row = filtered.iloc[0]
            mapping_e_c = {v_single: k for k, v_list in MAPPING_C_E.items() for v_single in (v_list if isinstance(v_list, list) else [v_list])}
            results = calculate_compatibility_vectorized(source_row, target_df, mapping_e_c)

        results_json = results.where(pd.notna(results), None).to_dict(orient='records')
        source_row_json = source_row.where(pd.notna(source_row), None).to_dict()

        return jsonify({ "results": results_json, "sourceItem": source_row_json, "mapping": MAPPING_C_E })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro durante a análise: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
