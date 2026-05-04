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
    return {
        "Categorias": ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"], 
        "Dicionario": {}
    }

def guardar_memoria(memoria):
    with open(MEMORY_FILE, "w") as f: json.dump(memoria, f)

def sugerir_categoria_ia(descricao, categorias_disponiveis):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Categoriza este gasto bancário em Portugal: '{descricao}'. As categorias permitidas são: {categorias_disponiveis}. Responde apenas com a palavra exata da categoria que melhor se aplica."
        response = model.generate_content(prompt)
        sugestao = response.text.strip()
        # Garantir que a IA não inventa categorias fora da lista
        if sugestao in categorias_disponiveis:
            return sugestao
        return "Outros"
    except:
        return "Outros"

def ler_excel_inteligente(file):
    df_raw = pd.read_excel(file, header=None)
    header_row = 0
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(val).lower() for val in row.values if pd.notnull(val)])
        if 'descrição' in row_str or 'descritivo' in row_str:
            header_row = i
            break
    df = pd.read_excel(file, header=header_row)
    # Resolver colunas duplicadas (ex: duas colunas 'Data')
    cols = []
    count = {}
    for column in df.columns:
        if column not in count:
            cols.append(column)
            count[column] = 1
        else:
            cols.append(f"{column}_{count[column]}")
            count[column] += 1
    df.columns = cols
    return df

# --- INTERFACE ---
st.title("🏦 Controlo Financeiro - Memória Inteligente")

dados_memoria = carregar_memoria()
# Garantir estrutura mínima
if "Categorias" not in dados_memoria: dados_memoria["Categorias"] = ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"]
if "Dicionario" not in dados_memoria: dados_memoria["Dicionario"] = {}

uploaded_file = st.file_uploader("Carrega o teu Excel (.xlsx)", type="xlsx")

if uploaded_file:
    try:
        df_limpo = ler_excel_inteligente(uploaded_file)
        
        mapping = {}
        for c in df_limpo.columns:
            c_low = str(c).lower()
            if 'data mov' in c_low or ('data' in c_low and 'valor' not in c_low and 'data' not in mapping.values()): mapping[c] = 'Data'
            elif 'desc' in c_low: mapping[c] = 'Descricao'
            elif any(x in c_low for x in ['valor', 'importância', 'montante']): mapping[c] = 'Valor'
        
        df = df_limpo.rename(columns=mapping)
        # Manter apenas o essencial para evitar erros de colunas duplicadas
        df = df[['Data', 'Descricao', 'Valor']].copy()
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)

        # --- PROCESSAMENTO DE CATEGORIAS ---
        categorias_finais = []
        novos_itens = []

        for desc in df['Descricao']:
            if desc in dados_memoria["Dicionario"]:
                categorias_finais.append(dados_memoria["Dicionario"][desc])
            else:
                sugestao = sugerir_categoria_ia(desc, dados_memoria["Categorias"])
                categorias_finais.append(f"❓ {sugestao}")
                if desc not in novos_itens: novos_itens.append(desc)
        
        df['Categoria'] = categorias_finais

        # --- PAINEL DE ENSINO E CORREÇÃO ---
        if novos_itens:
            with st.expander("🎓 Movimentos Novos (Validar ou Corrigir)", expanded=True):
                st.write("A IA sugeriu estas categorias. Podes alterar antes de confirmar.")
                
                # Opção para criar nova categoria
                col_n1, col_n2 = st.columns([3, 1])
                nova_cat = col_n1.text_input("Criar nova categoria (ex: Seguros, Animais):")
                if col_n2.button("Adicionar"):
                    if nova_cat and nova_cat not in dados_memoria["Categorias"]:
                        dados_memoria["Categorias"].append(nova_cat)
                        guardar_memoria(dados_memoria)
                        st.rerun()

                st.divider()

                # Lista de novos movimentos para validar
                for i, item in enumerate(novos_itens[:15]): # Lote de 15 para performance
                    c1, c2, c3 = st.columns([3, 2, 1])
                    
                    sugestao_ia = df[df['Descricao'] == item]['Categoria'].iloc[0].replace("❓ ", "")
                    
                    # Se a categoria sugerida não existir (erro da IA), usa 'Outros'
                    lista_cats = dados_memoria["Categorias"]
                    default_idx = lista_cats.index(sugestao_ia) if sugestao_ia in lista_cats else lista_cats.index("Outros")
                    
                    c1.markdown(f"**{item}**")
                    escolha = c2.selectbox(f"Validar categoria para {i}", lista_cats, index=default_idx, key=f"sel_{i}", label_visibility="collapsed")
                    
                    if c3.button("✓", key=f"btn_{i}"):
                        dados_memoria["Dicionario"][item] = escolha
                        guardar_memoria(dados_memoria)
                        st.rerun()

        # --- DASHBOARD ---
        st.divider()
        despesas = df[df['Valor'] < 0]
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Gastos", f"{abs(despesas['Valor'].sum()):.2f}€")
        col_m2.metric("Total Entradas", f"{df[df['Valor'] > 0]['Valor'].sum():.2f}€")
        col_m3.metric("Saldo do Mês", f"{df['Valor'].sum():.2f}€")

        # Gráfico e Tabela
        tab1, tab2 = st.tabs(["📊 Distribuição", "📝 Lista Completa"])
        
        with tab1:
            df_plot = df.copy()
            df_plot['Categoria'] = df_plot['Categoria'].str.replace("❓ ", "")
            fig = px.pie(df_plot[df_plot['Valor'] < 0], values=df_plot[df_plot['Valor'] < 0]['Valor'].abs(), names='Categoria', hole=0.5)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")
