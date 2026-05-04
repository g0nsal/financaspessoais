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

# --- PROCESSO DE LIMPEZA ROBUSTO ---
def processar_extrato(file):
    # 1. Ler tudo para encontrar o cabeçalho real
    df_raw = pd.read_excel(file, header=None)
    
    header_row = 0
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(val).lower() for val in row.values if pd.notnull(val)])
        if 'descrição' in row_str or 'descritivo' in row_str or 'movimento' in row_str:
            header_row = i
            break
            
    # 2. Re-ler com o cabeçalho correto
    df = pd.read_excel(file, header=header_row)
    
    # 3. Eliminar colunas "Unnamed" (lixo de formatação do Excel)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    # 4. Mapear colunas essenciais
    mapping = {}
    for c in df.columns:
        c_low = str(c).lower()
        if 'data' in c_low and 'valor' not in c_low: mapping[c] = 'Data'
        elif 'desc' in c_low: mapping[c] = 'Descricao'
        elif any(x in c_low for x in ['valor', 'importância', 'montante']): mapping[c] = 'Valor'
    
    df = df.rename(columns=mapping)
    
    # 5. Filtrar linhas de ruído (Saldos, cabeçalhos repetidos, etc)
    palavras_ruido = ['saldo anterior', 'histórico de conta', 'número de conta', 'extrato de']
    if 'Descricao' in df.columns:
        mask = df['Descricao'].astype(str).lower().apply(lambda x: not any(p in x for p in palavras_ruido))
        df = df[mask]
    
    return df

# --- INTERFACE ---
st.title("🏦 Gestão Financeira Familiar")

memoria = carregar_memoria()
uploaded_file = st.file_uploader("Siga com o upload do seu Excel (.xlsx)", type="xlsx")

if uploaded_file:
    try:
        df = processar_extrato(uploaded_file)
        
        if 'Descricao' not in df.columns or 'Valor' not in df.columns:
            st.error("Não detetei as colunas de Descrição/Valor. Tente exportar o Excel novamente.")
            st.write("Colunas detetadas:", list(df.columns))
        else:
            df = df.dropna(subset=['Descricao', 'Valor'])
            # Limpeza de valores (tratar 1.200,50 como 1200.50)
            if df['Valor'].dtype == object:
                df['Valor'] = df['Valor'].astype(str).str.replace('.', '').str.replace(',', '.').str.extract('([-+]?\d*\.?\d+)')[0]
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)

            # Categorização
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

            # UI de Ensino
            if novos_itens:
                with st.expander("🎓 Ensinar novas categorias", expanded=True):
                    for i, item in enumerate(novos_itens[:10]):
                        c1, c2 = st.columns([3, 1])
                        sugestao_ia = df[df['Descricao'] == item]['Categoria'].iloc[0].replace("❓ ", "")
                        escolha = c2.selectbox("Cat", ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"], 
                                            index=["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"].index(sugestao_ia) if sugestao_ia in ["Alimentação", "Habitação", "Transportes", "Saúde", "Lazer", "Estado", "Investimentos", "Salário", "Transferências", "Outros"] else 9,
                                            key=f"item_{i}")
                        if c1.button(f"Confirmar {item}", key=f"btn_{i}"):
                            memoria[item] = escolha
                            guardar_memoria(memoria)
                            st.rerun()

            # Dashboard
            st.divider()
            despesas = df[df['Valor'] < 0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Despesas", f"{abs(despesas['Valor'].sum()):.2f}€")
            c2.metric("Receitas", f"{df[df['Valor'] > 0]['Valor'].sum():.2f}€")
            c3.metric("Saldo", f"{df['Valor'].sum():.2f}€")

            # Gráfico Interativo
            df_plot = df.copy()
            df_plot['Categoria'] = df_plot['Categoria'].str.replace("❓ ", "")
            fig = px.pie(df_plot[df_plot['Valor'] < 0], values=df_plot[df_plot['Valor'] < 0]['Valor'].abs(), names='Categoria', hole=0.5)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df[['Data', 'Descricao', 'Categoria', 'Valor']], use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao processar ficheiro: {e}")
