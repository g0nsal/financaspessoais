import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

st.set_page_config(page_title="S&G Budget Automator", layout="wide")

# --- 1. MOTOR DE REGRAS (Prioritário) ---
REGRAS_FIXAS = {
    "Portagens": r"VIAVERDE|VIA VERDE|A21|A8|A1|A2|A3|A4|A5|A6|A7|A9|A10",
    "Mercearia": r"CONTINENTE|LIDL|PINGO|MINIPRECO|ALDI|AUCHAN|MERCADONA",
    "Água": r"SMAS|EPAL",
    "Cred. Hab. / Renda": r"PRESTACAO|EMPRESTIMO|CHAB|PAG.PREST",
    "Despesas Médicas": r"MULTICARE|CUF|HOSPITAL|LUSIADAS",
    "Restaurantes": r"MR PIZZA|RESTAURANTE|UBER EATS|GLOVO|MCDONALD",
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
    if not descricao or descricao == 'nan': return None
    desc_upper = str(descricao).upper()
    for categoria, pattern in REGRAS_FIXAS.items():
        if re.search(pattern, desc_upper):
            return categoria
    return None

def pedir_ia(descricao):
    if not descricao or len(descricao) < 3: return "Outros"
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        categorias = list(REGRAS_FIXAS.keys()) + ["Salário", "Pastelaria", "Roupa", "Outros"]
        prompt = f"Categoriza: '{descricao}'. Escolhe uma: {categorias}. Responde apenas o nome."
        return model.generate_content(prompt).text.strip()
    except: return "Outros"

st.title("📊 S&G Budget Automator v4.0")

uploaded_file = st.file_uploader("Upload Excel ActivoBank", type=["xlsx"])

if uploaded_file:
    try:
        # 1. Ler o Excel ignorando os nomes de colunas iniciais
        df_raw = pd.read_excel(uploaded_file, header=None)
        
        # 2. Localizar a linha onde começam os dados
        # Procuramos a linha que tem uma data na primeira coluna
        start_row = 0
        for i, row in df_raw.iterrows():
            val = str(row[0])
            if re.search(r'\d{2}-\d{2}-\d{4}', val): # Procura formato DD-MM-YYYY
                start_row = i
                break
        
        # Criamos o dataframe a partir daí
        df = df_raw.iloc[start_row:].copy()
        
        # 3. MAPEAMENTO FORÇADO (Baseado na estrutura real do ActivoBank)
        # Col 0: Data Mov. | Col 1: Data Valor | Col 2: Descrição | Col 3: Montante
        df_final = pd.DataFrame()
        df_final['Data'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
        df_final['Descricao'] = df.iloc[:, 2].astype(str) # Coluna C
        
        # O Montante no ActivoBank costuma estar na Coluna D (index 3) ou E (index 4)
        # Vamos tentar encontrar a coluna que tem a maioria de valores numéricos
        col_valor_idx = 3
        for idx in [3, 4, 5]:
            nums = pd.to_numeric(df.iloc[:, idx], errors='coerce').dropna()
            if not nums.empty:
                col_valor_idx = idx
                break
        
        df_final['Valor'] = pd.to_numeric(df.iloc[:, col_valor_idx], errors='coerce').fillna(0)
        
        # Limpeza
        df_final = df_final.dropna(subset=['Data'])
        df_final = df_final[df_final['Descricao'] != 'nan']

        # 4. Classificar
        st.info(f"A processar {len(df_final)} movimentos...")
        df_final['Categoria'] = df_final['Descricao'].apply(lambda x: classificar_movimento(x) or pedir_ia(x))
        
        # 5. Agrupar (SUMIF) - Apenas despesas (negativas)
        despesas = df_final[df_final['Valor'] < 0].copy()
        despesas['Valor'] = despesas['Valor'].abs()
        despesas['Mes_Ano'] = despesas['Data'].dt.strftime('%m-%Y')
        
        resumo = despesas.groupby(['Mes_Ano', 'Categoria'])['Valor'].sum().reset_index()

        # 6. OUTPUT PARA EXCEL
        st.subheader("📋 Output para o Excel S&G")
        output_rows = []
        for _, row in resumo.iterrows():
            data_excel = f"01-{row['Mes_Ano']}"
            valor_pt = f"{row['Valor']:.2f}".replace('.', ',')
            output_rows.append(f"{data_excel}\tTotal {row['Categoria']}\t{valor_pt}\t{row['Categoria']}")
        
        if output_rows:
            st.text_area("Copia e cola no Excel S&G:", value="\n".join(output_rows), height=300)
            st.write("### Verificação de dados:")
            st.dataframe(df_final[['Data', 'Descricao', 'Valor', 'Categoria']])
        else:
            st.warning("Não foram encontradas despesas negativas. O valor está na coluna correta?")
            st.write("Amostra das colunas lidas:", df.head())

    except Exception as e:
        st.error(f"Erro Crítico: {e}")
