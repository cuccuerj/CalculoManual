import streamlit as st
import re
import PyPDF2
from io import BytesIO
import pandas as pd

# ===== Configuração da Página =====
st.set_page_config(
    page_title="Processador de Teleterapia",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ===== CSS Premium e Limpo (Ajustado) =====
st.markdown("""
<style>
    /* Fundo geral */
    .stApp {
        background-color: #f0f2f6;
    }

    /* Container Principal (Card Effect) */
    .main-card {
        background-color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        margin-top: 2rem;
    }

    /* Títulos */
    h1 {
        color: #0e3b5e;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 700;
        font-size: 2.2rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        color: #6c757d;
        font-size: 1rem;
        margin-bottom: 2.5rem;
    }

    /* --- HACK SUPREMO DO UPLOADER --- */
    
    /* 1. Esconde o texto "Drag and drop file here", o ícone de nuvem e a caixa branca interna. */
    /* Target: O primeiro div dentro da seção que contém o ícone e o texto de arrastar e soltar. */
    [data-testid='stFileUploader'] section > div:first-child {
        display: none !important; 
    }
    
    /* 2. Esconde o texto chato "Limit 200MB per file" e qualquer texto pequeno de aviso. */
    [data-testid='stFileUploader'] section + div, 
    [data-testid='stFileUploader'] small {
        display: none !important;
    }

    /* 3. Estiliza a área clicável para parecer um botão Sólido */
    [data-testid='stFileUploader'] section {
        background-color: #007EA7; /* Azul Hospitalar */
        color: white;
        border: none;
        border-radius: 50px; /* Bordas totalmente redondas */
        height: 55px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 126, 167, 0.2);
        /* Garante que o conteúdo que está sendo forçado a aparecer fique no centro */
        padding: 0; 
        margin: 0;
    }

    /* 4. Efeito Hover */
    [data-testid='stFileUploader'] section:hover {
        background-color: #005f7f;
        transform: translateY(-2px);
        box-shadow: 0 6px 10px rgba(0, 126, 167, 0.3);
    }

    /* 5. Insere o texto novo no botão, garantindo que ele sobrescreva qualquer outro conteúdo */
    [data-testid='stFileUploader'] section::after {
        content: "📄 Carregar Arquivo PDF";
        font-weight: 600;
        font-size: 1.1rem;
        letter-spacing: 0.5px;
        /* Força a centralização, caso o layout interno tenha sido afetado */
        display: block; 
        width: 100%;
        text-align: center;
    }
    
    /* 6. Quando o arquivo está carregado, remove a lista feia de arquivos */
    [data-testid='stFileUploader'] ul {
        display: none; 
    }

    /* Estilo dos Botões de Download */
    .stDownloadButton button {
        background-color: white;
        color: #007EA7;
        border: 2px solid #007EA7;
        border-radius: 8px;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stDownloadButton button:hover {
        background-color: #007EA7;
        color: white;
    }

    /* Text Area Style */
    .stTextArea textarea {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.9rem;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)

# ===== Lógica de Processamento (Mantida a versão corrigida) =====
class TeletherapyExtractor:
    def __init__(self, content):
        self.raw_content = content
        self.clean_content = ' '.join(content.split())

    def _extract_regex(self, pattern, content_block=None, group=1, find_all=False):
        target = content_block if content_block else self.clean_content
        try:
            if find_all: return re.findall(pattern, target)
            match = re.search(pattern, target, re.IGNORECASE | re.DOTALL)
            return match.group(group).strip() if match else None
        except: return None

    def _get_block(self, start_marker, end_marker):
        pattern = fr'{re.escape(start_marker)}(.*?){re.escape(end_marker)}'
        return self._extract_regex(pattern, group=1)

    def process(self):
        c = self.clean_content
        
        # Extrações Básicas
        nome = self._extract_regex(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)')
        matricula = self._extract_regex(r'Matricula:\s*(\d+)')
        
        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # Campos
        campos_raw = re.findall(r'Campo (\d+)\s+(\d+X)', c)
        energias_campos = [item[1] for item in campos_raw]
        num_campos = len(energias_campos)

        # Blocos
        block_x = self._get_block('Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
        block_y = self._get_block('Tamanho do Campo Aberto Y', 'Jaw Y1')
        block_jaw_y1 = self._get_block('Jaw Y1', 'Jaw Y2')
        block_jaw_y2 = self._get_block('Jaw Y2', 'Filtro')
        block_filtros = self._get_block('Filtro', 'MU')
        block_mu = self._get_block('MU', 'Dose')
        
        def get_vals(block, regex): return re.findall(regex, block) if block else []

        x_sizes = get_vals(block_x, r'Campo \d+\s*([\d.]+)\s*cm')
        y_sizes = get_vals(block_y, r'Campo \d+\s*([\d.]+)\s*cm')
        jaw_y1 = get_vals(block_jaw_y1, r'Y1:\s*([+-]?\d+\.\d+)')
        jaw_y2 = get_vals(block_jaw_y2, r'Y2:\s*([+-]?\d+\.\d+)')
        filtros = get_vals(block_filtros, r'Campo \d+\s*([-\w]+)')
        um_vals = get_vals(block_mu, r'Campo \d+\s*([\d.]+)\s*MU')
        dose_vals = re.findall(r'Campo \d+\s+([\d.]+)\s*cGy', c)
        
        block_ssd = self._get_block('SSD', 'Profundidade')
        ssd_vals = get_vals(block_ssd, r'Campo \d+\s*([\d.]+)\s*cm')
        
        block_prof = self._get_block('Profundidade', 'Profundidade Efetiva')
        prof_vals = get_vals(block_prof, r'Campo \d+\s*([\d.]+)\s*cm')
        
        block_eff = self._get_block('Profundidade Efetiva', 'Informações do Campo')
        if not block_eff: block_eff = self._get_block('Profundidade Efetiva', 'Campo 1')
        prof_eff_vals = get_vals(block_eff, r'Campo \d+\s*([\d.]+)\s*cm')

        # Fluência Tolerante a Falhas
        fluencia_matches = re.findall(
            r'flu[eê]ncia\s+total.*?fsx\s*[a-zA-Z]*\s*=\s*([\d\.]+)\s*mm,\s*fsy\s*[a-zA-Z]*\s*=\s*([\d\.]+)\s*mm', 
            c, re.IGNORECASE | re.DOTALL
        )

        output_lines = []
        if nome: output_lines.append(f"Nome, do, Paciente:, {', '.join(nome.split())}")
        if matricula: output_lines.append(f"Matricula:, '{matricula}'")
        if unidade != "N/A": output_lines.append(f"Informações:, 'Unidade, 'de, 'tratamento:, '{unidade},, 'energia:, '{energia_unidade}'")

        table_data = []

        for i in range(num_campos):
            def safe(lst, idx, p="'"): return f"{p}{lst[idx]}" if idx < len(lst) else "'N/A"
            
            # Lógica Fluência
            f_x_val, f_y_val = "'-", "'-"
            has_filtro = False
            if i < len(filtros) and filtros[i] != '-' and filtros[i].lower() != 'nan':
                has_filtro = True
            
            if not has_filtro:
                fsx, fsy = None, None
                if len(fluencia_matches) == num_campos: fsx, fsy = fluencia_matches[i]
                elif fluencia_matches: fsx, fsy = fluencia_matches[-1]
                
                if fsx: f_x_val, f_y_val = f"'{fsx}", f"'{fsy}"

            row = [
                safe(energias_campos, i, ""), safe(x_sizes, i), safe(y_sizes, i),
                safe(jaw_y1, i), safe(jaw_y2, i), safe(filtros, i), safe(um_vals, i),
                safe(dose_vals, i), safe(ssd_vals, i), safe(prof_vals, i),
                safe(prof_eff_vals, i), f_x_val, f_y_val
            ]
            output_lines.append(", ".join(row))
            table_data.append([r.replace("'", "") for r in row])

        return "\n".join(output_lines), pd.DataFrame(table_data, columns=[
            "Energia", "X", "Y", "Y1", "Y2", "Filtro", "MU", "Dose", "SSD", "Prof", "P.Ef", "FSX", "FSY"
        ]), nome

# ===== Interface do Usuário =====

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown("<h1>Processador de Teleterapia</h1>", unsafe_allow_html=True)
st.markdown('<div class="subtitle">Extração automática de dados de planejamento clínico</div>', unsafe_allow_html=True)

# Uploader Limpo
uploaded_file = st.file_uploader("", type="pdf")

if uploaded_file:
    # Feedback Visual quando o arquivo é carregado
    st.markdown(f"""
    <div style="text-align:center; margin-top:10px; color:#28a745; font-weight:bold;">
        ✅ Arquivo carregado: **{uploaded_file.name}**
    </div>
    """, unsafe_allow_html=True)
    
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = "\n".join([page.extract_text() for page in reader.pages])
        
        extractor = TeletherapyExtractor(full_text)
        result_text, df, nome_paciente = extractor.process()
        
        st.markdown("---")
        
        # Card de Resultado
        col_res1, col_res2 = st.columns([2, 1])
        
        with col_res1:
            st.subheader("📋 Pré-visualização dos Dados")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
        with col_res2:
            st.subheader("💾 Exportação")
            st.info(f"Paciente: **{nome_paciente if nome_paciente else 'Desconhecido'}**")
            
            file_name = f"teleterapia_{nome_paciente.replace(' ', '_')}.txt" if nome_paciente else "dados.txt"
            st.download_button(
                label="Baixar TXT Formatado",
                data=result_text,
                file_name=file_name,
                mime="text/plain",
                use_container_width=True
            )
            
        with st.expander("Ver texto bruto gerado (Copiar e Colar)"):
            st.text_area("Resultado", value=result_text, height=200, label_visibility="collapsed")

    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")

st.markdown('</div>', unsafe_allow_html=True) # Fecha Card

Would you like me to upload these files to the Streamlit app for you to test the new design, or is the code sufficient?
