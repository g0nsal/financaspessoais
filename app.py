import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
import json

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="S&G Budget Pro", layout="wide")

CATEGORIAS = [
    "Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", 
    "Água", "Prendas", "Saídas", "Netflix", "Internet", "Cabeleireiro", 
    "Seguros", "Despesas Médicas", "Farmácia", "Decoração/Obras", 
    "Transportes", "Desporto", "Eq. Eletrónicos", "Manutenção Auto", 
    "Viagens", "Entertenimento", "Estado", "Caridade", "Condomínio", 
    "Investimentos", "Telemóveis", "Pastelaria", "Salário", "Outros"
]

# --- MOTOR DE INTELIGÊNCIA ---
def limpar_texto(txt):
    """Remove ruído bancário: números, terminais, locais repetitivos"""
    txt = str(txt).upper()
    txt = re.sub(r'\d+', '', txt) # Remove números
    txt = re.sub(r'COMPRA|PAGAMENTO|PAG\.|CONTACTLESS|MAFRA|LISBOA|PORTUGAL', '', txt)
    return txt.strip()

def categorizar_pro(descricao):
    # 1. Regras Rápidas (Hardcoded para performance)
    desc_clean = limpar_texto(descricao)
    
    # Teu REGEX direto
    if any(x in desc_clean for x in ["VIAVERDE", "VIA VERDE", "A1", "A8", "A2"]): return "Portagens"
    if any(x in desc_clean for x in ["PINGO", "CONTINENTE", "LIDL", "AUCHAN", "ALDI"]): return "Mercearia"
    if "WELLS" in desc_clean or "FARMACIA" in desc_clean: return "Farmácia"
    if "PRESTACAO" in desc_clean: return "Cred. Hab. / Renda"
    if "SMAS" in desc_clean: return "Água"

    # 2. IA com Contexto de Especialista
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Age como um contabilista pessoal em Portugal. 
        Analisa este movimento: "{descricao}" (Limpo: "{desc_clean}")
        
        Usa EXCLUSIVAMENTE uma destas categorias: {CATEGORIAS}
        
        Raciocínio:
        - "Cáritas" ou "Donativo" -> Caridade
        - "Vinted" ou "Zippy" -> Roupa
        - "Netflix", "Spotify", "Disney" -> Netflix
        - "Uber Eats" ou "Restaurante" -> Restaurantes
        
        Responde apenas o nome da categoria.
        """
        response = model.generate_content(prompt)
        res = response.text.strip()
        # Validação: se a IA inventar uma categoria, vai para Outros
        return res if res in CATEGORIAS else "Outros"
    except:
        return "Outros"

# --- INTERFACE ---
st.title("📑 S&G Budget Automator Pro")

file = st.file_uploader("Upload do Extrato (ActivoBank)", type="xlsx")

if file:
    # Leitura ignorando o lixo do topo (procura a linha com datas)
    df_raw = pd.read_excel(file, header=None)
    start_row = 0
    for i, row in df_raw.iterrows():
        if re.search(r'\d{2}-\d{2}-\d{4}', str(row[0])):
            start_row = i
            break
    
    df = pd.read_excel(file, skiprows=start_row)
    
    # Mapeamento por posição (ActivoBank: A=Data, C=Desc, D ou E=Valor)
    df_proc = pd.DataFrame()
    df_proc['Data'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
    df_proc['Descricao'] = df.iloc[:, 2].astype(str)
    
    # Tenta achar a coluna do dinheiro
    v_col = 3 if pd.to_numeric(df.iloc[:, 3], errors='coerce').notnull().sum() > 5 else 4
    df_proc['Valor'] = pd.to_numeric(df.iloc[:, v_col], errors='coerce').fillna(0)
    
    # Limpeza e Categorização
    df_proc = df_proc.dropna(subset=['Data']).query("Valor != 0").copy()
    
    with st.spinner("IA a analisar com precisão..."):
        df_proc['Categoria'] = df_proc['Descricao'].apply(categorizar_pro)

    # --- RELATÓRIO SUMIF ---
    st.subheader("📊 Resumo para o Excel S&G")
    
    despesas = df_proc[df_proc['Valor'] < 0].copy()
    despesas['Valor'] = despesas['Valor'].abs()
    
    # Agrupamento (O SUMIF que tu queres)
    resumo = despesas.groupby('Categoria')['Valor'].sum().reset_index()
    
    output = ""
    data_ref = df_proc['Data'].iloc[0].strftime('%m-%Y')
    for _, r in resumo.iterrows():
        val = f"{r['Valor']:.2f}".replace('.', ',')
        output += f"01-{data_ref}\tTotal {r['Categoria']}\t{val}\t{r['Categoria']}\n"
    
    st.text_area("Copia para a aba 'Expenses':", value=output, height=250)
    
    with st.expander("Ver conferência detalhada"):
        st.dataframe(df_proc)
