import streamlit as st
import re
import PyPDF2
from io import BytesIO

st.set_page_config(page_title="Processador de PDFs para o cálculo manual", page_icon="🏥")

# Funções de extração de dados (as mesmas do seu código)
def extract_field(content, start, end):
    pattern = fr'{start}(.*?){end}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        block = match.group(1)
        return re.findall(r'Campo \d+\s*([\d.]+)\s*cm', block)
    return []

def extract_jaw(content, start, end, prefix):
    pattern = fr'{start}(.*?){end}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        block = match.group(1)
        return re.findall(fr'{prefix}\s*([+-]?\d+\.\d+)', block)
    return []

def extract_filtros(content):
    pattern = r'Filtro(.*?)MU'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        block = match.group(1)
        return re.findall(r'Campo \d+\s*([-\w]+)', block)
    return []

def process_pdf_content(content):
    content = ' '.join(content.split())
    
    # Extrair informações do paciente
    paciente_match = re.search(r'Nome do Paciente:\s*(.+?)(?=\s*(?:Matricula|$))', content)
    matricula_match = re.search(r'Matricula:\s*(\d+)', content)
    
    # Extrair dados dos campos
    energy_matches = re.findall(r'Campo \d+\s*(\d+X)', content)
    x_sizes = extract_field(content, 'Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
    y_sizes = extract_field(content, 'Tamanho do Campo Aberto Y', 'Jaw Y1')
    jaw_y1 = extract_jaw(content, 'Jaw Y1', 'Jaw Y2', 'Y1:')
    jaw_y2 = extract_jaw(content, 'Jaw Y2', 'Filtro', 'Y2:')
    filtros = extract_filtros(content)
    um_matches = re.findall(r'Campo \d+.*?(\d+)\s*UM', content)
    dose_matches = re.findall(r'Campo \d+.*?(\d+\.?\d*)\s*cGy', content)
    ssd = extract_field(content, 'SSD', 'Profundidade')
    prof = extract_field(content, 'Profundidade', 'Profundidade Efetiva')
    prof_eff = extract_field(content, 'Profundidade Efetiva', 'Informações do Campo')
    
    output = []
    
    # Informações do paciente
    if paciente_match:
        nome = paciente_match.group(1).strip()
        output.append(f"Nome, do, Paciente:, {', '.join(nome.split())}")
    if matricula_match:
        output.append(f"Matricula:, '{matricula_match.group(1)}'")

    # Informações da unidade de tratamento
    lines = content.split('Informações:')
    for line in lines:
        if 'Unidade de tratamento:' in line:
            parts = line.split(':')
            unidade = parts[1].split(',')[0].strip()
            energia = parts[2].strip()
            formatted = f"Informações:, 'Unidade, 'de, 'tratamento:, '{unidade},, 'energia:, '{energia}'"
    output.append(formatted)

    # Fluência total com tratamento de filtros
    padraocampofluencia = r"fluência total: fsx\s*=\s*(\d+)\s*mm,\s*fsy\s*=\s*(\d+)\s*mm"
    matches = re.findall(padraocampofluencia, content)
    fx = []
    fy = []
    
    if matches:
        for i in range(len(filtros)):
            if i < len(filtros) and filtros[i] != '-':
                fx.append("-")
                fy.append("-")
            elif i < len(matches):
                fsx, fsy = matches[i]
                fx.append(fsx)
                fy.append(fsy)

    # Dados dos campos de tratamento
    for i in range(len(energy_matches)):
        if (i < len(x_sizes) and i < len(y_sizes) and i < len(jaw_y1) and
            i < len(jaw_y2) and i < len(filtros) and i < len(um_matches) and
            i < len(dose_matches) and i < len(ssd) and i < len(prof) and
            i < len(prof_eff)):

            linha = (
                f"Campo {i+1}: {energy_matches[i]}, '{x_sizes[i]}, '{y_sizes[i]}, "
                f"'{jaw_y1[i]}, '{jaw_y2[i]}, "
                f"'{filtros[i]}, '{um_matches[i]}, "
                f"'{dose_matches[i]}, '{ssd[i]}, "
                f"'{prof[i]}, '{prof_eff[i]}, "
                f"'{fx[i]}, '{fy[i]}"
            )
            output.append(linha)

    return '\n'.join(output)

# Interface do Streamlit
st.title("📄 Processador de PDFs de Teleterapia")
st.markdown("""
Faça upload de um arquivo PDF de planejamento de teleterapia para extrair os dados estruturados.
""")

uploaded_file = st.file_uploader("Escolha um arquivo PDF", type="pdf")

if uploaded_file is not None:
    try:
        # Ler o conteúdo do PDF
        pdf_reader = PyPDF2.PdfReader(BytesIO(uploaded_file.getvalue()))
        content = ""
        for page in pdf_reader.pages:
            content += page.extract_text()
        
        # Processar o conteúdo
        result = process_pdf_content(content)
        
        # Exibir resultados
        st.success("Arquivo processado com sucesso!")
        
        st.subheader("Dados Extraídos")
        st.text_area("Resultado", result, height=400)
        
        # Opção para download dos resultados
        st.download_button(
            label="Baixar Resultados",
            data=result,
            file_name="dados_teleterapia.txt",
            mime="text/plain"
        )
        
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {str(e)}")
