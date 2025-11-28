import streamlit as st
import re
import PyPDF2
from io import BytesIO

st.set_page_config(
    page_title="Processador de PDFs de Teleterapia",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS futurista e moderno
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }
    
    .main-header {
        font-size: 3.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
        text-shadow: 0 0 30px rgba(102, 126, 234, 0.3);
        animation: glow 2s ease-in-out infinite alternate;
    }
    
    @keyframes glow {
        from {
            filter: drop-shadow(0 0 10px rgba(102, 126, 234, 0.5));
        }
        to {
            filter: drop-shadow(0 0 20px rgba(118, 75, 162, 0.8));
        }
    }
    
    .sub-header {
        font-size: 1.2rem;
        color: #a0aec0;
        text-align: center;
        margin-bottom: 3rem;
        font-weight: 300;
    }
    
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        margin: 1rem 0;
    }
    
    .metric-card {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        padding: 1.5rem;
        border: 1px solid rgba(102, 126, 234, 0.2);
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.4);
        border-color: rgba(102, 126, 234, 0.5);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    
    .success-box {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.1) 100%);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        padding: 1.5rem;
        border-left: 4px solid #10b981;
        color: #6ee7b7;
        margin: 1rem 0;
        animation: slideIn 0.5s ease-out;
    }
    
    @keyframes slideIn {
        from {
            transform: translateX(-20px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .stTextArea textarea {
        background: rgba(0, 0, 0, 0.3) !important;
        border: 1px solid rgba(102, 126, 234, 0.3) !important;
        border-radius: 15px !important;
        color: #e2e8f0 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 0.9rem !important;
        backdrop-filter: blur(10px);
    }
    
    .stTextArea textarea:focus {
        border-color: rgba(102, 126, 234, 0.6) !important;
        box-shadow: 0 0 20px rgba(102, 126, 234, 0.3) !important;
    }
    
    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
    }
    
    .stButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px rgba(102, 126, 234, 0.6) !important;
    }
    
    .stDownloadButton button {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(240, 147, 251, 0.4) !important;
    }
    
    .stDownloadButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px rgba(240, 147, 251, 0.6) !important;
    }
    
    .upload-box {
        background: rgba(255, 255, 255, 0.03);
        border: 2px dashed rgba(102, 126, 234, 0.4);
        border-radius: 20px;
        padding: 3rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .upload-box:hover {
        border-color: rgba(102, 126, 234, 0.8);
        background: rgba(102, 126, 234, 0.05);
        transform: scale(1.02);
    }
    
    .stExpander {
        background: rgba(255, 255, 255, 0.03) !important;
        border-radius: 15px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    
    .debug-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(102, 126, 234, 0.3);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .info-icon {
        display: inline-block;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: 0.6;
        }
    }
    
    div[data-testid="stFileUploader"] {
        background: rgba(255, 255, 255, 0.03);
        border: 2px dashed rgba(102, 126, 234, 0.4);
        border-radius: 20px;
        padding: 2rem;
        transition: all 0.3s ease;
    }
    
    div[data-testid="stFileUploader"]:hover {
        border-color: rgba(102, 126, 234, 0.8);
        background: rgba(102, 126, 234, 0.05);
    }
    
    .sidebar .sidebar-content {
        background: rgba(15, 12, 41, 0.8);
        backdrop-filter: blur(10px);
    }
    
    h1, h2, h3 {
        color: #e2e8f0 !important;
    }
    
    p, li, label {
        color: #cbd5e0 !important;
    }
    
    .stAlert {
        background: rgba(59, 130, 246, 0.1) !important;
        border-left: 4px solid #3b82f6 !important;
        border-radius: 12px !important;
        color: #93c5fd !important;
    }
    
    code {
        background: rgba(0, 0, 0, 0.4) !important;
        color: #a78bfa !important;
        padding: 0.2rem 0.4rem !important;
        border-radius: 6px !important;
    }
    
    .footer {
        text-align: center;
        padding: 2rem;
        color: #718096;
        font-size: 0.9rem;
        margin-top: 3rem;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #10b981;
        margin-right: 8px;
        animation: blink 1.5s infinite;
    }
    
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
</style>
""", unsafe_allow_html=True)

def extract_field(content, start, end):
    """Extrai valores de campos entre dois marcadores"""
    pattern = fr'{re.escape(start)}(.*?){re.escape(end)}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        block = match.group(1)
        valores = re.findall(r'Campo \d+\s*([\d.]+)\s*cm', block)
        return valores
    return []

def extract_jaw(content, start, end, prefix):
    """Extrai valores de Jaw"""
    pattern = fr'{re.escape(start)}(.*?){re.escape(end)}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        block = match.group(1)
        valores = re.findall(fr'{re.escape(prefix)}\s*([+-]?\d+\.\d+)', block)
        return valores
    return []

def extract_filtros(content):
    """Extrai valores de filtros"""
    pattern = r'Filtro(.*?)MU'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        block = match.group(1)
        valores = re.findall(r'Campo \d+\s*([-\w]+)', block)
        return valores
    return []

def extract_fluencia_values(content):
    """Extrai valores de fluência (fsx e fsy) para cada campo"""
    pattern = r'fluência total:\s*fsx\s*=\s*(\d+)\s*mm,\s*fsy\s*=\s*(\d+)\s*mm'
    matches = re.findall(pattern, content)
    return matches

def process_pdf_content(content):
    """Processa o conteúdo do PDF e extrai os dados estruturados"""
    content = ' '.join(content.split())
    
    output = []
    debug_info = {}
    
    # EXTRAIR INFORMAÇÕES DO PACIENTE
    paciente_match = re.search(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)', content)
    matricula_match = re.search(r'Matricula:\s*(\d+)', content)
    
    if paciente_match:
        nome = paciente_match.group(1).strip()
        output.append(f"Nome, do, Paciente:, {', '.join(nome.split())}")
        debug_info['nome'] = nome
    
    if matricula_match:
        output.append(f"Matricula:, '{matricula_match.group(1)}'")
        debug_info['matricula'] = matricula_match.group(1)
    
    # EXTRAIR ENERGIA DOS CAMPOS
    energy_matches = re.findall(r'Campo (\d+)\s+(\d+X)', content)
    energias = [e[1] for e in energy_matches]
    debug_info['energias'] = energias
    num_campos = len(energias)
    
    # EXTRAIR TAMANHOS DOS CAMPOS
    x_sizes = extract_field(content, 'Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
    y_sizes = extract_field(content, 'Tamanho do Campo Aberto Y', 'Jaw Y1')
    debug_info['x_sizes'] = x_sizes
    debug_info['y_sizes'] = y_sizes
    
    # EXTRAIR JAW
    jaw_y1 = extract_jaw(content, 'Jaw Y1', 'Jaw Y2', 'Y1:')
    jaw_y2 = extract_jaw(content, 'Jaw Y2', 'Filtro', 'Y2:')
    debug_info['jaw_y1'] = jaw_y1
    debug_info['jaw_y2'] = jaw_y2
    
    # EXTRAIR FILTROS
    filtros = extract_filtros(content)
    debug_info['filtros'] = filtros
    
    # EXTRAIR UM E DOSE
    um_matches = re.findall(r'Campo \d+\s+(\d+)\s*UM', content)
    dose_matches = re.findall(r'Campo \d+\s+([\d.]+)\s*cGy', content)
    debug_info['um_matches'] = um_matches
    debug_info['dose_matches'] = dose_matches
    
    # EXTRAIR SSD E PROFUNDIDADES
    ssd = extract_field(content, 'SSD', 'Profundidade')
    prof = extract_field(content, 'Profundidade', 'Profundidade Efetiva')
    prof_eff = extract_field(content, 'Profundidade Efetiva', 'Informações do Campo')
    debug_info['ssd'] = ssd
    debug_info['prof'] = prof
    debug_info['prof_eff'] = prof_eff
    
    # EXTRAIR UNIDADE DE TRATAMENTO
    unidade_pattern = r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)'
    unidades = re.findall(unidade_pattern, content)
    
    if unidades:
        unidade, energia_unidade = unidades[0]
        formatted = f"Informações:, 'Unidade, 'de, 'tratamento:, '{unidade.strip()},, 'energia:, '{energia_unidade.strip()}'"
        output.append(formatted)
        debug_info['unidade'] = unidade.strip()
    
    # EXTRAIR FLUÊNCIA
    fluencia_matches = extract_fluencia_values(content)
    debug_info['fluencia_matches'] = fluencia_matches
    
    fx = []
    fy = []
    
    fluencia_idx = 0
    for i in range(num_campos):
        if i < len(filtros) and filtros[i] != '-':
            fx.append("-")
            fy.append("-")
        else:
            if fluencia_idx < len(fluencia_matches):
                fsx, fsy = fluencia_matches[fluencia_idx]
                fx.append(fsx)
                fy.append(fsy)
                fluencia_idx += 1
            else:
                fx.append("-")
                fy.append("-")
    
    debug_info['fx'] = fx
    debug_info['fy'] = fy
    
    # MONTAR LINHAS DOS CAMPOS
    for i in range(num_campos):
        linha_parts = []
        linha_parts.append(energias[i] if i < len(energias) else 'N/A')
        linha_parts.append(f"'{x_sizes[i]}" if i < len(x_sizes) else "'N/A")
        linha_parts.append(f"'{y_sizes[i]}" if i < len(y_sizes) else "'N/A")
        linha_parts.append(f"'{jaw_y1[i]}" if i < len(jaw_y1) else "'N/A")
        linha_parts.append(f"'{jaw_y2[i]}" if i < len(jaw_y2) else "'N/A")
        linha_parts.append(f"'{filtros[i]}" if i < len(filtros) else "'N/A")
        linha_parts.append(f"'{um_matches[i]}" if i < len(um_matches) else "'N/A")
        linha_parts.append(f"'{dose_matches[i]}" if i < len(dose_matches) else "'N/A")
        linha_parts.append(f"'{ssd[i]}" if i < len(ssd) else "'N/A")
        linha_parts.append(f"'{prof[i]}" if i < len(prof) else "'N/A")
        linha_parts.append(f"'{prof_eff[i]}" if i < len(prof_eff) else "'N/A")
        linha_parts.append(f"'{fx[i]}" if i < len(fx) else "'N/A")
        linha_parts.append(f"'{fy[i]}" if i < len(fy) else "'N/A")
        
        linha = ", ".join(linha_parts)
        output.append(linha)
    
    return '\n'.join(output), debug_info

# INTERFACE DO STREAMLIT
st.markdown('<div class="main-header">⚡ TELETERAPIA PRO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Sistema avançado de processamento de PDFs de planejamento radioterápico</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Configurações")
    show_debug = st.checkbox("🔍 Modo Debug", value=False)
    st.markdown("---")
    st.markdown("### 📊 Status do Sistema")
    st.markdown('<span class="status-indicator"></span> Sistema Online', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("""
    ### 💡 Recursos
    - ✨ Extração automática
    - 🎯 Alta precisão
    - 🚀 Processamento rápido
    - 🔒 Seguro e confiável
    """)

# Informações sobre o sistema
with st.expander("ℹ️ Sobre o Sistema"):
    st.markdown("""
    ### 🏥 Processador de Planejamento Radioterápico
    
    **Funcionalidades:**
    - 📋 **Dados do Paciente**: Nome e Matrícula
    - 🎛️ **Unidade de Tratamento**: Equipamento e Energia
    - 🎯 **Campos de Tratamento**: Geometria e parâmetros
    - 📊 **Dosimetria**: UM, Dose, SSD, Profundidades
    - 🌊 **Fluência**: Valores fsx e fsy
    
    > ⚠️ Campos com filtros apresentam "-" nos valores de fluência
    """)

# Upload de arquivo
st.markdown("### 📁 Upload de Arquivo")
uploaded_file = st.file_uploader(
    "Arraste e solte o arquivo PDF aqui",
    type="pdf",
    help="Selecione o PDF de planejamento de teleterapia",
    label_visibility="collapsed"
)

if uploaded_file is not None:
    try:
        with st.spinner('⏳ Processando arquivo...'):
            # Ler o conteúdo do PDF
            pdf_reader = PyPDF2.PdfReader(BytesIO(uploaded_file.getvalue()))
            content = ""
            for page in pdf_reader.pages:
                content += page.extract_text()
            
            # Processar o conteúdo
            result, debug_info = process_pdf_content(content)
        
        # Exibir resultados
        st.markdown('<div class="success-box">✅ <strong>Processamento Concluído!</strong> Todos os dados foram extraídos com sucesso.</div>', unsafe_allow_html=True)
        
        # Estatísticas do processamento
        st.markdown("### 📊 Estatísticas de Processamento")
        col1, col2, col3 = st.columns(3)
        
        num_linhas = len(result.split('\n'))
        num_campos = len(debug_info.get('energias', []))
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">📄 Linhas Extraídas</div>
                <div class="metric-value">{num_linhas}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🎯 Campos Detectados</div>
                <div class="metric-value">{num_campos}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">📋 Páginas no PDF</div>
                <div class="metric-value">{len(pdf_reader.pages)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Mostrar debug se habilitado
        if show_debug:
            st.markdown("---")
            st.markdown("### 🔍 Painel de Debug")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown('<div class="debug-panel">', unsafe_allow_html=True)
                st.markdown("**🎯 Dados Principais**")
                st.json({
                    "Energias": debug_info.get('energias', []),
                    "X Sizes": debug_info.get('x_sizes', []),
                    "Y Sizes": debug_info.get('y_sizes', []),
                    "Jaw Y1": debug_info.get('jaw_y1', []),
                    "Jaw Y2": debug_info.get('jaw_y2', []),
                    "Filtros": debug_info.get('filtros', [])
                })
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="debug-panel">', unsafe_allow_html=True)
                st.markdown("**📊 Dados Complementares**")
                st.json({
                    "UM": debug_info.get('um_matches', []),
                    "Dose": debug_info.get('dose_matches', []),
                    "SSD": debug_info.get('ssd', []),
                    "Profundidade": debug_info.get('prof', []),
                    "Prof. Efetiva": debug_info.get('prof_eff', []),
                    "FX": debug_info.get('fx', []),
                    "FY": debug_info.get('fy', [])
                })
                st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Dados extraídos
        st.markdown("### 📊 Dados Extraídos")
        st.text_area(
            "Resultado do Processamento",
            result,
            height=400,
            help="Dados estruturados extraídos do PDF",
            label_visibility="collapsed"
        )
        
        # Botões de ação
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.download_button(
                label="💾 Baixar Resultados",
                data=result,
                file_name=f"teleterapia_{uploaded_file.name.replace('.pdf', '')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col2:
            if st.button("🔄 Novo Arquivo", use_container_width=True):
                st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erro no Processamento")
        st.exception(e)
        
        if show_debug and 'content' in locals():
            with st.expander("📄 Conteúdo Bruto do PDF"):
                st.text_area("Texto extraído", content, height=300)
else:
    # Instruções quando não há arquivo
    st.info("👆 Faça upload de um arquivo PDF para iniciar o processamento")
    
    # Exemplo de formato esperado
    with st.expander("📖 Formato Esperado do PDF"):
        st.code("""
Nome do Paciente: [Nome Completo]
Matricula: [Número]

Energia
Campo 1 6X
Campo 2 10X

Tamanho do Campo Aberto X
Campo 1 18.0 cm
Campo 2 18.0 cm

Tamanho do Campo Aberto Y
Campo 1 15.2 cm
Campo 2 15.9 cm

[... outros campos ...]

Informações: Unidade de tratamento: 2100C, energia: 6X
fluência total: fsx = 158 mm, fsy = 148 mm
        """, language="text")

# Rodapé
st.markdown('<div class="footer">⚡ TELETERAPIA PRO v1.0 | Desenvolvido para Excelência em Radioterapia</div>', unsafe_allow_html=True)
