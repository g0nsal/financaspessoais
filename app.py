import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="S&G Data Formatter", layout="wide")

# --- CATEGORIAS REAIS ---
MINHAS_CATEGORIAS = [
    "Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", 
    "Água", "Prendas", "Saídas", "Netflix", "Internet", "Cabeleireiro", 
    "Seguros", "Despesas Médicas", "Farmácia", "Decoração/Obras", 
    "Transportes", "Desporto", "Eq. Eletrónicos", "Manutenção Auto", 
    "Viagens", "Entertenimento", "Estado", "Caridade", "Condomínio", 
    "Investimentos", "Telemóveis", "Pastelaria", "Cartão de Crédito", 
    "Portagens", "Gás", "Eletricidade", "Limpeza", "Salário", "Outros"
]

# --- REGRAS EXTRAÍDAS DA TUA FÓRMULA ---
def categorizar_com_regras(desc):
    d = str(desc).upper()
    if any(x in d for x in ["VIAVERDE", "A21", "A8", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A9", "A10"]): return "Portagens"
    if any(x in d for x in ["CONTINENTE", "LIDL", "PINGO", "MINIPRECO", "ALDI"]): return "Mercearia"
    if "SMAS" in d: return "Água"
    if "PRESTACAO" in d: return "Cred. Hab. / Renda"
    if any(x in d for x in ["MULTICARE", "CUF"]): return "Despesas Médicas"
    if "MR PIZZA" in d: return "Restaurantes"
    if "VALOR ACTIVO" in d: return "Condomínio"
    if any(x in d for x in ["IKEA", "CHINA"]): return "Decoração/Obras"
    if any(x in d for x in ["FARMACIA", "FARMÁCIA", "WELLS", "FARMA"]): return "Farmácia"
    if "LIGAT" in d: return "Internet"
    if "6175" in d: return "Limpeza"
    if "WOO" in d: return "Telemóveis"
    if any(x in d for x in ["REAL VIDA", "OCIDENTAL"]): return "Seguros"
    if "LUZBOA" in d: return "Eletricidade"
    if "LISBOAGAS" in d: return "Gás"
    if any(x in d for x in ["AUCHAN ENERGY", "SODIMAFRA", "PRIO"]): return "Combustível"
    return None

def sugerir_ia(desc):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Categoriza: '{desc}'. Categorias: {MINHAS_CATEGORIAS}. Responde apenas com o nome da categoria."
        return model.generate_content(prompt).text.strip()
    except: return "Outros"

st.title("📑 Formatador para Excel S&G")

uploaded_file = st.file_uploader("Upload do Extrato", type="xlsx")

if uploaded_file:
    try:
        # Lógica robusta de leitura
        df_raw = pd.read_excel(uploaded_file, header=None)
        header_idx = 0
        for i, row in df_raw.iterrows():
            if any(x in str(val).lower() for val in row for x in ['descri', 'hist']):
                header_idx = i
                break
        
        df = pd.read_excel(uploaded_file, header=header_idx)
        
        # Selecionar colunas por proximidade de nome
        cols = {}
        for c in df.columns:
            cl = str(c).lower()
            if 'data' in cl and 'valor' not in cl: cols['Data'] = c
            if 'desc' in cl or 'hist' in cl: cols['Desc'] = c
            if any(x in cl for x in ['valor', 'import', 'montant']): cols['Valor'] = c

        df = df[[cols['Data'], cols['Desc'], cols['Valor']]].copy()
        df.columns = ['Data', 'Descricao', 'Valor']
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)

        # Processar Categorias
        df['Categoria'] = df['Descricao'].apply(lambda x: categorizar_com_regras(x) or sugerir_ia(x))
        
        # --- PREPARAÇÃO DO OUTPUT ---
        # Apenas despesas negativas
        despesas = df[df['Valor'] < 0].copy()
        despesas['Valor'] = despesas['Valor'].abs()
        
        # Agrupar por Mês e Categoria
        despesas['MesAno'] = despesas['Data'].dt.strftime('%m-%Y')
        resumo = despesas.groupby(['MesAno', 'Categoria'])['Valor'].sum().reset_index()

        # Formatação para o Excel (Data | Descrição | Valor | Categoria)
        output_list = []
        for _, row in resumo.iterrows():
            # Data no formato do teu Excel (MM-DD-YYYY ou DD-MM-YYYY conforme o teu local)
            data_str = f"01-{row['MesAno']}" 
            # String com TAB (\t) para o Excel separar em colunas no Paste
            linha = f"{data_str}\tTotal {row['Categoria']}\t{row['Valor']:.2f}\t{row['Categoria']}"
            output_list.append(linha)

        st.subheader("📋 Dados Agrupados para o Excel")
        if output_list:
            final_text = "\n".join(output_list)
            st.text_area("Clica aqui, faz Ctrl+A e Ctrl+C, depois cola no Excel:", value=final_text, height=300)
            
            st.write("### Pré-visualização da soma:")
            st.dataframe(resumo)
        else:
            st.warning("Não foram encontradas despesas (valores negativos) no ficheiro.")

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")
