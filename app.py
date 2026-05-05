import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

st.set_page_config(page_title="S&G Budget Automator", layout="wide")

# --- 1. TEU MOTOR DE REGRAS (Fórmulas do Google Sheets) ---
REGRAS_FIXAS = {
    "Portagens": r"VIAVERDE|A21|A8|A1|A2|A3|A4|A5|A6|A7|A9|A10",
    "Mercearia": r"CONTINENTE|LIDL|PINGO|MINIPRECO|ALDI",
    "Água": r"SMAS",
    "Cred. Hab. / Renda": r"PRESTACAO",
    "Despesas Médicas": r"MULTICARE|CUF",
    "Restaurantes": r"MR PIZZA",
    "Condomínio": r"VALOR ACTIVO",
    "Decoração/Obras": r"IKEA|CHINA",
    "Farmácia": r"FARMACIA|FARMÁCIA|FARMA|WELLS",
    "Internet": r"LIGAT",
    "Limpeza": r"6175",
    "Telemóveis": r"WOO",
    "Seguros": r"REAL VIDA|OCIDENTAL",
    "Eletricidade": r"LUZBOA",
    "Gás": r"LISBOAGAS",
    "Combustível": r"AUCHAN ENERGY|SODIMAFRA|PRIO"
}

def classificar_movimento(descricao):
    desc_upper = str(descricao).upper()
    for categoria, pattern in REGRAS_FIXAS.items():
        if re.search(pattern, desc_upper):
            return categoria
    return None

def pedir_ia(descricao):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        categorias_lista = list(REGRAS_FIXAS.keys()) + ["Outros", "Pastelaria", "Saídas", "Roupa"]
        prompt = f"Categoriza este gasto: '{descricao}'. Escolhe uma: {categorias_lista}. Responde apenas a categoria."
        return model.generate_content(prompt).text.strip()
    except:
        return "Outros"

# --- 2. INTERFACE ---
st.title("📊 Automação S&G (Regras + SUMIF)")

uploaded_file = st.file_uploader("Carrega o extrato (Excel ou CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # Leitura inicial
        if uploaded_file.name.endswith('.xlsx'):
            df_raw = pd.read_excel(uploaded_file, header=None)
        else:
            df_raw = pd.read_csv(uploaded_file, header=None)

        # Encontrar cabeçalho
        header_row = 0
        for i, row in df_raw.iterrows():
            row_str = " ".join([str(val).lower() for val in row if pd.notnull(val)])
            if any(x in row_str for x in ['descri', 'hist', 'movimento']):
                header_row = i
                break
        
        # Recarregar com o cabeçalho certo
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file, header=header_row)
        else:
            df = pd.read_csv(uploaded_file, header=header_row)

        # Mapear colunas
        cols = {}
        for c in df.columns:
            cl = str(c).lower()
            if ('data' in cl or 'mov' in cl) and 'valor' not in cl and 'Data' not in cols: cols['Data'] = c
            if ('desc' in cl or 'hist' in cl) and 'Desc' not in cols: cols['Desc'] = c
            if any(x in cl for x in ['valor', 'import', 'montant']) and 'Data' not in cl: cols['Valor'] = c

        if len(cols) >= 3:
            df = df[[cols['Data'], cols['Desc'], cols['Valor']]].copy()
            df.columns = ['Data', 'Descricao', 'Valor']
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

            # 1. Classificar
            df['Categoria'] = df['Descricao'].apply(lambda x: classificar_movimento(x) or pedir_ia(x))
            
            # 2. Agrupar (SUMIF) por Categoria e Mês
            df_despesas = df[df['Valor'] < 0].copy()
            df_despesas['Valor'] = df_despesas['Valor'].abs()
            df_despesas['Mes_Ano'] = df_despesas['Data'].dt.strftime('%m-%Y')
            
            resumo = df_despesas.groupby(['Mes_Ano', 'Categoria'])['Valor'].sum().reset_index()

            # 3. Gerar Output para copiar
            st.subheader("📋 Dados Agrupados para o Excel")
            output_text = ""
            for _, row in resumo.iterrows():
                # Formato: Data | Descrição | Valor | Categoria (separado por TAB)
                data_excel = f"01-{row['Mes_Ano']}"
                valor_pt = f"{row['Valor']:.2f}".replace('.', ',')
                output_text += f"{data_excel}\tTotal {row['Categoria']}\t{valor_pt}\t{row['Categoria']}\n"
            
            st.text_area("Copia estas linhas e cola no Excel S&G:", value=output_text, height=250)
            st.dataframe(resumo)
        else:
            st.error("Não detetei as colunas necessárias (Data, Descrição, Valor).")
            
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
