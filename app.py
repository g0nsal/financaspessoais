import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import json
import os

# --- 1. CONFIGURAÇÃO E CATEGORIAS REAIS ---
st.set_page_config(page_title="Budget Tracking S&G", layout="wide")

# Lista exata baseada no teu Excel
MINHAS_CATEGORIAS = [
    "Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", 
    "Água", "Prendas", "Saídas", "Netflix", "Internet", "Cabeleireiro", 
    "Seguros", "Despesas Médicas", "Farmácia", "Decoração/Obras", 
    "Transportes", "Desporto", "Eq. Eletrónicos", "Manutenção Auto", 
    "Viagens", "Entertenimento", "Estado", "Caridade", "Condomínio", 
    "Investimentos", "Telemóveis", "Pastelaria", "Cartão de Crédito", 
    "Portagens", "Gás", "Eletricidade", "Limpeza", "Salário", "Outros"
]

MEMORY_FILE = "memoria_categorias.json"

def carregar_memoria():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f: return json.load(f)
        except: return {"Dicionario": {}}
    return {"Dicionario": {}}

def guardar_memoria(memoria):
    with open(MEMORY_FILE, "w") as f: json.dump(memoria, f)

def sugerir_categoria_ia(descricao):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        Categoriza este movimento bancário: '{descricao}'
        Usa uma destas categorias: {MINHAS_CATEGORIAS}
        Regras: 'PAG.PRESTACAO' ou 'EMPR' -> 'Cred. Hab. / Renda'. 'PINGO DOCE' ou 'CONTINENTE' -> 'Mercearia'.
        Responde apenas a palavra exata.
        """
        response = model.generate_content(prompt)
        sugestao = response.text.strip()
        return sugestao if sugestao in MINHAS_CATEGORIAS else "Outros"
    except: return "Outros"

# --- 2. INTERFACE ---
st.title("📊 Budget Tracking S&G")

dados_memoria = carregar_memoria()
if "Dicionario" not in dados_memoria: dados_memoria["Dicionario"] = {}

uploaded_file = st.file_uploader("Upload do Extrato Excel", type="xlsx")

if uploaded_file:
    try:
        # Encontrar cabeçalho
        df_all = pd.read_excel(uploaded_file, header=None)
        header_idx = 0
        for i, row in df_all.iterrows():
            row_str = " ".join([str(x).lower() for x in row if pd.notnull(x)])
            if 'descri' in row_str or 'movimento' in row_str:
                header_idx = i
                break
        
        df_orig = pd.read_excel(uploaded_file, header=header_idx)
        df_orig = df_orig.loc[:, ~df_orig.columns.str.contains('^Unnamed')]
        
        # Mapeamento robusto
        temp_df = pd.DataFrame()
        for col in df_orig.columns:
            c_low = str(col).lower()
            if 'data' in c_low and 'valor' not in c_low and 'Data' not in temp_df.columns:
                temp_df['Data'] = df_orig[col]
            elif ('desc' in c_low or 'hist' in c_low) and 'Descricao' not in temp_df.columns:
                temp_df['Descricao'] = df_orig[col]
            elif any(x in c_low for x in ['valor', 'import', 'montante']) and 'Data' not in c_low and 'Valor' not in temp_df.columns:
                temp_df['Valor'] = df_orig[col]

        # Fallback se não detectar
        if len(temp_df.columns) < 3:
            temp_df = df_orig.iloc[:, [0, 1, 2]]
            temp_df.columns = ['Data', 'Descricao', 'Valor']

        df = temp_df.dropna(subset=['Descricao', 'Valor']).copy()
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)

        # Categorização
        novos = []
        desc_unicas = df['Descricao'].unique()
        map_sugestoes = {}

        for d in desc_unicas:
            if d in dados_memoria["Dicionario"]:
                map_sugestoes[d] = dados_memoria["Dicionario"][d]
            else:
                sug = sugerir_categoria_ia(d)
                map_sugestoes[d] = f"❓ {sug}"
                novos.append(d)

        df['Categoria'] = df['Descricao'].map(map_sugestoes)

        # Painel de Ensino
        if novos:
            with st.expander("🎓 Validar Movimentos Novos", expanded=True):
                for i, item in enumerate(novos[:15]):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    sug_limpa = map_sugestoes[item].replace("❓ ", "")
                    idx = MINHAS_CATEGORIAS.index(sug_limpa) if sug_limpa in MINHAS_CATEGORIAS else 0
                    c1.write(f"**{item}**")
                    escolha = c2.selectbox(f"Cat_{i}", MINHAS_CATEGORIAS, index=idx, key=f"sel_{i}", label_visibility="collapsed")
                    if c3.button("✓", key=f"btn_{i}"):
                        dados_memoria["Dicionario"][item] = escolha
                        guardar_memoria(dados_memoria)
                        st.rerun()

        # DASHBOARD
        st.divider()
        gastos = df[df['Valor'] < 0]
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Despesas", f"{abs(gastos['Valor'].sum()):.2f}€")
        col_b.metric("Receitas", f"{df[df['Valor'] > 0]['Valor'].sum():.2f}€")
        col_c.metric("Saldo", f"{df['Valor'].sum():.2f}€")

        df_p = df.copy()
        df_p['Categoria'] = df_p['Categoria'].str.replace("❓ ", "")
        gastos_cat = df_p[df_p['Valor'] < 0].groupby('Categoria')['Valor'].sum().abs().reset_index().sort_values('Valor')
        
        fig = px.bar(gastos_cat, x='Valor', y='Categoria', orientation='h', title="Gastos por Categoria")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
