import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
import json
import os

st.set_page_config(page_title="S&G Budget AI Learner", layout="wide")

# --- 1. MEMÓRIA DA IA (Onde ela aprende) ---
MEMORIA_FILE = "memoria_ia.json"

def carregar_memoria():
    if os.path.exists(MEMORIA_FILE):
        with open(MEMORIA_FILE, "r") as f:
            return json.load(f)
    return {}

def salvar_memoria(nova_regra, categoria):
    memoria = carregar_memoria()
    memoria[nova_regra.upper()] = categoria
    with open(MEMORIA_FILE, "w") as f:
        json.dump(memoria, f)

# --- 2. REGRAS E CATEGORIAS ---
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
    memoria = carregar_memoria()
    
    # 1. Verificar Memória Aprendida
    for termo, cat in memoria.items():
        if termo in desc_upper:
            return cat, "Aprendido"
            
    # 2. IA Audaz (Gemini)
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""Age como gestor financeiro em Portugal. 
        Classifica o gasto: '{descricao}'. 
        Categorias: {CATEGORIAS_S_G}. 
        Responde apenas no formato JSON: {{"categoria": "NOME", "confianca": 0.95, "motivo": "porque..."}}"""
        
        response = model.generate_content(prompt)
        res_json = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
        return res_json['categoria'], f"IA ({res_json['confianca']*100:.0f}%)"
    except:
        return "Outros", "Falha"

# --- 3. INTERFACE ---
st.title("🧠 S&G Budget AI: Relatório de Aprendizagem")

uploaded_file = st.file_uploader("Upload Excel ActivoBank", type=["xlsx"])

if uploaded_file:
    df_raw = pd.read_excel(uploaded_file, header=None)
    # (Lógica de detecção de start_row igual à anterior)
    start_row = 0
    for i, row in df_raw.iterrows():
        if re.search(r'\d{2}-\d{2}-\d{4}', str(row[0])):
            start_row = i
            break
    
    df = df_raw.iloc[start_row:].copy()
    df_proc = pd.DataFrame()
    df_proc['Data'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True)
    df_proc['Descricao'] = df.iloc[:, 2].astype(str)
    
    # Detecção de Valor
    col_v = 3 if not pd.to_numeric(df.iloc[:, 3], errors='coerce').dropna().empty else 4
    df_proc['Valor'] = pd.to_numeric(df.iloc[:, col_v], errors='coerce').fillna(0)
    df_proc = df_proc[df_proc['Valor'] < 0].copy() # Foco em despesas
    df_proc['Valor'] = df_proc['Valor'].abs()

    # Processar com Relatório
    if 'processado' not in st.session_state:
        resultados = []
        for d in df_proc['Descricao']:
            cat, fonte = motor_decisao(d)
            resultados.append({'Categoria': cat, 'Fonte': fonte})
        st.session_state.df_final = pd.concat([df_proc.reset_index(drop=True), pd.DataFrame(resultados)], axis=1)
        st.session_state.processado = True

    # --- RELATÓRIO DE DÚVIDAS ---
    st.subheader("🤖 Relatório da IA: O que eu fiz?")
    
    # Tabela de Feedback
    for i, row in st.session_state.df_final.iterrows():
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        with col1: st.write(f"**{row['Descricao']}**")
        with col2: 
            nova_cat = st.selectbox(f"Categoria", CATEGORIAS_S_G, index=CATEGORIAS_S_G.index(row['Categoria']) if row['Categoria'] in CATEGORIAS_S_G else 0, key=f"sel_{i}")
        with col3: 
            st.caption(f"Fonte: {row['Fonte']}")
        with col4:
            if st.button("✅ OK", key=f"btn_{i}"):
                if row['Fonte'].startswith("IA"):
                    # Extrair termo chave para aprender (ex: tirar números da descrição)
                    termo_chave = "".join([i for i in row['Descricao'] if not i.isdigit()]).split('-')[0].strip()
                    salvar_memoria(termo_chave, nova_cat)
                    st.success(f"Aprendi: {termo_chave}!")

    # --- OUTPUT FINAL PARA EXCEL ---
    st.divider()
    resumo = st.session_state.df_final.groupby(['Categoria'])['Valor'].sum().reset_index()
    output_text = ""
    data_ref = st.session_state.df_final['Data'].iloc[0].strftime('%m-%Y')
    for _, r in resumo.iterrows():
        output_text += f"01-{data_ref}\tTotal {r['Categoria']}\t{str(r['Valor']).replace('.', ',')}\t{r['Categoria']}\n"
    
    st.subheader("📋 Dados Finais (Após o teu OK/KO)")
    st.text_area("Copia para o Excel S&G:", value=output_text, height=200)
