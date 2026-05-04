import streamlit as st
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
