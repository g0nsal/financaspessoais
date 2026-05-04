import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import json
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Financeira Gonsalo", layout="wide")

# Ficheiro local para guardar o que a IA aprendeu
MEMORY_FILE = "memoria_categorias.json"

def carregar_memoria():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f: return json.load(f)
    return {}

def guardar_memoria(memoria):
    with open(MEMORY_FILE, "w") as f: json.dump(memoria, f)

# --- FUNÇÃO DE IA CORRIGIDA ---
def sugerir_categoria_ia(descricao):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Usando a versão estável para evitar o erro 404
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        prompt = f"Categoriza este gasto bancário em Portugal: '{descricao}'. Escolha uma: [Alimentação, Habitação, Transportes, Saúde, Lazer, Estado, Investimentos, Salário, Transferências, Outros]. Responde apenas a palavra."
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Outros"

# --- INTERFACE ---
st.title("🏦 Dashboard Inteligente Familiar")

memoria = carregar_memoria()
uploaded_file = st.file_uploader("Upload Excel", type="xlsx")

if uploaded_file:
    df_raw = pd.read_excel(uploaded_file)
    if "Descrição" not in df_raw.columns:
        df_raw = pd.read_excel(uploaded_file, header=7)

    # Limpeza e Padronização
    mapping_cols = {'Descrição': 'Descricao', 'Importância': 'Valor', 'Montante': 'Valor', 'Valor': 'Valor', 'Data Mov.': 'Data'}
    df = df_raw.rename(columns=mapping_cols)
    df = df[['Data', 'Descricao', 'Valor']].dropna()
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')

    # --- CATEGORIZAÇÃO HÍBRIDA ---
    categorias_finais = []
    novos_movimentos = []

    for desc in df['Descricao']:
        if desc in memoria:
            categorias_finais.append(memoria[desc])
        else:
            # Se não conhece, pede sugestão à IA mas marca como "Novo"
            sugestao = sugerir_categoria_ia(desc)
            categorias_finais.append(f"❓ {sugestao}")
            if desc not in novos_movimentos: novos_movimentos.append(desc)

    df['Categoria'] = categorias_finais

    # --- ZONA DE ENSINO (Aprender com o Utilizador) ---
    if novos_movimentos:
        with st.expander("🎓 Ensinar novas categorias", expanded=True):
            st.write("Encontrei movimentos novos. Confirma ou altera:")
            for m in novos_movimentos[:10]: # Mostra 10 de cada vez para não sobrecarregar
                col_a, col_b = st.columns([2,1])
                nova_cat = col_b.selectbox(f"Categoria para: {m}", 
                                         ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"],
                                         key=m)
                if col_a.button(f"Confirmar {m}"):
                    memoria[m] = nova_cat
                    guardar_memoria(memoria)
                    st.rerun()

    # --- DASHBOARD ---
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    despesas = df[df['Valor'] < 0]
    
    m1.metric("Gastos Totais", f"{abs(despesas['Valor'].sum()):.2f}€")
    m2.metric("Movimentos Novos", len(novos_movimentos))
    
    c1, c2 = st.columns(2)
    with c1:
        # Limpar o prefixo "❓ " para o gráfico
        df_plot = df.copy()
        df_plot['Categoria'] = df_plot['Categoria'].str.replace("❓ ", "")
        fig = px.pie(df_plot[df_plot['Valor'] < 0], values=df_plot[df_plot['Valor'] < 0]['Valor'].abs(), names='Categoria', hole=0.4)
        st.plotly_chart(fig)
    
    with c2:
        st.dataframe(df)
