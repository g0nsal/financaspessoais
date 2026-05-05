import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
import json
import os

st.set_page_config(page_title="S&G Budget AI Learner", layout="wide")

# --- 1. REGRAS DE OURO E MEMÓRIA ---
MEMORIA_FILE = "memoria_ia.json"

def carregar_memoria():
    if os.path.exists(MEMORIA_FILE):
        try:
            with open(MEMORIA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def salvar_memoria(termo, categoria):
    memoria = carregar_memoria()
    memoria[termo.upper()] = categoria
    with open(MEMORIA_FILE, "w") as f:
        json.dump(memoria, f)

# Tuas regras prioritárias
REGRAS_FIXAS = {
    "Portagens": r"VIAVERDE|VIA VERDE|A21|A8|A1|A2|A3|A4|A5|A6|A7|A9|A10",
    "Mercearia": r"CONTINENTE|LIDL|PINGO|MINIPRECO|ALDI|AUCHAN|MODELO",
    "Água": r"SMAS|EPAL",
    "Cred. Hab. / Renda": r"PRESTACAO|EMPRESTIMO|CHAB|PAG.PREST",
    "Despesas Médicas": r"MULTICARE|CUF|HOSPITAL|LUSIADAS|SAUDE",
    "Farmácia": r"FARMACIA|FARMÁCIA|FARMA|WELLS|WELL S",
    "Seguros": r"REAL VIDA|OCIDENTAL|FIDELIDADE|REALVSEGUROS",
    "Combustível": r"AUCHAN ENERGY|SODIMAFRA|PRIO|REPSOL|BP|GALP"
}

CATEGORIAS_S_G = [
    "Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", 
    "Água", "Prendas", "Saídas", "Netflix", "Internet", "Cabeleireiro", 
    "Seguros", "Despesas Médicas", "Farmácia", "Decoração/Obras", 
    "Transportes", "Desporto", "Eq. Eletrónicos", "Manutenção Auto", 
    "Viagens", "Entertenimento", "Estado", "Caridade", "Condomínio", 
    "Investimentos", "Telemóveis", "Pastelaria", "Salário", "Outros"
]

def motor_decisao(descricao):
    desc_upper = str(descricao).upper()
    # 1. Regras Fixas
    for cat, pattern in REGRAS_FIXAS.items():
        if re.search(pattern, desc_upper): return cat, "Regra Fixa"
    # 2. Memória
    memoria = carregar_memoria()
    for termo, cat in memoria.items():
        if termo in desc_upper: return cat, "Aprendido"
    return None, "IA"

# --- 2. INTERFACE ---
st.title("🧠 S&G Budget AI: Automação e Somatórios")

uploaded_file = st.file_uploader("Upload Excel ActivoBank", type=["xlsx"])

if uploaded_file:
    try:
        df_raw = pd.read_excel(uploaded_file, header=None)
        start_row = 0
        for i, row in df_raw.iterrows():
            if re.search(r'\d{2}-\d{2}-\d{4}', str(row[0])):
                start_row = i
                break
        
        df = df_raw.iloc[start_row:].copy()
        df_proc = pd.DataFrame()
        df_proc['Data'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
        df_proc['Descricao'] = df.iloc[:, 2].astype(str)
        v_col = 3 if pd.to_numeric(df.iloc[:, 3], errors='coerce').notnull().sum() > 0 else 4
        df_proc['Valor'] = pd.to_numeric(df.iloc[:, v_col], errors='coerce').fillna(0)
        df_proc = df_proc.dropna(subset=['Data']).query("Valor != 0").copy()

        if 'df_final' not in st.session_state or st.session_state.get('last_file') != uploaded_file.name:
            with st.spinner("A aplicar regras e somatórios..."):
                cats, fontes = [], []
                for desc in df_proc['Descricao']:
                    res, fonte = motor_decisao(desc)
                    cats.append(res if res else "Outros") # Fallback para Outros se a IA não correu
                    fontes.append(fonte)
                
                df_proc['Categoria'] = cats
                df_proc['Fonte'] = fontes
                st.session_state.df_final = df_proc.reset_index(drop=True)
                st.session_state.last_file = uploaded_file.name

        # --- OUTPUT PARA EXCEL (O SUMIF que faltava) ---
        st.subheader("📋 Output para o Excel S&G (Somado)")
        
        # Filtrar apenas despesas negativas para o somatório
        df_despesas = st.session_state.df_final[st.session_state.df_final['Valor'] < 0].copy()
        df_despesas['Valor'] = df_despesas['Valor'].abs()
        
        # Agrupar por Categoria (O teu SUMIF automático)
        resumo_mensal = df_despesas.groupby('Categoria')['Valor'].sum().reset_index()
        
        output_txt = ""
        data_str = st.session_state.df_final['Data'].iloc[0].strftime('%m-%Y')
        for _, r in resumo_mensal.iterrows():
            # Data | Descrição Fixa | Valor Somado | Categoria
            valor_pt = f"{r['Valor']:.2f}".replace('.', ',')
            output_txt += f"01-{data_str}\tTotal {r['Categoria']}\t{valor_pt}\t{r['Categoria']}\n"
        
        st.text_area("Copia para o Excel (Resumo Mensal):", value=output_txt, height=200)

        # --- RELATÓRIO DE CONFERÊNCIA ---
        st.divider()
        st.subheader("🔍 Conferir Movimentos Individuais")
        with st.form("form_ajustes"):
            for i, row in st.session_state.df_final.iterrows():
                col1, col2 = st.columns([3, 1])
                idx_cat = CATEGORIAS_S_G.index(row['Categoria']) if row['Categoria'] in CATEGORIAS_S_G else 0
                nova = col1.selectbox(f"{row['Descricao']} ({row['Valor']:.2f}€)", CATEGORIAS_S_G, index=idx_cat, key=f"s_{i}")
                # Se mudares, marcamos para aprender
                if col2.checkbox("Ensinar IA", key=f"c_{i}"):
                    termo = re.sub(r'\d+', '', row['Descricao']).split('-')[0].strip()
                    salvar_memoria(termo, nova)
            
            if st.form_submit_button("Recalcular Somatórios"):
                st.rerun()

    except Exception as e:
        st.error(f"Erro: {e}")
