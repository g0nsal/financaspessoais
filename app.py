import streamlit as st
import pandas as pd
import google.generativeai as genai
import sqlite3
import re

# --- CONFIGURAÇÃO DA BASE DE DADOS ---
conn = sqlite3.connect('financas.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS memoria 
             (termo TEXT PRIMARY KEY, categoria TEXT)''')
conn.commit()

def aprender_regra(termo, categoria):
    c.execute("INSERT OR REPLACE INTO memoria VALUES (?, ?)", (termo.upper(), categoria))
    conn.commit()

def consultar_memoria(descricao):
    c.execute("SELECT categoria FROM memoria")
    regras = c.fetchall()
    desc_upper = descricao.upper()
    # Busca por termos aprendidos
    c.execute("SELECT termo, categoria FROM memoria")
    for termo, cat in c.fetchall():
        if termo in desc_upper:
            return cat
    return None

# --- ENGINE DE CATEGORIZAÇÃO ---
def categorizar_inteligente(desc):
    desc_upper = str(desc).upper()
    
    # 1. Tenta Memória Permanente (O que tu já ensinaste)
    memo = consultar_memoria(desc_upper)
    if memo: return memo

    # 2. IA Gemini com Prompt Reforçado
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""Age como contabilista. Categoriza este movimento bancário: "{desc}".
        Categorias: {st.session_state.categorias_list}.
        Dicas: VIAVERDE=Portagens, PINGO/CONTINENTE=Mercearia, REAL VIDA=Seguros, WOO=Telemóveis, MB WAY=Outros (ou Saídas se for restaurante).
        Responde APENAS o nome da categoria."""
        res = model.generate_content(prompt).text.strip()
        return res if res in st.session_state.categorias_list else "Outros"
    except:
        return "Outros"

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="S&G Budget Pro v5", layout="wide")
if 'categorias_list' not in st.session_state:
    st.session_state.categorias_list = ["Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", "Água", "Seguros", "Farmácia", "Decoração/Obras", "Internet", "Telemóveis", "Portagens", "Gás", "Eletricidade", "Outros"]

st.title("🧠 S&G Budget: Sistema com Memória Permanente")

file = st.file_uploader("Upload do Extrato", type="xlsx")

if file:
    df_raw = pd.read_excel(file, header=None)
    # (Lógica de detecção de linha inicial...)
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

    # Processar
    with st.spinner("A consultar memória e IA..."):
        df_proc['Categoria'] = df_proc['Descricao'].apply(categorizar_inteligente)

    # --- TABELA DE TREINO (OK/KO) ---
    st.subheader("🎓 Ensina a tua IA (As tuas correções ficam gravadas para sempre)")
    with st.expander("Clique para validar/corrigir movimentos individuais"):
        for i, row in df_proc.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(row['Descricao'])
            nova_cat = col2.selectbox(f"Categoria {i}", st.session_state.categorias_list, 
                                      index=st.session_state.categorias_list.index(row['Categoria']),
                                      key=f"sel_{i}", label_visibility="collapsed")
            if col3.button("Gravar", key=f"btn_{i}"):
                # Limpa o nome para gravar regra (ex: tira números)
                termo_limpo = re.sub(r'\d+', '', row['Descricao']).split('-')[0].strip()
                aprender_regra(termo_limpo, nova_cat)
                st.success(f"Aprendido: {termo_limpo}!")

    # --- SUMIF FINAL ---
    st.divider()
    despesas = df_proc[df_proc['Valor'] < 0].copy()
    despesas['Valor'] = despesas['Valor'].abs()
    resumo = despesas.groupby('Categoria')['Valor'].sum().reset_index()
    
    output = ""
    mes_ano = df_proc['Data'].iloc[0].strftime('%m-%Y')
    for _, r in resumo.iterrows():
        val = f"{r['Valor']:.2f}".replace('.', ',')
        output += f"01-{mes_ano}\tTotal {r['Categoria']}\t{val}\t{r['Categoria']}\n"
    
    st.subheader("📋 Output para o Excel S&G")
    st.text_area("Copia para o Excel:", value=output, height=200)
