import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

st.set_page_config(page_title="S&G Budget Automator", layout="wide")

# --- 1. REGRAS DE OURO (IGUAL AO TEU EXCEL) ---
REGRAS_FIXAS = {
    "Portagens": r"VIAVERDE|VIA VERDE|A21|A8|A1|A2|A3|A4|A5|A6|A7|A9|A10",
    "Mercearia": r"CONTINENTE|LIDL|PINGO|MINIPRECO|ALDI|AUCHAN|MERCADONA",
    "Água": r"SMAS|EPAL",
    "Cred. Hab. / Renda": r"PRESTACAO|EMPRESTIMO|CHAB",
    "Despesas Médicas": r"MULTICARE|CUF|HOSPITAL|LUSIADAS",
    "Restaurantes": r"MR PIZZA|RESTAURANTE|UBER EATS|GLOVO",
    "Condomínio": r"VALOR ACTIVO|CONDOMINIO",
    "Decoração/Obras": r"IKEA|CHINA|LEROY|AKI",
    "Farmácia": r"FARMACIA|FARMÁCIA|FARMA|WELLS",
    "Internet": r"LIGAT|NOS|MEO|VODAFONE",
    "Limpeza": r"6175",
    "Telemóveis": r"WOO|DIGI",
    "Seguros": r"REAL VIDA|OCIDENTAL|FIDELIDADE",
    "Eletricidade": r"LUZBOA|EDP|IBERDROLA|ENDESA",
    "Gás": r"LISBOAGAS|GALP",
    "Combustível": r"AUCHAN ENERGY|SODIMAFRA|PRIO|REPSOL|BP|GALP"
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
        prompt = f"Categoriza: '{descricao}'. Escolhe uma: {list(REGRAS_FIXAS.keys()) + ['Outros', 'Pastelaria', 'Saídas', 'Roupa']}. Responde apenas o nome."
        return model.generate_content(prompt).text.strip()
    except: return "Outros"

st.title("📊 S&G Formatter v2.0")

uploaded_file = st.file_uploader("Carrega o Excel", type=["xlsx"])

if uploaded_file:
    try:
        # Lemos o Excel
        df_raw = pd.read_excel(uploaded_file, header=None)
        
        # 1. Tentar encontrar a linha de cabeçalho real
        header_row = 0
        for i, row in df_raw.iterrows():
            row_str = " ".join([str(x).lower() for x in row if pd.notnull(x)])
            if any(k in row_str for k in ['descri', 'hist', 'movimento', 'valor']):
                header_row = i
                break
        
        # Recarregar com o cabeçalho detetado
        df = pd.read_excel(uploaded_file, header=header_row)
        st.write("🔍 Colunas detetadas:", list(df.columns))

        # 2. Mapeamento Inteligente
        col_data, col_desc, col_valor = None, None, None
        
        for col in df.columns:
            c_low = str(col).lower()
            if ('data' in c_low or 'mov' in c_low) and 'valor' not in c_low: col_data = col
            if 'desc' in c_low or 'hist' in c_low or 'texto' in c_low: col_desc = col
            if any(x in c_low for x in ['valor', 'import', 'montant', 'débito', 'debito']): col_valor = col

        # Fallback se falhar mapeamento por nome
        if not col_data: col_data = df.columns[0]
        if not col_desc: col_desc = df.columns[1]
        if not col_valor: col_valor = df.columns[2] if len(df.columns) > 2 else df.columns[-1]

        # 3. Processamento
        df_clean = pd.DataFrame()
        df_clean['Data'] = pd.to_datetime(df[col_data], errors='coerce')
        df_clean['Descricao'] = df[col_desc].astype(str)
        df_clean['Valor'] = pd.to_numeric(df[col_valor], errors='coerce').fillna(0)
        
        df_clean = df_clean.dropna(subset=['Data']).copy()
        
        # Aplicar Regras + IA
        df_clean['Categoria'] = df_clean['Descricao'].apply(lambda x: classificar_movimento(x) or pedir_ia(x))
        
        # 4. Agrupar por Categoria e Mês
        # Filtramos despesas (tudo o que for negativo ou, se for tudo positivo, assumimos despesa)
        despesas = df_clean[df_clean['Valor'] != 0].copy()
        despesas['Valor'] = despesas['Valor'].abs()
        despesas['Mes_Ano'] = despesas['Data'].dt.strftime('%m-%Y')
        
        resumo = despesas.groupby(['Mes_Ano', 'Categoria'])['Valor'].sum().reset_index()

        # 5. Output Formatado
        st.subheader("📋 Output para o Excel S&G")
        output_text = ""
        for _, row in resumo.iterrows():
            data_out = f"01-{row['Mes_Ano']}"
            valor_out = f"{row['Valor']:.2f}".replace('.', ',')
            output_text += f"{data_out}\tTotal {row['Categoria']}\t{valor_out}\t{row['Categoria']}\n"
        
        if output_text:
            st.text_area("Copia e cola no Excel S&G:", value=output_text, height=350)
            st.write("### Detalhe das somas:")
            st.dataframe(resumo)
        else:
            st.warning("Não foram processados dados. Verifica se as colunas estão corretas acima.")

    except Exception as e:
        st.error(f"Erro: {e}")
