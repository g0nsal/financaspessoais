import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import json
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Financeira Gonsalo", layout="wide")

MEMORY_FILE = "memoria_categorias.json"

def carregar_memoria():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def guardar_memoria(memoria):
    with open(MEMORY_FILE, "w") as f: json.dump(memoria, f)

def sugerir_categoria_ia(descricao):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Categoriza este gasto em Portugal: '{descricao}'. Categorias: [Alimentação, Habitação, Transportes, Saúde, Lazer, Estado, Investimentos, Salário, Transferências, Outros]. Responde apenas a palavra."
        response = model.generate_content(prompt)
        return response.text.strip().replace("❓", "")
    except:
        return "Outros"

# --- FUNÇÃO DETETIVE DE EXCEL ---
def ler_excel_inteligente(file):
    # Carrega o excel sem header para analisar a estrutura
    df_raw = pd.read_excel(file, header=None)
    
    # Procura a linha que contém as palavras-chave do ActivoBank ou Cetelem
    header_row = 0
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(val).lower() for val in row.values])
        if 'descrição' in row_str or 'descritivo' in row_str:
            header_row = i
            break
            
    # Re-lê o ficheiro a partir da linha encontrada
    df = pd.read_excel(file, header=header_row)
    return df

# --- INTERFACE ---
st.title("🏦 Dashboard Financeiro Inteligente")

memoria = carregar_memoria()
uploaded_file = st.file_uploader("Upload do Excel", type="xlsx")

if uploaded_file:
    try:
        df_limpo = ler_excel_inteligente(uploaded_file)
        
        # Mapeamento de Colunas
        mapping = {}
        for c in df_limpo.columns:
            c_low = str(c).lower()
            if 'data' in c_low: mapping[c] = 'Data'
            elif 'desc' in c_low: mapping[c] = 'Descricao'
            elif any(x in c_low for x in ['valor', 'importância', 'montante', 'movimento']): 
                # Evitar confundir com 'Data Valor'
                if 'data' not in c_low: mapping[c] = 'Valor'
        
        df = df_limpo.rename(columns=mapping)
        
        # Validação
        if 'Descricao' not in df.columns or 'Valor' not in df.columns:
            st.error(f"Ainda não consegui encontrar as colunas. Colunas lidas: {list(df.columns)}")
            st.write("Amostra dos dados para debug:", df.head(10))
        else:
            # Limpeza de dados
            df = df.dropna(subset=['Descricao', 'Valor'])
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
            
            # --- CATEGORIZAÇÃO ---
            categorias_finais = []
            novos_itens = []
            for desc in df['Descricao']:
                if desc in memoria:
                    categorias_finais.append(memoria[desc])
                else:
                    sugestao = sugerir_categoria_ia(desc)
                    categorias_finais.append(f"❓ {sugestao}")
                    if desc not in novos_itens: novos_itens.append(desc)
            
            df['Categoria'] = categorias_finais

            # --- UI DE ENSINO ---
            if novos_itens:
                with st.expander("🎓 Confirmar Categorias Novas", expanded=True):
                    for i, item in enumerate(novos_itens[:10]):
                        c1, c2 = st.columns([3, 1])
                        sugestao_ia = df[df['Descricao'] == item]['Categoria'].iloc[0].replace("❓ ", "")
                        escolha = c2.selectbox("Cat", ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"], 
                                            index=["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"].index(sugestao_ia) if sugestao_ia in ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"] else 9,
                                            key=f"s_{i}")
                        if c1.button(f"Confirmar {item}", key=f"b_{i}"):
                            memoria[item] = escolha
                            guardar_memoria(memoria)
                            st.rerun()

            # --- DASHBOARD ---
            st.divider()
            despesas = df[df['Valor'] < 0]
            col1, col2, col3 = st.columns(3)
            col1.metric("Despesas", f"{abs(despesas['Valor'].sum()):.2f}€")
            col2.metric("Receitas", f"{df[df['Valor'] > 0]['Valor'].sum():.2f}€")
            col3.metric("Saldo", f"{df['Valor'].sum():.2f}€")

            df_plot = df.copy()
            df_plot['Categoria'] = df_plot['Categoria'].str.replace("❓ ", "")
            st.plotly_chart(px.pie(df_plot[df_plot['Valor'] < 0], values=df_plot[df_plot['Valor'] < 0]['Valor'].abs(), names='Categoria', hole=0.5))
            st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Erro Crítico: {e}")
