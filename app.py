import streamlit as st
import pandas as pd
import google.generativeai as genai
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Financeira Familiar", layout="wide")
genai.configure(api_key="TUA_CHAVE_API_AQUI")
model = genai.GenerativeModel('gemini-1.5-flash')

# --- ESTILO ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
""", unsafe_allow_html=True)

# --- LÓGICA DE IA ---
def categorizar_transacoes(df):
    """Envia as descrições para o Gemini categorizar."""
    lista_descricoes = df['Descrição'].unique().tolist()
    
    prompt = f"""
    Atua como um contabilista português. Categoriza estas descrições de movimentos bancários:
    {lista_descricoes}
    
    Categorias permitidas: [Alimentação, Habitação, Transportes, Saúde, Lazer, Estado, Investimentos, Salário, Transferências, Outros].
    
    Regras:
    - SMAS, EPAL, Goldenergy, Condomínio -> Habitação.
    - Pingo Doce, Continente, Lidl, Mercadona -> Alimentação.
    - Galp, Repsol, Via Verde -> Transportes.
    - Transferências entre Sofia e Gonçalo -> Transferências.
    
    Responde APENAS com um formato de lista Python: ["Categoria1", "Categoria2", ...] na mesma ordem.
    """
    
    response = model.generate_content(prompt)
    try:
        # Converte a string da resposta numa lista
        categorias = eval(response.text.strip())
        mapping = dict(zip(lista_descricoes, categorias))
        return mapping
    except:
        st.error("Erro na resposta da IA. Tenta novamente.")
        return {}

# --- UI ---
st.title("🏦 Dashboard de Despesas Familiares")
st.subheader("Upload de Extratos (ActivoBank / Cetelem)")

with st.expander("📁 Upload de Ficheiros", expanded=True):
    uploaded_files = st.file_uploader("Carrega os teus Excels ou CSVs", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        # Tenta ler Excel (padrão ActivoBank/Cetelem)
        try:
            # O ActivoBank costuma ter lixo nas primeiras 7 linhas
            df = pd.read_excel(file, header=7) 
            if 'Descrição' not in df.columns:
                df = pd.read_excel(file) # Tenta sem skip se falhar
        except:
            df = pd.read_csv(file)
            
        all_data.append(df)

    if all_data:
        df_final = pd.concat(all_data, ignore_index=True)
        
        # Limpeza básica (ajustar nomes de colunas conforme o teu banco)
        # Exemplo para ActivoBank: 'Data Mov.' e 'Descrição' e 'Montante'
        st.write(f"Total de movimentos carregados: {len(df_final)}")

        if st.button("✨ Categorizar com IA"):
            with st.spinner("O Gemini está a analisar os teus gastos..."):
                mapping = categorizar_transacoes(df_final)
                df_final['Categoria'] = df_final['Descrição'].map(mapping)
                
                # Guardar em cache/estado para não gastar API em cada clique
                st.session_state['df_analisado'] = df_final

        if 'df_analisado' in st.session_state:
            df_plot = st.session_state['df_analisado']
            
            # --- DASHBOARD ---
            c1, c2, c3 = st.columns(3)
            receitas = df_plot[df_plot['Montante'] > 0]['Montante'].sum()
            despesas = df_plot[df_plot['Montante'] < 0]['Montante'].sum()
            
            c1.metric("Recebimentos", f"{receitas:,.2f}€")
            c2.metric("Gastos Totais", f"{abs(despesas):,.2f}€", delta_color="inverse")
            c3.metric("Saldo", f"{(receitas + despesas):,.2f}€")

            # Gráficos
            st.markdown("---")
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.write("### Gastos por Categoria")
                gastos_cat = df_plot[df_plot['Montante'] < 0].groupby('Categoria')['Montante'].sum().abs()
                st.bar_chart(gastos_cat)

            with col_chart2:
                st.write("### Tabela de Detalhe")
                st.dataframe(df_plot[['Data Mov.', 'Descrição', 'Categoria', 'Montante']], use_container_width=True)
