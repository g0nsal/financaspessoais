import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import json
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Budget Tracking S&G", layout="wide")

# As tuas categorias reais (baseadas no teu Excel)
MINHAS_CATEGORIAS = [
    "Cred. Hab. / Renda", "Combustível", "Roupa", "Mercearia", "Restaurantes", 
    "Água", "Prendas", "Saídas", "Netflix", "Internet", "Cabeleireiro", 
    "Seguros", "Despesas Médicas", "Farmácia", "Decoração/Obras", 
    "Transportes", "Desporto", "Eq. Eletrónicos", "Manutenção Auto", 
    "Viagens", "Entertenimento", "Estado", "Caridade", "Condomínio", 
    "Investimentos", "Telemóveis", "Pastelaria", "Cartão de Crédito", 
    "Portagens", "Gás", "Eletricidade", "Limpeza", "Salário", "Outros"
]

MEMORY_FILE = "memoria_categorias.json"

def carregar_memoria():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f: return json.load(f)
        except: return {"Dicionario": {}}
    return {"Dicionario": {}}

def guardar_memoria(memoria):
    with open(MEMORY_FILE, "w") as f: json.dump(memoria, f)

def sugerir_categoria_ia(descricao):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        Categoriza este movimento bancário em Portugal: '{descricao}'
        Usa apenas uma destas categorias: {MINHAS_CATEGORIAS}
        Regras: 'PAG.PRESTACAO' ou 'EMPR' é 'Cred. Hab. / Renda'. 'PINGO DOCE' ou 'CONTINENTE' é 'Mercearia'.
        Responde apenas a palavra exata.
        """
        response = model.generate_content(prompt)
        sugestao = response.text.strip()
        return sugestao if sugestao in MINHAS_CATEGORIAS else "Outros"
    except: return "Outros"

# --- INTERFACE ---
st.title("📊 Budget Tracking Familiar S&G")

dados_memoria = carregar_memoria()
if "Dicionario" not in dados_memoria: dados_memoria["Dicionario"] = {}

uploaded_file = st.file_uploader("Upload do Extrato (Excel)", type="xlsx")

if uploaded_file:
    try:
        # Detetive de cabeçalho
        df_raw = pd.read_excel(uploaded_file, header=None)
        header_row = 0
        for i, row in df_raw.iterrows():
            row_str = " ".join([str(val).lower() for val in row.values if pd.notnull(val)])
            if 'descrição' in row_str or 'descritivo' in row_str:
                header_row = i
                break
        
        df = pd.read_excel(uploaded_file, header=header_row)
        
        # Mapeamento de colunas
        mapping = {}
        for c in df.columns:
            c_l = str(c).lower()
            if 'data mov' in c_l or ('data' in c_l and 'valor' not in c_l and 'Data' not in mapping.values()): mapping[c] = 'Data'
            elif ('desc' in c_l or 'hist' in c_l) and 'Descricao' not in mapping.values(): mapping[c] = 'Descricao'
            elif any(x in c_l for x in ['valor', 'import', 'montante']) and 'Valor' not in mapping.values(): mapping[c] = 'Valor'
        
        df = df.rename(columns=mapping)
        df = df[['Data', 'Descricao', 'Valor']].copy()
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)

        # Categorização com Memória + IA
        cat_finais = []
        novos = []
        for d in df['Descricao']:
            if d in dados_memoria["Dicionario"]:
                cat_finais.append(dados_memoria["Dicionario"][d])
            else:
                sug = sugerir_categoria_ia(d)
                cat_finais.append(f"❓ {sug}")
                if d not in novos: novos.append(d)
        
        df['Categoria'] = cat_finais

        # Painel de Ensino (Onde tu dás a ordem final)
        if novos:
            with st.expander("🎓 Validar Novas Categorias", expanded=True):
                for i, item in enumerate(novos[:15]):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    sug_ia = df[df['Descricao'] == item]['Categoria'].iloc[0].replace("❓ ", "")
                    idx = MINHAS_CATEGORIAS.index(sug_ia) if sug_ia in MINHAS_CATEGORIAS else 0
                    
                    c1.write(f"**{item}**")
                    escolha = c2.selectbox(f"Cat", MINHAS_CATEGORIAS, index=idx, key=f"s_{i}", label_visibility="collapsed")
                    if c3.button("✓", key=f"b_{i}"):
                        dados_memoria["Dicionario"][item] = escolha
                        guardar_memoria(dados_memoria)
                        st.rerun()

        # DASHBOARD
        st.divider()
        c1, c2, c3 = st.columns(3)
        gastos = df[df['Valor'] < 0]['Valor'].sum()
        ganhos = df[df['Valor'] > 0]['Valor'].sum()
        
        c1.metric("Despesas", f"{abs(gastos):.2f}€")
        c2.metric("Receitas", f"{ganhos:.2f}€")
        c3.metric("Saldo", f"{df['Valor'].sum():.2f}€")

        # Gráfico de Barras (Mais profissional para muitas categorias)
        df_p = df.copy()
        df_p['Categoria'] = df_p['Categoria'].str.replace("❓ ", "")
        gastos_cat = df_p[df_p['Valor'] < 0].groupby('Categoria')['Valor'].sum().abs().reset_index().sort_values('Valor')
        
        fig = px.bar(gastos_cat, x='Valor', y='Categoria', orientation='h', title="Gastos por Categoria")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao ler ficheiro: {e}")
