import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import json

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Financeira Gonsalo", layout="wide")

# Inicializar Estado
if 'data' not in st.session_state:
    st.session_state['data'] = None

# --- FUNÇÃO DE CATEGORIZAÇÃO (IA) ---
def categorizar_com_ia(lista_descricoes):
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Filtro para não enviar descrições vazias
        lista_limpa = [str(d) for d in lista_descricoes if str(d).strip()]
        if not lista_limpa:
            return {}

        prompt = f"""
        Categoriza estes movimentos bancários portugueses nestas categorias: 
        [Alimentação, Habitação, Transportes, Saúde, Lazer, Estado, Investimentos, Salário, Transferências, Outros].
        
        Movimentos: {lista_limpa}
        
        Responde APENAS no formato JSON: {{"Descricao": "Categoria", ...}}
        """
        
        response = model.generate_content(prompt)
        # Limpeza para extrair apenas o JSON
        texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(texto)
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return {}

# --- INTERFACE ---
st.title("🏦 Gestão Financeira Familiar")

uploaded_file = st.file_uploader("Upload do Excel (ActivoBank ou Cetelem)", type="xlsx")

if uploaded_file:
    try:
        # Tenta ler ActivoBank (pula 7 linhas)
        df_raw = pd.read_excel(uploaded_file)
        if "Descrição" not in df_raw.columns:
            df_raw = pd.read_excel(uploaded_file, header=7)

        # Normalizar colunas
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        mapping_cols = {
            'Descrição': 'Descricao',
            'Descritivo': 'Descricao',
            'Importância': 'Valor',
            'Montante': 'Valor',
            'Valor': 'Valor',
            'Data Mov.': 'Data',
            'Data': 'Data'
        }
        df = df_raw.rename(columns=mapping_cols)
        
        # Manter apenas o que interessa
        cols_existentes = [c for c in ['Data', 'Descricao', 'Valor'] if c in df.columns]
        df = df[cols_existentes].dropna(subset=['Descricao', 'Valor'])
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')

        st.success(f"Carregados {len(df)} movimentos.")
        
        if st.button("✨ Categorizar com IA"):
            with st.spinner("O Gemini está a analisar..."):
                unique_desc = df['Descricao'].unique().tolist()
                categorias_map = categorizar_com_ia(unique_desc)
                df['Categoria'] = df['Descricao'].map(categorias_map).fillna("Outros")
                st.session_state['data'] = df

        if st.session_state['data'] is not None:
            data = st.session_state['data']
            
            # Dashboard
            m1, m2, m3 = st.columns(3)
            receitas = data[data['Valor'] > 0]['Valor'].sum()
            despesas = data[data['Valor'] < 0]['Valor'].sum()
            
            m1.metric("Recebimentos", f"{receitas:.2f}€")
            m2.metric("Despesas", f"{abs(despesas):.2f}€")
            m3.metric("Saldo", f"{(receitas+despesas):.2f}€")

            st.markdown("---")
            c1, c2 = st.columns(2)
            
            with c1:
                fig = px.pie(data[data['Valor'] < 0], values=data[data['Valor'] < 0]['Valor'].abs(), names='Categoria', hole=0.4, title="Distribuição de Gastos")
                st.plotly_chart(fig, use_container_width=True)
            
            with c2:
                st.dataframe(data, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao ler ficheiro: {e}")
