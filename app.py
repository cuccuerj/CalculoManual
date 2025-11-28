import streamlit as st
import re
import PyPDF2
from io import BytesIO

st.set_page_config(
    page_title="Processador de PDFs de Teleterapia",
    page_icon="🏥",
    layout="wide"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stTextArea textarea {
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    .debug-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        margin: 1rem 0;
        font-family: monospace;
        font-size: 0.85rem;
    }
    /* Esconde o texto padrão do uploader */
    .uploadedFile {display: none;}
    .stFileUploader label {
        display: flex;
        justify-content: center;
        align-items: center;
        background-color: #1f77b4;
        color: white;
        padding: 0.8rem 1.5rem;
        border-radius: 8px;
        cursor: pointer;
        font-weight: bold;
        transition: background-color 0.3s ease;
    }
    .stFileUploader label:hover {
        background-color: #105a8b;
    }
    /* Remove borda e fundo padrão */
    .stFileUploader > div {
        border: none !important;
        background: none !important;
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
    pattern = r'flu[eê]ncia\s+total\s*:\s*fsx\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*mm,\s*fsy\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*mm'
    matches = re.findall(pattern, content, flags=re.IGNORECASE | re.DOTALL)
    # Se houver mais de uma, usa a última (geralmente a “determinada a partir da fluência total”)
    return matches[-1] if matches else None



def process_pdf_content(content):
    """Processa o conteúdo do PDF e extrai os dados estruturados"""
    # Normalizar espaços
    content = ' '.join(content.split())
    
    output = []
    debug_info = {}
    
    # ===== EXTRAIR INFORMAÇÕES DO PACIENTE =====
    paciente_match = re.search(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)', content)
    matricula_match = re.search(r'Matricula:\s*(\d+)', content)
    
    if paciente_match:
        nome = paciente_match.group(1).strip()
        output.append(f"Nome, do, Paciente:, {', '.join(nome.split())}")
        debug_info['nome'] = nome
    
    if matricula_match:
        output.append(f"Matricula:, '{matricula_match.group(1)}'")
        debug_info['matricula'] = matricula_match.group(1)
    
    # ===== EXTRAIR ENERGIA DOS CAMPOS =====
    energy_matches = re.findall(r'Campo (\d+)\s+(\d+X)', content)
    energias = [e[1] for e in energy_matches]
    debug_info['energias'] = energias
    num_campos = len(energias)
    
    # ===== EXTRAIR TAMANHOS DOS CAMPOS =====
    x_sizes = extract_field(content, 'Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
    y_sizes = extract_field(content, 'Tamanho do Campo Aberto Y', 'Jaw Y1')
    debug_info['x_sizes'] = x_sizes
    debug_info['y_sizes'] = y_sizes
    
    # ===== EXTRAIR JAW =====
    jaw_y1 = extract_jaw(content, 'Jaw Y1', 'Jaw Y2', 'Y1:')
    jaw_y2 = extract_jaw(content, 'Jaw Y2', 'Filtro', 'Y2:')
    debug_info['jaw_y1'] = jaw_y1
    debug_info['jaw_y2'] = jaw_y2
    
    # ===== EXTRAIR FILTROS =====
    filtros = extract_filtros(content)
    debug_info['filtros'] = filtros
    
    # ===== EXTRAIR UM E DOSE =====
    um_matches = re.findall(r'Campo \d+\s+(\d+)\s*UM', content)
    dose_matches = re.findall(r'Campo \d+\s+([\d.]+)\s*cGy', content)
    debug_info['um_matches'] = um_matches
    debug_info['dose_matches'] = dose_matches
    
    # ===== EXTRAIR SSD E PROFUNDIDADES =====
    ssd = extract_field(content, 'SSD', 'Profundidade')
    prof = extract_field(content, 'Profundidade', 'Profundidade Efetiva')
    prof_eff = extract_field(content, 'Profundidade Efetiva', 'Informações do Campo')
    debug_info['ssd'] = ssd
    debug_info['prof'] = prof
    debug_info['prof_eff'] = prof_eff
    
    # ===== EXTRAIR UNIDADE DE TRATAMENTO =====
    # Buscar todas as ocorrências de "Unidade de tratamento"
    unidade_pattern = r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)'
    unidades = re.findall(unidade_pattern, content)
    
    if unidades:
        # Pegar a primeira unidade (geralmente todas são iguais)
        unidade, energia_unidade = unidades[0]
        formatted = f"Informações:, 'Unidade, 'de, 'tratamento:, '{unidade.strip()},, 'energia:, '{energia_unidade.strip()}'"
        output.append(formatted)
        debug_info['unidade'] = unidade.strip()
    
    # ===== EXTRAIR FLUÊNCIA =====
    fluencia_matches = extract_fluencia_values(content)
    debug_info['fluencia_matches'] = fluencia_matches
    
    # Criar listas fx e fy baseadas no número de campos
    fx = []
    fy = []
    
    fluencia_idx = 0
    for i in range(num_campos):
        # Se o campo tem filtro (filtro != '-'), usar "-"
        if i < len(filtros) and filtros[i] != '-':
            fx.append("-")
            fy.append("-")
        else:
            # Se tem dados de fluência disponíveis, usar
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
    
    # ===== MONTAR LINHAS DOS CAMPOS =====
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

# ===== INTERFACE DO STREAMLIT =====
st.markdown('<div class="main-header">🏥 Processador de PDFs de Teleterapia</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Extraia dados estruturados de planejamentos de teleterapia</div>', unsafe_allow_html=True)

# Informações sobre o sistema
with st.expander("ℹ️ Sobre este sistema"):
    st.markdown("""
    Este sistema processa arquivos PDF de planejamento de teleterapia e extrai:
    - **Dados do Paciente**: Nome e Matrícula
    - **Informações da Unidade**: Equipamento e Energia
    - **Dados dos Campos**: Tamanho, Jaw, Filtros, UM, Dose, SSD, Profundidade
    - **Fluência**: Valores fsx e fsy (quando não há filtro)
    
    ⚠️ **Nota**: Campos com filtros apresentam "-" nos valores de fluência.
    """)

# Opção de debug
show_debug = st.sidebar.checkbox("🔍 Mostrar informações de debug", value=False)

# Upload de arquivo
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    uploaded_file = st.file_uploader(
        "📁 Selecione o arquivo PDF",
        type="pdf",
        help="Faça upload do PDF de planejamento de teleterapia",
        label_visibility = "collapsed"
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
        st.markdown('<div class="success-box">✅ Arquivo processado com sucesso!</div>', unsafe_allow_html=True)
        
        # Estatísticas do processamento
        col1, col2, col3 = st.columns(3)
        num_linhas = len(result.split('\n'))
        num_campos = len(debug_info.get('energias', []))
        
        with col1:
            st.metric("📄 Total de Linhas", num_linhas)
        with col2:
            st.metric("🎯 Campos Detectados", num_campos)
        with col3:
            st.metric("📋 Páginas no PDF", len(pdf_reader.pages))
        
        # Mostrar debug se habilitado
        if show_debug:
            st.markdown("---")
            st.subheader("🔍 Informações de Debug")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Dados Extraídos:**")
                st.json({
                    "Energias": debug_info.get('energias', []),
                    "X Sizes": debug_info.get('x_sizes', []),
                    "Y Sizes": debug_info.get('y_sizes', []),
                    "Jaw Y1": debug_info.get('jaw_y1', []),
                    "Jaw Y2": debug_info.get('jaw_y2', []),
                    "Filtros": debug_info.get('filtros', [])
                })
            
            with col2:
                st.markdown("**Dados Complementares:**")
                st.json({
                    "UM": debug_info.get('um_matches', []),
                    "Dose": debug_info.get('dose_matches', []),
                    "SSD": debug_info.get('ssd', []),
                    "Prof": debug_info.get('prof', []),
                    "Prof Eff": debug_info.get('prof_eff', []),
                    "FX": debug_info.get('fx', []),
                    "FY": debug_info.get('fy', [])
                })
        
        st.markdown("---")
        
        # Dados extraídos
        st.subheader("📊 Dados Extraídos")
        st.text_area(
            "Resultado",
            result,
            height=400,
            help="Dados extraídos do PDF em formato estruturado"
        )
        
        # Botões de ação
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.download_button(
                label="💾 Baixar Resultados",
                data=result,
                file_name=f"dados_teleterapia_{uploaded_file.name.replace('.pdf', '')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col2:
            if st.button("🔄 Processar Outro", use_container_width=True):
                st.rerun()
        
    except Exception as e:
        st.error(f"❌ Ocorreu um erro ao processar o arquivo:")
        st.exception(e)
        
        # Mostrar conteúdo bruto para debug
        if show_debug and 'content' in locals():
            with st.expander("📄 Conteúdo bruto do PDF"):
                st.text_area("Texto extraído", content, height=300)
else:
    # Instruções quando não há arquivo
    st.info("👆 Faça upload de um arquivo PDF para começar o processamento")
    
    # Exemplo de formato esperado
    with st.expander("📖 Formato esperado do PDF"):
        st.markdown("""
        O PDF deve conter as seguintes informações:
        ```
        Nome do Paciente: [Nome]
        Matricula: [Número]
        
        Energia
        Campo 1 6X
        Campo 2 10X
        
        Tamanho do Campo Aberto X
        Campo 1 18.0 cm
        Campo 2 18.0 cm
        
        [... outros campos ...]
        
        Informações: Unidade de tratamento: 2100C, energia: 6X
        fluência total: fsx = 158 mm, fsy = 148 mm
        ```
        """)

# Rodapé
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.9rem;'>Desenvolvido para processamento de dados de Teleterapia | Ative o modo Debug no menu lateral para diagnósticos</div>",
    unsafe_allow_html=True
)
