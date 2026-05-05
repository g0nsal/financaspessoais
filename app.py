import streamlit as st
import pandas as pd
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import re

# --- CONFIGURAÇÃO DA APP ---
st.set_page_config(page_title="S&G Budget AI", layout="wide")

# Ligação à Google Sheet (Memória Permanente)
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_memoria():
    try:
        return conn.read(worksheet="Memoria")
    except:
        return pd.DataFrame(columns=["Termo", "Categoria"])

def salvar_na_memoria(termo, categoria):
    memoria_atual = carregar_memoria()
    nova_regra = pd.DataFrame([{"Termo": termo.upper(), "Categoria": categoria}])
    # Evitar duplicados e atualizar
    updated_mem = pd.concat([memoria_atual[memoria_atual['Termo'] != termo.upper()], nova_regra])
    conn.update(worksheet="Memoria", data=updated_mem)
    st.toast(f"✅ Aprendido: {termo} é {categoria}")

# --- MOTOR DE INTELIGÊNCIA ---
def categorizar_inteligente(desc, categorias_disponiveis):
    desc_upper = str(desc).upper()
    memoria = carregar_memoria()
    
    # 1. Procura na Memória (O que já ensinaste)
    for _, row in memoria.iterrows():
        if str(row['Termo']) in desc_upper:
            return row['Categoria'], "Memória"
            
    # 2. IA Gemini (Especialista em Finanças)
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Categoriza: '{desc}'. Categorias: {categorias_disponiveis}. Responde apenas o nome da categoria."
        res = model.generate_content(prompt).text.strip()
        return res if res in categorias_disponiveis else "Outros", "IA"
    except:
        return "Outros", "Erro"

# --- INTERFACE ---
st.title("📊 S&G Budget AI: O teu Gestor Autónomo")

categorias = ["Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", "Água", "Seguros", "Farmácia", "Decoração/Obras", "Internet", "Telemóveis", "Portagens", "Gás", "Eletricidade", "Outros"]

file = st.file_uploader("Upload do Extrato Bancário", type="xlsx")

if file:
    # Lógica de leitura (ActivoBank)
    df_raw = pd.read_excel(file, header=None)
    start_row = 0
    for i, row in df_raw.iterrows():
        if re.search(r'\d{2}-\d{2}-\d{4}', str(row[0])):
            start_row = i
            break
    
    df = pd.read_excel(file, skiprows=start_row)
    df_proc = pd.DataFrame()
    df_proc['Data'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
    df_proc['Descricao'] = df.iloc[:, 2].astype(str)
    v_col = 3 if pd.to_numeric(df.iloc[:, 3], errors='coerce').notnull().sum() > 5 else 4
    df_proc['Valor'] = pd.to_numeric(df.iloc[:, v_col], errors='coerce').fillna(0)
    df_proc = df_proc.dropna(subset=['Data']).query("Valor != 0").copy()

    # Processar com IA e Memória
    with st.spinner("A organizar as tuas finanças..."):
        resultados = [categorizar_inteligente(d, categorias) for d in df_proc['Descricao']]
        df_proc['Categoria'] = [r[0] for r in resultados]
        df_proc['Fonte'] = [r[1] for r in resultados]

    # Interface de Validação (Onde tu ensinas a App)
    st.subheader("🎓 Validação e Aprendizagem")
    with st.form("validacao"):
        novas_cats = []
        for i, row in df_proc.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(f"{row['Descricao']} ({row['Valor']:.2f}€)")
            idx = categorias.index(row['Categoria']) if row['Categoria'] in categorias else 0
            sel = col2.selectbox("Cat", categorias, index=idx, key=f"s_{i}", label_visibility="collapsed")
            novas_cats.append(sel)
            # Botão de ensinar dentro do form (ou gerido por lógica posterior)
        
        if st.form_submit_button("Confirmar Tudo e Gerar Relatório"):
            for i, (orig, nova) in enumerate(zip(df_proc['Categoria'], novas_cats)):
                if orig != nova or df_proc.iloc[i]['Fonte'] == "IA":
                    termo = re.sub(r'\d+', '', df_proc.iloc[i]['Descricao']).split('-')[0].strip()
                    salvar_na_memoria(termo, nova)
            df_proc['Categoria'] = novas_cats
            st.session_state.ready = True
            st.session_state.df_ready = df_proc

if 'ready' in st.session_state:
    # Relatório Final Somado (O teu Excel automático)
    st.divider()
    resumo = st.session_state.df_ready[st.session_state.df_ready['Valor'] < 0].copy()
    resumo['Valor'] = resumo['Valor'].abs()
    final = resumo.groupby('Categoria')['Valor'].sum().reset_index()
    
    st.subheader("📈 Resumo Mensal (Somas Automáticas)")
    st.table(final)
    
    # Gerar texto para o teu Excel habitual (se ainda o quiseres usar)
    output = ""
    for _, r in final.iterrows():
        val = f"{r['Valor']:.2f}".replace('.', ',')
        output += f"01-Mês\tTotal {r['Categoria']}\t{val}\t{r['Categoria']}\n"
    st.text_area("Copia para o teu Excel:", value=output)
