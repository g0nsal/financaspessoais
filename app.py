import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import json
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Financeira Gonsalo", layout="wide")

# Ficheiro de Memória
MEMORY_FILE = "memoria_categorias.json"

def carregar_memoria():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def guardar_memoria(memoria):
    with open(MEMORY_FILE, "w") as f: json.dump(memoria, f)

# --- IA COM FALLBACK ---
def sugerir_categoria_ia(descricao):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Categoriza este gasto em Portugal: '{descricao}'. Categorias: [Alimentação, Habitação, Transportes, Saúde, Lazer, Estado, Investimentos, Salário, Transferências, Outros]. Responde apenas a palavra."
        response = model.generate_content(prompt)
        return response.text.strip().replace("❓", "")
    except:
        return "Outros"

# --- INTERFACE ---
st.title("🏦 Dashboard Financeiro Inteligente")

memoria = carregar_memoria()
uploaded_file = st.file_uploader("Upload do Excel (ActivoBank, Cetelem, etc.)", type="xlsx")

if uploaded_file:
    try:
        # Tenta ler ActivoBank (header na linha 8) ou padrão
        df_test = pd.read_excel(uploaded_file)
        if len(df_test.columns) < 3: # Provavelmente falhou o header
            df_raw = pd.read_excel(uploaded_file, header=7)
        else:
            df_raw = df_test

        # Mapeamento Inteligente de Colunas (Case Insensitive)
        cols_atuais = df_raw.columns.tolist()
        mapping = {}
        
        for c in cols_atuais:
            c_low = str(c).lower()
            if 'data' in c_low: mapping[c] = 'Data'
            elif 'desc' in c_low: mapping[c] = 'Descricao'
            elif any(x in c_low for x in ['valor', 'importância', 'montante']): mapping[c] = 'Valor'
        
        df = df_raw.rename(columns=mapping)
        
        # Validar se temos as colunas mínimas
        colunas_necessarias = ['Descricao', 'Valor']
        if not all(c in df.columns for c in colunas_necessarias):
            st.error(f"Não encontrei colunas de Descrição ou Valor. Colunas detetadas: {cols_atuais}")
        else:
            # Limpeza
            df = df.dropna(subset=['Descricao', 'Valor'])
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
            if 'Data' not in df.columns: df['Data'] = "N/D"

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

            # --- ENSINAR (UI) ---
            if novos_itens:
                with st.expander("🎓 Ensinar Novas Categorias", expanded=True):
                    st.info(f"Encontrei {len(novos_itens)} descrições novas. Escolha a categoria correta:")
                    for i, item in enumerate(novos_itens[:15]): # Lote de 15 por vez
                        c1, c2 = st.columns([3, 1])
                        sugestao_limpa = df[df['Descricao'] == item]['Categoria'].iloc[0].replace("❓ ", "")
                        
                        escolha = c2.selectbox(f"Categoria", 
                                            ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"],
                                            index=["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"].index(sugestao_limpa) if sugestao_limpa in ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"] else 9,
                                            key=f"sel_{i}")
                        
                        if c1.button(f"Confirmar: {item}", key=f"btn_{i}"):
                            memoria[item] = escolha
                            guardar_memoria(memoria)
                            st.rerun()

            # --- DASHBOARD ---
            st.divider()
            despesas = df[df['Valor'] < 0]
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Despesas", f"{abs(despesas['Valor'].sum()):.2f}€")
            col_m2.metric("Total Receitas", f"{df[df['Valor'] > 0]['Valor'].sum():.2f}€")
            col_m3.metric("Saldo", f"{df['Valor'].sum():.2f}€")

            tab1, tab2 = st.tabs(["📊 Gráficos", "📑 Dados"])
            
            with tab1:
                df_plot = df.copy()
                df_plot['Categoria'] = df_plot['Categoria'].str.replace("❓ ", "")
                fig = px.pie(df_plot[df_plot['Valor'] < 0], values=df_plot[df_plot['Valor'] < 0]['Valor'].abs(), 
                            names='Categoria', hole=0.5, title="Onde gastaste dinheiro")
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
