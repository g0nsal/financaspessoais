import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

st.set_page_config(page_title="S&G Budget Automator", layout="wide")

# --- 1. O TEU MOTOR DE REGRAS (Fórmulas convertidas) ---
REGRAS_FIXAS = {
    "Portagens": "VIAVERDE|A21|A8|A1|A2|A3|A4|A5|A6|A7|A9|A10",
    "Mercearia": "CONTINENTE|LIDL|PINGO|MINIPRECO|ALDI",
    "Água": "SMAS",
    "Cred. Hab. / Renda": "PRESTACAO", # Atualizei para bater com a tua categoria
    "Despesas Médicas": "MULTICARE|CUF",
    "Restaurantes": "MR PIZZA",
    "Condomínio": "VALOR ACTIVO",
    "Decoração/Obras": "IKEA|CHINA",
    "Farmácia": "FARMACIA|FARMÁCIA|FARMA|WELLS",
    "Internet": "LIGAT",
    "Limpeza": "6175",
    "Telemóveis": "WOO",
    "Seguros": "REAL VIDA|OCIDENTAL",
    "Eletricidade": "LUZBOA",
    "Gás": "LISBOAGAS",
    "Combustível": "AUCHAN ENERGY|SODIMAFRA|PRIO"
}

def classificar_movimento(descricao):
    desc_upper = str(descricao).upper()
    # Tenta primeiro as tuas regras fixas
    for categoria, pattern in REGRAS_FIXAS.items():
        if any(keyword in desc_upper for keyword in pattern.split('|')):
            return categoria
    return None # Se não encontrar, devolve None para a IA tratar

def pedir_ia(descricao):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Categoriza este gasto: '{descricao}'. Escolhe uma: {list(REGRAS_FIXAS.keys()) + ['Outros']}. Responde apenas a categoria."
        return model.generate_content(prompt).text.strip()
    except: return "Outros"

# --- 2. INTERFACE ---
st.title("📊 Automação de Extratos S&G")
st.markdown("Este sistema usa as tuas fórmulas de Excel + IA para processar tudo de uma vez.")

uploaded_file = st.file_uploader("Carrega o extrato (Excel ou CSV)", type=["xlsx", "csv"])

if uploaded_file:
    # Leitura inteligente (salta lixo do topo)
    df_raw = pd.read_excel(uploaded_file, header=None) if ".xlsx" in uploaded_file.name else pd.read_csv(uploaded_file, header=None)
    header_row = 0
    for i, row in df_raw.iterrows():
        if any(x in str(val).lower() for val in row for x in ['descri', 'hist', 'movimento']):
            header_row = i
            break
    
    df = pd.read_excel(uploaded_file, header=header_row) if ".xlsx" in uploaded_file.name else pd.read_csv(uploaded_file, header=header_row)
    
    # Identificar colunas (Data, Descrição, Valor)
    cols = {}
    for c in df.columns:
        cl = str(c).lower()
        if ('data' in cl or 'mov' in cl) and 'valor' not in cl: cols['Data'] = c
        if 'desc' in cl or 'hist' in cl: cols['Desc'] = c
        if any(x in cl for x in ['valor', 'import', 'montant']): cols['Valor'] = c

    if len(cols) >= 3:
        df = df[[cols['Data'], cols['Desc'], cols['Valor']]].copy()
        df.columns = ['Data', 'Descricao', 'Valor']
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
        
        # --- PROCESSAMENTO ---
        # 1. Aplicar Categorias
        df['Categoria'] = df['Descricao'].apply(lambda x: classificar_movimento(x) or pedir_ia(x))
        
        # 2. SUMIF Automático (Agrupado por Categoria)
        resumo = df[df['Valor'] < 0].groupby('Categoria')['Valor'].sum().abs().reset_index()
        resumo.columns = ['Categoria', 'Total Mensal']
        
        # --- OUTPUT PARA COPIAR ---
        st.subheader("📋 Resumo para o teu Excel (SUMIF automático)")
        
        # Formata o texto para colares direto no Excel
        output_text = ""
        mes_ano = pd.to_datetime(df['Data']).iloc[0].strftime('%m-%Y')
        for _, row in resumo.iterrows():
            output_text += f"01-{mes_ano}\tTotal {row['Categoria']}\t{str(row['Total Mensal']).replace('.', ',')}\t{row['Categoria']}\n"
        
        st.text_area("Copia estas linhas e cola na aba 'Expenses' do teu Excel S&G:", value=output_text, height=250)
        
        # Visualização
        st.write("### Detalhe do Processamento")
        st.dataframe(df)
    else:
        st.error("Não consegui detectar as colunas de Data, Descrição e Valor.")import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="S&G Data Formatter", layout="wide")

