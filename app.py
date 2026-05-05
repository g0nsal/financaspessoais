import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

st.set_page_config(page_title="S&G Budget Automator", layout="wide")

# --- 1. TEU MOTOR DE REGRAS (O teu "REGEX" do Google Sheets) ---
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
        prompt = f"Categoriza este gasto: '{descricao}'. Escolhe uma destas categorias: {categorias_lista}. Responde apenas o nome da categoria."
        return model.generate_content(prompt).text.strip()
    except:
        return "Outros"

st.title("📊 Automação S&G (Versão ActivoBank)")

uploaded_file = st.file_uploader("Carrega o extrato Excel", type=["xlsx"])

if uploaded_file:
    try:
        # Lemos o Excel ignorando nomes de colunas, apenas os valores brutos
        df_raw = pd.read_excel(uploaded_file, header=None)
        
        # 1. Procurar a linha onde os dados começam (contendo uma data ou palavra chave)
        start_row = 0
        for i, row in df_raw.iterrows():
            row_str = " ".join([str(x).lower() for x in row if pd.notnull(x)])
            if any(k in row_str for k in ['descri', 'hist', 'movimento', 'data']):
                start_row = i + 1
                break
        
        # Cortamos o "lixo" do topo
        df = df_raw.iloc[start_row:].copy()
        
        # 2. MAPEAMENTO POR POSIÇÃO (Atalho para não falhar nomes)
        # Normalmente: Col 0 = Data, Col 1 = Descrição, Col 2 ou 3 = Valor
        df_clean = pd.DataFrame()
        df_clean['Data'] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
        df_clean['Descricao'] = df.iloc[:, 1].astype(str)
        
        # O Valor pode estar na coluna 2 ou 3 (depende se há coluna de 'Data Valor')
        # Vamos tentar converter ambas e ver qual tem números
        v1 = pd.to_numeric(df.iloc[:, 2], errors='coerce')
        v2 = pd.to_numeric(df.iloc[:, 3], errors='coerce')
        df_clean['Valor'] = v1.fillna(v2).fillna(0)

        # Remover linhas sem data ou descrição válida
        df_clean = df_clean.dropna(subset=['Data', 'Descricao'])
        df_clean = df_clean[df_clean['Descricao'] != 'nan']

        # 3. CLASSIFICAÇÃO E SUMIF
        df_clean['Categoria'] = df_clean['Descricao'].apply(lambda x: classificar_movimento(x) or pedir_ia(x))
        
        # Filtrar despesas (negativos) e agrupar
        despesas = df_clean[df_clean['Valor'] < 0].copy()
        despesas['Valor'] = despesas['Valor'].abs()
        despesas['Mes_Ano'] = despesas['Data'].dt.strftime('%m-%Y')
        
        resumo = despesas.groupby(['Mes_Ano', 'Categoria'])['Valor'].sum().reset_index()

        # 4. OUTPUT PARA O EXCEL
        st.subheader("📋 Resumo por Categoria (Para colar no Excel S&G)")
        output_text = ""
        for _, row in resumo.iterrows():
            data_formatada = f"01-{row['Mes_Ano']}"
            valor_pt = f"{row['Valor']:.2f}".replace('.', ',')
            # Formato: DATA [TAB] DESCRIÇÃO [TAB] VALOR [TAB] CATEGORIA
            output_text += f"{data_formatada}\tTotal {row['Categoria']}\t{valor_pt}\t{row['Categoria']}\n"
        
        if output_text:
            st.text_area("Copia tudo e cola no teu Excel:", value=output_text, height=300)
            st.dataframe(resumo)
        else:
            st.warning("Não foram detetadas despesas negativas no ficheiro.")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
