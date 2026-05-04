import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="S&G Data Formatter", layout="wide")

# --- CATEGORIAS REAIS DO TEU EXCEL ---
MINHAS_CATEGORIAS = [
    "Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", 
    "Água", "Prendas", "Saídas", "Netflix", "Internet", "Cabeleireiro", 
    "Seguros", "Despesas Médicas", "Farmácia", "Decoração/Obras", 
    "Transportes", "Desporto", "Eq. Eletrónicos", "Manutenção Auto", 
    "Viagens", "Entertenimento", "Estado", "Caridade", "Condomínio", 
    "Investimentos", "Telemóveis", "Pastelaria", "Cartão de Crédito", 
    "Portagens", "Gás", "Eletricidade", "Limpeza", "Salário", "Outros"
]

# --- REGRAS DO TEU EXCEL (VIA VERDE, PINGO, ETC) ---
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
    if any(x in d for x in ["FARMACIA", "WELLS", "FARMA"]): return "Farmácia"
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
        prompt = f"Categoriza apenas com o nome da categoria: '{desc}'. Opções: {MINHAS_CATEGORIAS}"
        return model.generate_content(prompt).text.strip()
    except: return "Outros"

st.title("📑 Formatador S&G (Somado por Categoria)")

uploaded_file = st.file_uploader("Upload do Extrato", type="xlsx")

if uploaded_file:
    try:
        # 1. Tentar encontrar a linha onde começam os dados
        df_raw = pd.read_excel(uploaded_file, header=None)
        header_idx = 0
        for i, row in df_raw.iterrows():
            row_str = " ".join([str(val).lower() for val in row if pd.notnull(val)])
            if any(x in row_str for x in ['descri', 'hist', 'movimento']):
                header_idx = i
                break
        
        df = pd.read_excel(uploaded_file, header=header_idx)
        
        # 2. Mapeamento Inteligente de Colunas
        col_map = {}
        for c in df.columns:
            c_low = str(c).lower()
            if ('data' in c_low or 'mov' in c_low) and 'valor' not in c_low and 'Data' not in col_map:
                col_map['Data'] = c
            elif ('desc' in c_low or 'hist' in c_low) and 'Desc' not in col_map:
                col_map['Desc'] = c
            elif any(x in c_low for x in ['valor', 'import', 'montant']) and 'Data' not in c_low:
                col_map['Valor'] = c

        # Verificar se encontramos as 3 colunas vitais
        if all(k in col_map for k in ['Data', 'Desc', 'Valor']):
            df = df[[col_map['Data'], col_map['Desc'], col_map['Valor']]].copy()
            df.columns = ['Data', 'Descricao', 'Valor']
            
            # Limpeza de dados
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
            df = df.dropna(subset=['Data', 'Descricao'])

            # 3. Categorização
            df['Categoria'] = df['Descricao'].apply(lambda x: categorizar_com_regras(x) or sugerir_ia(x))
            
            # 4. Agrupar apenas despesas negativas para o resumo mensal
            despesas = df[df['Valor'] < 0].copy()
            despesas['Valor'] = despesas['Valor'].abs()
            despesas['MesAno'] = despesas['Data'].dt.strftime('%m-%Y')
            
            resumo = despesas.groupby(['MesAno', 'Categoria'])['Valor'].sum().reset_index()

            # 5. Gerar Texto para o Excel
            output_rows = []
            for _, row in resumo.iterrows():
                # Formato: 01-MM-AAAA [TAB] Descrição [TAB] Valor [TAB] Categoria
                linha = f"01-{row['MesAno']}\tTotal {row['Categoria']}\t{str(row['Valor']).replace('.', ',')}\t{row['Categoria']}"
                output_rows.append(linha)

            st.subheader("📋 Dados para Copiar e Colar")
            if output_rows:
                final_text = "\n".join(output_rows)
                st.text_area("Seleciona tudo (Ctrl+A), copia (Ctrl+C) e cola no Excel S&G:", value=final_text, height=300)
                st.dataframe(resumo)
            else:
                st.warning("Não encontrei despesas negativas. O teu banco usa uma coluna separada para débitos?")
        else:
            st.error(f"Não consegui identificar as colunas. Encontradas: {list(col_map.keys())}")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
