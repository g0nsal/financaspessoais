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
        "Categorias": ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Seguros", "Outros"], 
        "Dicionario": {}
    }

def guardar_memoria(memoria):
    with open(MEMORY_FILE, "w") as f: json.dump(memoria, f)

def sugerir_categoria_ia(descricao, categorias_disponiveis):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Categoriza este gasto bancário em Portugal: '{descricao}'. Categorias permitidas: {categorias_disponiveis}. Responde apenas com a palavra exata."
        response = model.generate_content(prompt)
        sugestao = response.text.strip()
        return sugestao if sugestao in categorias_disponiveis else "Outros"
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
    # Lê os dados a partir da linha detetada
    df = pd.read_excel(file, header=header_row)
    
    # Limpeza de colunas duplicadas de forma robusta
    new_cols = []
    for i, col in enumerate(df.columns):
        col_name = str(col).strip()
        if col_name in new_cols or not col_name:
            new_cols.append(f"{col_name}_{i}")
        else:
            new_cols.append(col_name)
    df.columns = new_cols
    return df

# --- INTERFACE ---
st.title("🏦 Controlo Financeiro Familiar")

dados_memoria = carregar_memoria()
if "Categorias" not in dados_memoria: dados_memoria["Categorias"] = ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Seguros", "Outros"]
if "Dicionario" not in dados_memoria: dados_memoria["Dicionario"] = {}

uploaded_file = st.file_uploader("Upload do Excel", type="xlsx")

if uploaded_file:
    try:
        df_full = ler_excel_inteligente(uploaded_file)
        
        # Identificar colunas por conteúdo (evita erro de nomes)
        col_data, col_desc, col_valor = None, None, None
        
        for c in df_full.columns:
            c_low = c.lower()
            if 'data mov' in c_low and not col_data: col_data = c
            elif 'data' in c_low and 'valor' not in c_low and not col_data: col_data = c
            elif ('desc' in c_low or 'histórico' in c_low) and not col_desc: col_desc = c
            elif any(x in c_low for x in ['valor', 'importância', 'montante']) and 'data' not in c_low and not col_valor: col_valor = c

        if not col_desc or not col_valor:
            st.error(f"Não detetei as colunas. Encontradas: Desc={col_desc}, Valor={col_valor}")
            st.write("Colunas disponíveis:", list(df_full.columns))
        else:
            # Criar DataFrame de trabalho limpo
            df = df_full[[col_data or df_full.columns[0], col_desc, col_valor]].copy()
            df.columns = ['Data', 'Descricao', 'Valor']
            
            df = df.dropna(subset=['Descricao', 'Valor'])
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)

            # --- PROCESSAMENTO ---
            categorias_finais = []
            novos_itens = []
            
            # Usar set para descrições únicas para poupar API
            descricoes_unicas = df['Descricao'].unique()
            map_temp = {}

            for desc in descricoes_unicas:
                if desc in dados_memoria["Dicionario"]:
                    map_temp[desc] = dados_memoria["Dicionario"][desc]
                else:
                    sugestao = sugerir_categoria_ia(desc, dados_memoria["Categorias"])
                    map_temp[desc] = f"❓ {sugestao}"
                    novos_itens.append(desc)

            df['Categoria'] = df['Descricao'].map(map_temp)

            # --- PAINEL DE ENSINO ---
            if novos_itens:
                with st.expander("🎓 Validar Novas Categorias", expanded=True):
                    # Adicionar Categoria
                    c_n1, c_n2 = st.columns([3,1])
                    nova = c_n1.text_input("Nova Categoria:")
                    if c_n2.button("Adicionar") and nova:
                        if nova not in dados_memoria["Categorias"]:
                            dados_memoria["Categorias"].append(nova)
                            guardar_memoria(dados_memoria)
                            st.rerun()

                    st.divider()
                    for i, item in enumerate(novos_itens[:10]):
                        col_a, col_b, col_c = st.columns([3, 2, 1])
                        sug_ia = map_temp[item].replace("❓ ", "")
                        
                        lista = dados_memoria["Categorias"]
                        d_idx = lista.index(sug_ia) if sug_ia in lista else 0
                        
                        col_a.write(f"**{item}**")
                        escolha = col_b.selectbox("Cat", lista, index=d_idx, key=f"s_{i}", label_visibility="collapsed")
                        if col_c.button("✓", key=f"b_{i}"):
                            dados_memoria["Dicionario"][item] = escolha
                            guardar_memoria(dados_memoria)
                            st.rerun()

            # --- DASHBOARD ---
            st.divider()
            despesas = df[df['Valor'] < 0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Gastos", f"{abs(despesas['Valor'].sum()):.2f}€")
            c2.metric("Entradas", f"{df[df['Valor'] > 0]['Valor'].sum():.2f}€")
            c3.metric("Saldo", f"{df['Valor'].sum():.2f}€")

            df_plot = df.copy()
            df_plot['Categoria'] = df_plot['Categoria'].str.replace("❓ ", "")
            st.plotly_chart(px.pie(df_plot[df_plot['Valor'] < 0], values=df_plot[df_plot['Valor'] < 0]['Valor'].abs(), names='Categoria', hole=0.5))
            st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")
