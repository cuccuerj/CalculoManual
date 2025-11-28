import streamlit as st
import re
import PyPDF2
import pandas as pd

# ===== Configuração da Página =====
st.set_page_config(
    page_title="Processador de Teleterapia",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ===== CSS Global =====
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }

    .main-card {
        background-color: white;
        padding: 2rem;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        margin-top: 2rem;
        max-width: 900px;
        margin-left: auto;
        margin-right: auto;
    }

    h1 {
        color: #0e3b5e;
        font-weight: 700;
        font-size: 2.1rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        color: #6c757d;
        font-size: 0.98rem;
        margin-bottom: 1.5rem;
    }

    /* ===== Esconde COMPLETAMENTE o uploader nativo ===== */
    [data-testid="stFileUploader"] {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        z-index: -1 !important;
    }

    /* ===== Botão 100% novo (não parece com o padrão do Streamlit) ===== */
    .custom-upload {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        background: linear-gradient(135deg, #0e3b5e, #007EA7);
        color: #ffffff;
        border: none;
        border-radius: 12px;
        padding: 14px 18px;
        font-size: 1rem;
        font-weight: 700;
        cursor: pointer;
        box-shadow: 0 6px 16px rgba(0,0,0,0.16);
        transition: transform 0.08s ease, box-shadow 0.25s ease, filter 0.25s ease;
        user-select: none;
    }
    .custom-upload:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(0,0,0,0.20);
        filter: brightness(1.03);
    }
    .custom-upload:active {
        transform: translateY(0);
        box-shadow: 0 6px 16px rgba(0,0,0,0.16);
        filter: brightness(0.98);
    }
    .custom-upload .icon-wrap {
        display: grid;
        place-items: center;
        width: 34px;
        height: 34px;
        background: rgba(255,255,255,0.18);
        border-radius: 10px;
    }
    .custom-upload .label-wrap {
        display: flex;
        flex-direction: column;
        line-height: 1.1;
    }
    .custom-upload .label-main {
        letter-spacing: 0.3px;
    }
    .custom-upload .label-sub {
        font-size: 0.78rem;
        font-weight: 600;
        opacity: 0.85;
    }

    /* Nome do arquivo selecionado */
    .file-name {
        margin-top: 10px;
        font-weight: 700;
        color: #0e3b5e;
        text-align: center;
    }

    /* Botões de download */
    .stDownloadButton button {
        background-color: white;
        color: #007EA7;
        border: 2px solid #007EA7;
        border-radius: 8px;
        font-weight: 700;
        transition: all 0.25s ease;
    }
    .stDownloadButton button:hover {
        background-color: #007EA7;
        color: white;
    }

    .stTextArea textarea {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.9rem;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ===== JS: Clicar no botão custom aciona o input do uploader nativo =====
st.markdown("""
<script>
function triggerUploader() {
    const uploader = window.parent.document.querySelector('[data-testid="stFileUploader"] input[type="file"]');
    if (uploader) { uploader.click(); }
}
</script>
""", unsafe_allow_html=True)

# ===== Lógica de Processamento =====
class TeletherapyExtractor:
    def __init__(self, content: str):
        self.raw_content = content
        self.clean_content = ' '.join(content.split())

    def _extract_regex(self, pattern, content_block=None, group=1, find_all=False):
        target = content_block if content_block else self.clean_content
        try:
            if find_all:
                return re.findall(pattern, target)
            match = re.search(pattern, target, re.IGNORECASE | re.DOTALL)
            return match.group(group).strip() if match else None
        except:
            return None

    def _get_block(self, start_marker, end_marker):
        pattern = fr'{re.escape(start_marker)}(.*?){re.escape(end_marker)}'
        return self._extract_regex(pattern, group=1)

    def process(self):
        c = self.clean_content

        nome = self._extract_regex(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)')
        matricula = self._extract_regex(r'Matricula:\s*(\d+)')

        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        campos_raw = re.findall(r'Campo (\d+)\s+(\d+X)', c)
        energias_campos = [item[1] for item in campos_raw]
        num_campos = len(energias_campos)

        block_x = self._get_block('Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
        block_y = self._get_block('Tamanho do Campo Aberto Y', 'Jaw Y1')
        block_jaw_y1 = self._get_block('Jaw Y1', 'Jaw Y2')
        block_jaw_y2 = self._get_block('Jaw Y2', 'Filtro')
        block_filtros = self._get_block('Filtro', 'MU')
        block_mu = self._get_block('MU', 'Dose')

        def get_vals(block, regex):
            return re.findall(regex, block) if block else []

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
        if not block_eff:
            block_eff = self._get_block('Profundidade Efetiva', 'Campo 1')
        prof_eff_vals = get_vals(block_eff, r'Campo \d+\s*([\d.]+)\s*cm')

        fluencia_matches = re.findall(
            r'flu[eê]ncia\s+total.*?fsx\s*[a-zA-Z]*\s*=\s*([\d\.]+)\s*mm,\s*fsy\s*[a-zA-Z]*\s*=\s*([\d\.]+)\s*mm',
            c, re.IGNORECASE | re.DOTALL
        )

        output_lines = []
        if nome:
            output_lines.append(f"Nome, do, Paciente:, {', '.join(nome.split())}")
        if matricula:
            output_lines.append(f"Matricula:, '{matricula}'")
        if unidade != "N/A":
            output_lines.append(f"Informações:, 'Unidade, 'de, 'tratamento:, '{unidade},, 'energia:, '{energia_unidade}'")

        table_data = []
        for i in range(num_campos):
            def safe(lst, idx, p="'"):
                return f"{p}{lst[idx]}" if idx < len(lst) else "'N/A"

            f_x_val, f_y_val = "'-", "'-"
            has_filtro = False
            if i < len(filtros) and filtros[i] != '-' and str(filtros[i]).lower() != 'nan':
                has_filtro = True

            if not has_filtro:
                fsx, fsy = None, None
                if len(fluencia_matches) == num_campos:
                    fsx, fsy = fluencia_matches[i]
                elif fluencia_matches:
                    fsx, fsy = fluencia_matches[-1]
                if fsx:
                    f_x_val, f_y_val = f"'{fsx}", f"'{fsy}"

            row = [
                safe(energias_campos, i, ""),
                safe(x_sizes, i),
                safe(y_sizes, i),
                safe(jaw_y1, i),
                safe(jaw_y2, i),
                safe(filtros, i),
                safe(um_vals, i),
                safe(dose_vals, i),
                safe(ssd_vals, i),
                safe(prof_vals, i),
                safe(prof_eff_vals, i),
                f_x_val,
                f_y_val
            ]
            output_lines.append(", ".join(row))
            table_data.append([r.replace("'", "") for r in row])

        df = pd.DataFrame(table_data, columns=[
            "Energia", "X", "Y", "Y1", "Y2", "Filtro", "MU", "Dose", "SSD", "Prof", "P.Ef", "FSX", "FSY"
        ])
        return "\n".join(output_lines), df, nome

# ===== Interface =====
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown("<h1>Processador de Teleterapia</h1>", unsafe_allow_html=True)
st.markdown('<div class="subtitle">Extração automática de dados de planejamento clínico</div>', unsafe_allow_html=True)

# Uploader nativo escondido (para funcionalidade real)
uploaded_file = st.file_uploader(" ", type=["pdf"])

# Botão custom que não tem nada a ver com o padrão
st.markdown("""
<div style="display:flex; justify-content:center; margin-bottom: 8px;">
    <button class="custom-upload" onclick="triggerUploader()">
        <span class="icon-wrap">📄</span>
        <span class="label-wrap">
            <span class="label-main">Carregar arquivo PDF</span>
            <span class="label-sub">Clique para selecionar</span>
        </span>
    </button>
</div>
""", unsafe_allow_html=True)

# Feedback quando arquivo é carregado
if uploaded_file:
    st.markdown(f'<div class="file-name">✅ Arquivo carregado: {uploaded_file.name}</div>', unsafe_allow_html=True)

    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = "\n".join([page.extract_text() or "" for page in reader.pages])

        extractor = TeletherapyExtractor(full_text)
        result_text, df, nome_paciente = extractor.process()

        st.markdown("---")

        col_res1, col_res2 = st.columns([2, 1])

        with col_res1:
            st.subheader("📋 Pré-visualização dos dados")
            st.dataframe(df, use_container_width=True, hide_index=True)

        with col_res2:
            st.subheader("💾 Exportação")
            st.info(f"Paciente: **{nome_paciente if nome_paciente else 'Desconhecido'}**")

            file_name = f"teleterapia_{(nome_paciente or 'desconhecido').replace(' ', '_')}.txt"
            st.download_button(
                label="Baixar TXT formatado",
                data=result_text,
                file_name=file_name,
                mime="text/plain",
                use_container_width=True
            )

        with st.expander("Ver texto bruto gerado (copiar e colar)"):
            st.text_area("Resultado", value=result_text, height=220, label_visibility="collapsed")

    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")

st.markdown('</div>', unsafe_allow_html=True)
