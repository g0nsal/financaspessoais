import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
import json
import os

st.set_page_config(page_title="S&G Budget AI Learner", layout="wide")

# --- 1. MEMÓRIA DA IA ---
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

# --- 2. CATEGORIAS ---
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
    
    # 1. Memória Direta
    for termo, cat in memoria.items():
        if termo in desc_upper: return cat, "Aprendido"
            
    # 2. IA Gemini
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Classifica o gasto: '{descricao}'. Categorias: {CATEGORIAS_S_G}. Responde apenas JSON: {{\"categoria\": \"NOME\"}}"
        response = model.generate_content(prompt)
        res_json = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
        return res_json['categoria'], "IA"
    except: return "Outros", "Falha"

# --- 3. INTERFACE ---
st.title("🧠 S&G Budget AI: Relatório de Aprendizagem")

uploaded_file = st.file_uploader("Upload Excel ActivoBank", type=["xlsx"])

if uploaded_file:
    try:
        df_raw = pd.read_excel(uploaded_file, header=None)
        
        # Encontrar onde começa a tabela (procura data DD-MM-YYYY)
        start_row = 0
        for i, row in df_raw.iterrows():
            if re.search(r'\d{2}-\d{2}-\d{4}', str(row[0])):
                start_row = i
                break
        
        df = df_raw.iloc[start_row:].copy()
        
        # Limpeza Crítica: Converter datas e remover linhas inválidas (o fix do teu erro)
        df_proc = pd.DataFrame()
        df_proc['Data'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
        df_proc['Descricao'] = df.iloc[:, 2].astype(str)
        
        # Valor: Tenta coluna 3 ou 4
        v_col = 3 if pd.to_numeric(df.iloc[:, 3], errors='coerce').notnull().sum() > 0 else 4
        df_proc['Valor'] = pd.to_numeric(df.iloc[:, v_col], errors='coerce').fillna(0)
        
        # Remove linhas que não são transações reais
        df_proc = df_proc.dropna(subset=['Data']).copy()
        df_proc = df_proc[df_proc['Valor'] != 0].copy()

        # Evitar re-processar tudo ao clicar em botões
        if 'last_file' not in st.session_state or st.session_state.last_file != uploaded_file.name:
            st.session_state.last_file = uploaded_file.name
            with st.spinner("IA a analisar movimentos..."):
                resultados = [motor_decisao(d) for d in df_proc['Descricao']]
                df_proc['Categoria'] = [r[0] for r in resultados]
                df_proc['Fonte'] = [r[1] for r in resultados]
                st.session_state.df_final = df_proc.reset_index(drop=True)

        # --- RELATÓRIO E FEEDBACK ---
        st.subheader("🤖 Relatório de Classificação")
        
        for i, row in st.session_state.df_final.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                col1.write(f"**{row['Descricao']}** ({row['Valor']:.2f}€)")
                
                # Seleção de categoria com a sugestão da IA já marcada
                current_cat = row['Categoria'] if row['Categoria'] in CATEGORIAS_S_G else "Outros"
                nova_cat = col2.selectbox("Cat", CATEGORIAS_S_G, index=CATEGORIAS_S_G.index(current_cat), key=f"s_{i}", label_visibility="collapsed")
                
                if col3.button("Confirmar", key=f"b_{i}"):
                    # Limpa o texto (tira números) para criar uma regra de memória
                    termo_limpo = re.sub(r'\d+', '', row['Descricao']).split('-')[0].strip()
                    salvar_memoria(termo_limpo, nova_cat)
                    st.toast(f"Aprendido: {termo_limpo} → {nova_cat}")

        # --- OUTPUT PARA EXCEL ---
        st.divider()
        final_sum = st.session_state.df_final[st.session_state.df_final['Valor'] < 0].groupby('Categoria')['Valor'].sum().abs().reset_index()
        
        output_txt = ""
        data_str = st.session_state.df_final['Data'].iloc[0].strftime('%m-%Y')
        for _, r in final_sum.iterrows():
            output_txt += f"01-{data_str}\tTotal {r['Categoria']}\t{str(r['Valor']).replace('.', ',')}\t{r['Categoria']}\n"
        
        st.subheader("📋 Output para o Excel S&G")
        st.text_area("Copia para a aba 'Expenses':", value=output_txt, height=200)

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
