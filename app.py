import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

st.set_page_config(page_title="S&G Budget Automator", layout="wide")

# --- 1. TEU MOTOR DE REGRAS (Fórmulas do teu Sheets) ---
REGRAS_FIXAS = {
    "Portagens": r"VIAVERDE|VIA VERDE|A21|A8|A1|A2|A3|A4|A5|A6|A7|A9|A10",
    "Mercearia": r"CONTINENTE|LIDL|PINGO|MINIPRECO|ALDI|AUCHAN|MERCADONA",
    "Água": r"SMAS|EPAL",
    "Cred. Hab. / Renda": r"PRESTACAO|EMPRESTIMO|CHAB|RENDIMENTO MÍNIMO",
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

st.title("📊 S&G Formatter v3.0 (ActivoBank Fix)")

uploaded_file = st.file_uploader("Carrega o Excel", type=["xlsx"])

if uploaded_file:
    try:
        # Lemos o Excel bruto para encontrar onde a tabela começa
        df_raw = pd.read_excel(uploaded_file, header=None)
        
        # 1. Encontrar a linha que contém os cabeçalhos reais (Data, Descrição, etc.)
        start_row = 0
        found_header = False
        for i, row in df_raw.iterrows():
            # Juntamos o conteúdo da linha para procurar palavras-chave
            line_content = " ".join([str(x).lower() for x in row if pd.notnull(x)])
            if any(k in line_content for k in ['data', 'descritivo', 'descri', 'movimento', 'valor', 'montante']):
                start_row = i
                found_header = True
                break
        
        if not found_header:
            st.error("Não consegui encontrar a tabela de movimentos. O ficheiro está correto?")
        else:
            # Recarregamos o DF a partir da linha certa
            df = pd.read_excel(uploaded_file, header=start_row)
            st.write("✅ Tabela encontrada! Colunas:", list(df.columns))

            # 2. Mapeamento Inteligente (Ajustado para ActivoBank)
            col_data, col_desc, col_valor = None, None, None
            for col in df.columns:
                c_low = str(col).lower()
                if 'data' in c_low and 'valor' not in c_low: col_data = col
                if any(x in c_low for x in ['descri', 'hist', 'texto', 'detalhe']): col_desc = col
                if any(x in c_low for x in ['montante', 'valor', 'quantia', 'import', 'débito', 'debito']): col_valor = col

            # Se falhar, tentamos por posição (mais comum no AB: Data=0, Desc=1, Valor=3 ou 4)
            if not col_data: col_data = df.columns[0]
            if not col_desc: col_desc = df.columns[1]
            if not col_valor:
                # No AB o valor costuma estar na 4ª ou 5ª coluna se houver "Data Valor"
                for i in [3, 4, 2]:
                    if i < len(df.columns):
                        col_valor = df.columns[i]
                        break

            # 3. Limpeza e Processamento
            df_clean = pd.DataFrame()
            df_clean['Data'] = pd.to_datetime(df[col_data], errors='coerce')
            df_clean['Descricao'] = df[col_desc].astype(str)
            df_clean['Valor'] = pd.to_numeric(df[col_valor], errors='coerce').fillna(0)
            
            # Remover linhas inúteis (saldos, rodapés ou datas vazias)
            df_clean = df_clean.dropna(subset=['Data']).copy()
            df_clean = df_clean[df_clean['Descricao'].str.len() > 3]

            # 4. Classificar e Agrupar
            df_clean['Categoria'] = df_clean['Descricao'].apply(lambda x: classificar_movimento(x) or pedir_ia(x))
            
            # Focar apenas em despesas (valores negativos ou considerar tudo despesa se vierem positivos)
            # Dica: No ActivoBank as despesas vêm com sinal negativo.
            despesas = df_clean[df_clean['Valor'] < 0].copy()
            despesas['Valor'] = despesas['Valor'].abs()
            despesas['Mes_Ano'] = despesas['Data'].dt.strftime('%m-%Y')
            
            resumo = despesas.groupby(['Mes_Ano', 'Categoria'])['Valor'].sum().reset_index()

            # 5. Output Final para o teu Excel
            st.subheader("📋 Copiar para Excel S&G")
            output_rows = []
            for _, row in resumo.iterrows():
                data_excel = f"01-{row['Mes_Ano']}"
                valor_pt = f"{row['Valor']:.2f}".replace('.', ',')
                # DATA [TAB] DESCRIÇÃO [TAB] VALOR [TAB] CATEGORIA
                output_rows.append(f"{data_excel}\tTotal {row['Categoria']}\t{valor_pt}\t{row['Categoria']}")
            
            if output_rows:
                st.text_area("Seleciona tudo, copia e cola no Excel:", value="\n".join(output_rows), height=300)
                st.dataframe(resumo)
            else:
                st.warning("Não encontrei despesas negativas. Tens a certeza que este extrato tem gastos?")

    except Exception as e:
        st.error(f"Erro Crítico: {e}")
