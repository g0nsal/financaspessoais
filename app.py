import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os

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
def aplicar_regras_excel(desc):
    d = str(desc).upper()
    if any(x in d for x in ["VIAVERDE", "VIA VERDE", "A21", "A8", "A1", "A9"]): return "Portagens"
    if any(x in d for x in ["CONTINENTE", "LIDL", "PINGO", "MINIPRECO", "ALDI"]): return "Mercearia"
    if any(x in d for x in ["FARMACIA", "WELLS", "FARMA"]): return "Farmácia"
    if "SMAS" in d: return "Água"
    if "PRESTACAO" in d: return "Cred. Hab. / Renda"
    if "VALOR ACTIVO" in d: return "Condomínio"
    if "LIGAT" in d: return "Internet"
    if "LUZBOA" in d: return "Eletricidade"
    if "LISBOAGAS" in d: return "Gás"
    if "WOO" in d: return "Telemóveis"
    if any(x in d for x in ["IKEA", "CHINA"]): return "Decoração/Obras"
    if any(x in d for x in ["MULTICARE", "CUF"]): return "Despesas Médicas"
    return None

def sugerir_ia(desc):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Categoriza apenas com uma palavra: '{desc}'. Opções: {MINHAS_CATEGORIAS}"
        return model.generate_content(prompt).text.strip()
    except: return "Outros"

# --- INTERFACE ---
st.title("📑 Formatador para Excel S&G")
st.info("Faz o upload do extrato e copia os dados somados por categoria para o teu Excel.")

uploaded_file = st.file_uploader("Upload Excel ActivoBank / Cetelem", type="xlsx")

if uploaded_file:
    try:
        # Lógica de leitura robusta
        df_all = pd.read_excel(uploaded_file, header=None)
        header_idx = 0
        for i, row in df_all.iterrows():
            if any('descri' in str(x).lower() for x in row):
                header_idx = i
                break
        
        df = pd.read_excel(uploaded_file, header=header_idx)
        
        # Identificar colunas
        cols = {'Data': None, 'Desc': None, 'Valor': None}
        for c in df.columns:
            cl = str(c).lower()
            if 'data' in cl and not cols['Data']: cols['Data'] = c
            if ('desc' in cl or 'hist' in cl) and not cols['Desc']: cols['Desc'] = c
            if any(x in cl for x in ['valor', 'import', 'montant']) and not cols['Valor']: cols['Valor'] = c

        df = df[[cols['Data'], cols['Desc'], cols['Valor']]].copy()
        df.columns = ['Data', 'Descricao', 'Valor']
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
        
        # Categorização
        categorias_atribuidas = []
        for d in df['Descricao']:
            regra = aplicar_regras_excel(d)
            categorias_atribuidas.append(regra if regra else sugerir_ia(d))
        
        df['Categoria'] = categorias_atribuidas
        
        # --- PROCESSAMENTO PARA COPIAR E COLAR ---
        # 1. Filtrar apenas despesas (Valor < 0)
        despesas = df[df['Valor'] < 0].copy()
        despesas['Valor'] = despesas['Valor'].abs()
        
        # 2. Agrupar por Mês e Categoria
        despesas['Mes_Ano'] = despesas['Data'].dt.strftime('%Y-%m')
        resumo = despesas.groupby(['Mes_Ano', 'Categoria'])['Valor'].sum().reset_index()
        
        # 3. Formatar string para o Excel (Data | Descrição fixa | Valor | Categoria)
        # Ex: 01-01-2024 | Total Mercearia | 250.50 | Mercearia
        output_rows = []
        for _, row in resumo.iterrows():
            data_fake = f"01-{row['Mes_Ano'][5:7]}-{row['Mes_Ano'][0:4]}" # Ex: 01-01-2024
            linha = f"{data_fake}\tTotal {row['Categoria']}\t{row['Valor']:.2f}\t{row['Categoria']}"
            output_rows.append(linha)

        st.subheader("📋 Dados para Copiar (Paste no Excel S&G)")
        text_output = "\n".join(output_rows)
        st.text_area("Copia o conteúdo abaixo:", value=text_output, height=300)
        
        st.success("Dica: Os valores estão separados por TAB, o que permite colar direto nas colunas do Excel.")
        st.dataframe(resumo)

    except Exception as e:
        st.error(f"Erro: {e}")
