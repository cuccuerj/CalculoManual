import streamlit as st
import re
import pandas as pd
import PyPDF2
from io import BytesIO

# ===== Configuração da Página =====
st.set_page_config(
    page_title="Processador de PDFs - Teleterapia",
    page_icon="🏥",
    layout="wide"
)

# ===== CSS Moderno e Customização do Botão =====
st.markdown("""
<style>
    /* Estilos Gerais */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0E1117;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 2rem;
    }
    
    /* ===== TRANSFORMAÇÃO DO FILE UPLOADER EM BOTÃO ===== */
    /* Esconde o texto padrão de 'Drag and drop' e o ícone */
    [data-testid='stFileUploader'] section > div:first-child {
        display: none;
    }
    
    [data-testid='stFileUploader'] section {
        padding: 0;
        background-color: transparent;
        border: none;
    }

    [data-testid='stFileUploader'] section > button {
        display: none; /* Esconde o botão de fechar nativo se aparecer */
    }

    /* Estiliza a área clicável para parecer um botão moderno */
    [data-testid='stFileUploader'] {
        width: fit-content;
        margin: auto;
    }

    /* Cria o visual do botão usando o label do uploader */
    div[data-testid="stFileUploader"] label {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background-color: #2563EB; /* Azul Moderno */
        color: white;
        padding: 0.6rem 1.5rem;
        border-radius: 8px;
        cursor: pointer;
        font-weight: 600;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        text-transform: uppercase;
        font-size: 0.9rem;
        letter-spacing: 0.5px;
    }

    div[data-testid="stFileUploader"] label:hover {
        background-color: #1D4ED8;
        transform: translateY(-2px);
        box-shadow: 0 6px 8px -1px rgba(0, 0, 0, 0.15);
    }

    div[data-testid="stFileUploader"] label::before {
        content: "📂 Carregar Relatório PDF"; /* Texto do botão */
        margin-right: 8px;
    }
    
    /* Esconde o texto original "Browse files" */
    div[data-testid="stFileUploader"] span {
        display: none;
    }

    /* ===== Fim do CSS do Uploader ===== */

    .stTextArea textarea {
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        border-radius: 8px;
    }
    
    .status-box {
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    .info-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ===== Funções de Extração (Lógica Original Preservada) =====
def extract_field(content, start, end):
    try:
        pattern = fr'{re.escape(start)}(.*?){re.escape(end)}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            block = match.group(1)
            valores = re.findall(r'Campo \d+\s*([\d.]+)\s*cm', block)
            return valores
    except Exception:
        pass
    return []

def extract_jaw(content, start, end, prefix):
    try:
        pattern = fr'{re.escape(start)}(.*?){re.escape(end)}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            block = match.group(1)
            valores = re.findall(fr'{re.escape(prefix)}\s*([+-]?\d+\.\d+)', block)
            return valores
    except Exception:
        pass
    return []

def extract_filtros(content):
    try:
        pattern = r'Filtro(.*?)MU'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            block = match.group(1)
            valores = re.findall(r'Campo \d+\s*([-\w]+)', block)
            return valores
    except Exception:
        pass
    return []

def extract_fluencia_total(content):
    try:
        pattern = r'flu[eê]ncia\s+total\s*:\s*fsx\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*mm,\s*fsy\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*mm'
        matches = re.findall(pattern, content, flags=re.IGNORECASE | re.DOTALL)
        return matches[-1] if matches else None
    except Exception:
        return None

def process_pdf_content(content):
    # Normalização básica
    content = ' '.join(content.split())
    
    output = []
    debug_info = {}
    
    # 1. Identificação do Paciente
    paciente_match = re.search(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)', content)
    matricula_match = re.search(r'Matricula:\s*(\d+)', content)
    
    if paciente_match:
        nome = paciente_match.group(1).strip()
        # Formato específico solicitado (com vírgulas extras)
        output.append(f"Nome, do, Paciente:, {', '.join(nome.split())}")
        debug_info['nome'] = nome
    
    if matricula_match:
        output.append(f"Matricula:, '{matricula_match.group(1)}'")
        debug_info['matricula'] = matricula_match.group(1)
    
    # 2. Dados dos Campos
    energy_matches = re.findall(r'Campo (\d+)\s+(\d+X)', content)
    energias = [e[1] for e in energy_matches]
    debug_info['energias'] = energias
    num_campos = len(energias)
    
    # Extrações
    x_sizes = extract_field(content, 'Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
    y_sizes = extract_field(content, 'Tamanho do Campo Aberto Y', 'Jaw Y1')
    jaw_y1 = extract_jaw(content, 'Jaw Y1', 'Jaw Y2', 'Y1:')
    jaw_y2 = extract_jaw(content, 'Jaw Y2', 'Filtro', 'Y2:')
    filtros = extract_filtros(content)
    um_matches = re.findall(r'Campo \d+\s+(\d+)\s*UM', content)
    dose_matches = re.findall(r'Campo \d+\s+([\d.]+)\s*cGy', content)
    ssd = extract_field(content, 'SSD', 'Profundidade')
    prof = extract_field(content, 'Profundidade', 'Profundidade Efetiva')
    prof_eff = extract_field(content, 'Profundidade Efetiva', 'Informações do Campo')
    
    # Salvar debug
    debug_info.update({
        'x_sizes': x_sizes, 'y_sizes': y_sizes, 'jaw_y1': jaw_y1, 
        'jaw_y2': jaw_y2, 'filtros': filtros, 'um_matches': um_matches,
        'dose_matches': dose_matches, 'ssd': ssd, 'prof': prof, 'prof_eff': prof_eff
    })
    
    # 3. Informações da Unidade
    unidade_pattern = r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)'
    unidades = re.findall(unidade_pattern, content)
    if unidades:
        unidade, energia_unidade = unidades[0]
        formatted = f"Informações:, 'Unidade, 'de, 'tratamento:, '{unidade.strip()},, 'energia:, '{energia_unidade.strip()}'"
        output.append(formatted)
        debug_info['unidade'] = unidade.strip()
    
    # 4. Fluência
    fluencia_total = extract_fluencia_total(content)
    debug_info['fluencia_total'] = fluencia_total
    
    fx, fy = [], []
    for i in range(num_campos):
        # Lógica: Se tem filtro físico, não usa fluência (suposição baseada no código original)
        if i < len(filtros) and filtros[i] != '-':
            fx.append("-")
            fy.append("-")
        else:
            if fluencia_total:
                fsx, fsy = fluencia_total
                fx.append(fsx)
                fy.append(fsy)
            else:
                fx.append("-")
                fy.append("-")
    
    # 5. Montagem das Linhas (CSV-Like Format)
    table_data = [] # Para visualização bonita na UI
    
    for i in range(num_campos):
        # Função auxiliar para pegar valor com segurança e formatar com apóstrofo
        def get_val(arr, idx, prefix="'"):
            return f"{prefix}{arr[idx]}" if idx < len(arr) else f"{prefix}N/A"

        def get_raw(arr, idx): 
            return arr[idx] if idx < len(arr) else "N/A"

        linha_parts = [
            energias[i] if i < len(energias) else 'N/A',
            get_val(x_sizes, i),
            get_val(y_sizes, i),
            get_val(jaw_y1, i),
            get_val(jaw_y2, i),
            get_val(filtros, i),
            get_val(um_matches, i),
            get_val(dose_matches, i),
            get_val(ssd, i),
            get_val(prof, i),
            get_val(prof_eff, i),
            get_val(fx, i),
            get_val(fy, i)
        ]
        output.append(", ".join(linha_parts))
        
        # Dados para tabela visual
        table_data.append({
            "Energia": energias[i],
            "Campo X": get_raw(x_sizes, i),
            "Campo Y": get_raw(y_sizes, i),
            "Jaw Y1": get_raw(jaw_y1, i),
            "Jaw Y2": get_raw(jaw_y2, i),
            "Filtro": get_raw(filtros, i),
            "UM": get_raw(um_matches, i),
            "Dose": get_raw(dose_matches, i),
            "SSD": get_raw(ssd, i),
            "Fluência X": get_raw(fx, i),
            "Fluência Y": get_raw(fy, i)
        })

    return '\n'.join(output), debug_info, table_data

# ===== Interface Principal =====

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("<div class='main-header'>Processador de Teleterapia</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Converta relatórios PDF para formato de dados estruturado</div>", unsafe_allow_html=True)
    
    # O botão customizado (via CSS)
    uploaded_file = st.file_uploader("Carregar PDF", type=['pdf'], label_visibility="visible")

if uploaded_file is not None:
    try:
        with st.spinner("Processando documento..."):
            # Leitura do PDF
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            full_text = ""
            for page in pdf_reader.pages:
                full_text += page.extract_text() + "\n"
            
            # Processamento
            result_text, debug_data, table_data = process_pdf_content(full_text)
            
            st.success("Processamento concluído com sucesso!")
            
            # Abas para organização
            tab1, tab2, tab3 = st.tabs(["📄 Texto Formatado", "📊 Visualização em Tabela", "🐞 Debug"])
            
            with tab1:
                st.markdown("### Saída para Copiar")
                st.markdown("Copie o conteúdo abaixo para o sistema de destino:")
                st.text_area("Resultado", value=result_text, height=300, label_visibility="collapsed")
            
            with tab2:
                st.markdown("### Conferência de Dados")
                if debug_data.get('nome'):
                    st.markdown(f"**Paciente:** {debug_data['nome']} | **Matrícula:** {debug_data.get('matricula', '-')}")
                
                if table_data:
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("Nenhum campo de tratamento encontrado.")

            with tab3:
                st.markdown("### Dados Brutos Extraídos")
                st.json(debug_data)

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {str(e)}")
else:
    # Espaço vazio ou instruções quando não há arquivo
    st.markdown(
        """
        <div style='text-align: center; color: #888; margin-top: 50px;'>
            <p>Aguardando upload do arquivo PDF...</p>
        </div>
        """, 
        unsafe_allow_html=True
    )
