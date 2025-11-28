import streamlit as st
import re
import PyPDF2
from io import BytesIO
import pandas as pd

# ===== Configuração da Página =====
st.set_page_config(
    page_title="Processador de Teleterapia",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== CSS Moderno e Customização do Uploader =====
st.markdown("""
<style>
    /* Estilo Geral */
    .main {
        background-color: #f8f9fa;
    }
    h1 {
        color: #2c3e50;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 700;
        text-align: center;
    }
    h3 {
        color: #7f8c8d;
        font-size: 1.1rem;
        text-align: center;
        margin-bottom: 2rem;
    }

    /* --- Customização AVANÇADA do File Uploader para parecer um botão --- */
    [data-testid='stFileUploader'] {
        width: 100%;
        max-width: 400px;
        margin: 0 auto;
    }
    
    [data-testid='stFileUploader'] section {
        padding: 0;
        background-color: #3498db;
        border: none;
        border-radius: 8px;
        transition: background-color 0.3s;
        height: 60px; /* Altura do botão */
        display: flex;
        align-items: center;
        justify-content: center;
    }

    [data-testid='stFileUploader'] section:hover {
        background-color: #2980b9; /* Cor ao passar o mouse */
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Esconde o ícone e texto padrão feios do Streamlit */
    [data-testid='stFileUploader'] section > button {
        display: none;
    }
    [data-testid='stFileUploader'] section span {
        display: none;
    }
    
    /* Cria o texto do botão via CSS */
    [data-testid='stFileUploader'] section::after {
        content: "📂 Carregar PDF de Tratamento";
        color: white;
        font-weight: bold;
        font-size: 1rem;
        pointer-events: none;
    }

    /* Pequeno texto de ajuda abaixo do botão */
    .upload-help {
        text-align: center;
        font-size: 0.8rem;
        color: #95a5a6;
        margin-top: -10px;
        margin-bottom: 20px;
    }

    /* Caixas de resultado */
    .result-area {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e1e4e8;
    }
    
    .stTextArea textarea {
        font-family: 'Courier New', monospace;
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)

# ===== Classe de Processamento =====
class TeletherapyExtractor:
    def __init__(self, content):
        self.raw_content = content
        # Normaliza espaços múltiplos para um único espaço
        self.clean_content = ' '.join(content.split())
        self.debug_data = {}

    def _extract_regex(self, pattern, content_block=None, group=1, find_all=False):
        """Função genérica segura para extração via Regex."""
        target = content_block if content_block else self.clean_content
        try:
            if find_all:
                return re.findall(pattern, target)
            match = re.search(pattern, target, re.IGNORECASE | re.DOTALL)
            return match.group(group).strip() if match else None
        except Exception:
            return None

    def _get_block(self, start_marker, end_marker):
        """Extrai um bloco de texto entre dois marcadores."""
        pattern = fr'{re.escape(start_marker)}(.*?){re.escape(end_marker)}'
        return self._extract_regex(pattern, group=1)

    def process(self):
        c = self.clean_content
        data = {}

        # 1. Dados do Paciente
        nome = self._extract_regex(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)')
        matricula = self._extract_regex(r'Matricula:\s*(\d+)')
        
        # 2. Unidade e Energia
        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # 3. Identificação de Campos e Energias
        # Busca padrão "Campo X 6X" ou "Campo X 15X"
        campos_raw = re.findall(r'Campo (\d+)\s+(\d+X)', c)
        energias_campos = [item[1] for item in campos_raw]
        num_campos = len(energias_campos)

        # 4. Extração de Blocos para Parsing
        # Definimos os blocos onde cada informação reside para evitar pegar dados errados
        block_x = self._get_block('Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
        block_y = self._get_block('Tamanho do Campo Aberto Y', 'Jaw Y1')
        block_jaw_y1 = self._get_block('Jaw Y1', 'Jaw Y2')
        block_jaw_y2 = self._get_block('Jaw Y2', 'Filtro')
        block_filtros = self._get_block('Filtro', 'MU')
        
        # Extrações específicas dentro dos blocos
        def get_vals_from_block(block, prefix_regex):
            if not block: return []
            return re.findall(prefix_regex, block)

        x_sizes = get_vals_from_block(block_x, r'Campo \d+\s*([\d.]+)\s*cm')
        y_sizes = get_vals_from_block(block_y, r'Campo \d+\s*([\d.]+)\s*cm')
        jaw_y1 = get_vals_from_block(block_jaw_y1, r'Y1:\s*([+-]?\d+\.\d+)')
        jaw_y2 = get_vals_from_block(block_jaw_y2, r'Y2:\s*([+-]?\d+\.\d+)')
        filtros = get_vals_from_block(block_filtros, r'Campo \d+\s*([-\w]+)')

        # Dados gerais espalhados
        um_vals = re.findall(r'Campo \d+\s+(\d+)\s*UM', c)
        dose_vals = re.findall(r'Campo \d+\s+([\d.]+)\s*cGy', c)
        
        # Blocos finais
        block_ssd = self._get_block('SSD', 'Profundidade')
        ssd_vals = get_vals_from_block(block_ssd, r'Campo \d+\s*([\d.]+)\s*cm')
        
        block_prof = self._get_block('Profundidade', 'Profundidade Efetiva')
        prof_vals = get_vals_from_block(block_prof, r'Campo \d+\s*([\d.]+)\s*cm')
        
        block_eff = self._get_block('Profundidade Efetiva', 'Informações do Campo')
        prof_eff_vals = get_vals_from_block(block_eff, r'Campo \d+\s*([\d.]+)\s*cm')

        # Fluência
        fluencia_match = re.findall(r'flu[eê]ncia\s+total\s*:\s*fsx\s*=\s*([0-9.]+)\s*mm,\s*fsy\s*=\s*([0-9.]+)\s*mm', c, re.IGNORECASE)
        fluencia_fsx, fluencia_fsy = fluencia_match[-1] if fluencia_match else (None, None)

        # ===== Montagem das Linhas de Saída =====
        output_lines = []
        
        # Cabeçalho Paciente (Formatado conforme seu código original com vírgulas extras)
        if nome:
            fmt_nome = ', '.join(nome.split())
            output_lines.append(f"Nome, do, Paciente:, {fmt_nome}")
        if matricula:
            output_lines.append(f"Matricula:, '{matricula}'")
        if unidade != "N/A":
            output_lines.append(f"Informações:, 'Unidade, 'de, 'tratamento:, '{unidade},, 'energia:, '{energia_unidade}'")

        # Dados Tabulares para conferência visual
        table_data = []

        for i in range(num_campos):
            # Função auxiliar para pegar valor com segurança ou retornar 'N/A'
            def safe_get(lst, idx, prefix="'"):
                return f"{prefix}{lst[idx]}" if idx < len(lst) else "'N/A"

            # Lógica da Fluência (baseado no filtro)
            current_filtro = filtros[i] if i < len(filtros) else '-'
            if current_filtro != '-' and fluencia_fsx:
                f_x_val = f"'{fluencia_fsx}"
                f_y_val = f"'{fluencia_fsy}"
            else:
                f_x_val = "'N/A" if fluencia_fsx is None else "'-"
                f_y_val = "'N/A" if fluencia_fsx is None else "'-"
                # Ajuste lógico: Se tem filtro, geralmente não tem fluencia FSX/FSY da mesma forma que campo aberto? 
                # Mantive a lógica original: se filtro != '-', usa '-', senão usa o valor extraído.
                if current_filtro != '-': 
                     f_x_val, f_y_val = "'-", "'-"
                elif fluencia_fsx:
                     f_x_val, f_y_val = f"'{fluencia_fsx}", f"'{fluencia_fsy}"
                else:
                     f_x_val, f_y_val = "'-", "'-"

            row = [
                energias_campos[i],
                safe_get(x_sizes, i),
                safe_get(y_sizes, i),
                safe_get(jaw_y1, i),
                safe_get(jaw_y2, i),
                safe_get(filtros, i),
                safe_get(um_vals, i),
                safe_get(dose_vals, i),
                safe_get(ssd_vals, i),
                safe_get(prof_vals, i),
                safe_get(prof_eff_vals, i),
                f_x_val,
                f_y_val
            ]
            
            output_lines.append(", ".join(row))
            
            # Limpa aspas para a tabela visual
            clean_row = [r.replace("'", "") for r in row]
            table_data.append(clean_row)

        final_text = "\n".join(output_lines)
        
        # Cria dataframe para display
        df = pd.DataFrame(table_data, columns=[
            "Energia", "X Size", "Y Size", "Jaw Y1", "Jaw Y2", "Filtro", 
            "UM", "Dose", "SSD", "Prof", "Prof Eff", "FSX", "FSY"
        ])
        
        return final_text, df, nome

# ===== Layout Principal =====

st.title("🏥 Processador de Teleterapia")
st.markdown("<h3>Converta PDFs de tratamento em dados estruturados</h3>", unsafe_allow_html=True)

# Container do Uploader
with st.container():
    uploaded_file = st.file_uploader("", type="pdf")
    st.markdown('<div class="upload-help">Arraste o arquivo ou clique no botão azul acima</div>', unsafe_allow_html=True)

if uploaded_file is not None:
    try:
        # Leitura do PDF
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
            
        # Processamento
        extractor = TeletherapyExtractor(full_text)
        result_text, df_preview, paciente_nome = extractor.process()
        
        st.divider()
        
        # Colunas para organizar o resultado
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.success("✅ Processamento Concluído!")
            st.markdown(f"**Paciente:** {paciente_nome if paciente_nome else 'Não identificado'}")
        
        with col2:
            # Botão de Download
            file_name = f"teleterapia_{paciente_nome.replace(' ', '_')}.txt" if paciente_nome else "dados_teleterapia.txt"
            st.download_button(
                label="⬇️ Baixar Arquivo .txt",
                data=result_text,
                file_name=file_name,
                mime="text/plain",
                use_container_width=True
            )

        # Aba de visualização
        tab1, tab2 = st.tabs(["📊 Visualização Tabela", "📝 Texto Formatado"])
        
        with tab1:
            st.caption("Conferência dos dados extraídos:")
            st.dataframe(df_preview, use_container_width=True)
            
        with tab2:
            st.caption("Formato final para exportação (Copiável):")
            st.text_area("", value=result_text, height=300, key="final_output")
            
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {str(e)}")
        st.info("Verifique se o PDF é legível e segue o padrão esperado.")