# --- CATEGORIAS ---
MINHAS_CATEGORIAS = [
    "Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", 
    "Água", "Prendas", "Saídas", "Netflix", "Internet", "Cabeleireiro", 
    "Seguros", "Despesas Médicas", "Farmácia", "Decoração/Obras", 
    "Transportes", "Desporto", "Eq. Eletrónicos", "Manutenção Auto", 
    "Viagens", "Entertenimento", "Estado", "Caridade", "Condomínio", 
    "Investimentos", "Telemóveis", "Pastelaria", "Cartão de Crédito", 
    "Portagens", "Gás", "Eletricidade", "Limpeza", "Salário", "Outros"
]

# --- REGRAS DO TEU EXCEL ---
def aplicar_regras(desc):
    d = str(desc).upper()
    if any(x in d for x in ["VIAVERDE", "A21", "A8", "A1", "A2", "A9"]): return "Portagens"
    if any(x in d for x in ["CONTINENTE", "LIDL", "PINGO", "MINIPRECO", "ALDI"]): return "Mercearia"
    if "SMAS" in d: return "Água"
    if "PRESTACAO" in d: return "Cred. Hab. / Renda"
    if any(x in d for x in ["FARMACIA", "WELLS", "FARMA"]): return "Farmácia"
    if any(x in d for x in ["MULTICARE", "CUF"]): return "Despesas Médicas"
    if "WOO" in d: return "Telemóveis"
    if "LUZBOA" in d: return "Eletricidade"
    if "LISBOAGAS" in d: return "Gás"
    return None

def sugerir_ia(desc):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Categoriza apenas com uma destas palavras: {MINHAS_CATEGORIAS}. Item: '{desc}'"
        return model.generate_content(prompt).text.strip()
    except: return "Outros"

st.title("📑 Formatador S&G (Somado)")

uploaded_file = st.file_uploader("Upload Extrato Excel", type="xlsx")

if uploaded_file:
    try:
        # 1. Tentar ler o Excel de várias formas até encontrar colunas úteis
        df = None
        for skip in range(0, 20):
            temp_df = pd.read_excel(uploaded_file, skiprows=skip)
            cols_norm = [str(c).lower() for c in temp_df.columns]
            # Se encontrar colunas que pareçam Data e Valor, é este!
            if any('data' in c or 'mov' in c for c in cols_norm) and \
               any('valor' in c or 'import' in c or 'montant' in c for c in cols_norm):
                df = temp_df
                break
        
        if df is not None:
            # 2. Mapeamento Manual Forçado
            final_df = pd.DataFrame()
            for c in df.columns:
                c_low = str(c).lower()
                if ('data' in c_low or 'mov' in c_low) and 'Data' not in final_df.columns:
                    final_df['Data'] = df[c]
                if ('desc' in c_low or 'hist' in c_low or 'texto' in c_low) and 'Desc' not in final_df.columns:
                    final_df['Desc'] = df[c]
                if any(x in c_low for x in ['valor', 'import', 'montant']) and 'Valor' not in final_df.columns:
                    final_df['Valor'] = df[c]

            # Limpeza e Datas
            final_df['Data'] = pd.to_datetime(final_df['Data'], errors='coerce')
            final_df['Valor'] = pd.to_numeric(final_df['Valor'], errors='coerce').fillna(0)
            final_df = final_df.dropna(subset=['Desc', 'Data'])

            # 3. Categorizar e Somar
            final_df['Cat'] = final_df['Desc'].apply(lambda x: aplicar_regras(x) or sugerir_ia(x))
            
            # Apenas despesas (negativos) somadas por mês/categoria
            despesas = final_df[final_df['Valor'] < 0].copy()
            despesas['Valor'] = despesas['Valor'].abs()
            despesas['MesAno'] = despesas['Data'].dt.strftime('%m-%Y')
            
            resumo = despesas.groupby(['MesAno', 'Cat'])['Valor'].sum().reset_index()

            # 4. Texto para Copiar
            output = []
            for _, row in resumo.iterrows():
                data_excel = f"01-{row['MesAno']}"
                # Formato: DATA [TAB] DESCRIÇÃO [TAB] VALOR [TAB] CATEGORIA
                linha = f"{data_excel}\tTotal {row['Cat']}\t{str(row['Valor']).replace('.', ',')}\t{row['Cat']}"
                output.append(linha)

            st.text_area("Copia estas linhas para o teu Excel:", value="\n".join(output), height=300)
            st.dataframe(resumo)
        else:
            st.error("Não consegui encontrar as colunas de Data e Valor. O ficheiro está no formato padrão do banco?")

    except Exception as e:
        st.error(f"Erro: {e}")
