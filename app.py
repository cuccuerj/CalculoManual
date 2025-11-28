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

# ===== CSS: Uploader com visual de botão minimalista =====
st.markdown("""
<style>
    /* Fundo e card */
    .stApp { background-color: #f5f7fb; }
    .main-card {
        background-color: #ffffff;
        padding: 2rem;
        border-radius: 16px;
        box-shadow: 0 6px 24px rgba(17, 24, 39, 0.06);
        margin: 3rem auto 2rem auto;
        max-width: 880px;
    }

    /* Títulos */
    h1 {
        color: #0e3b5e;
        font-weight: 750;
        font-size: 2.05rem;
        text-align: center;
        margin: 0 0 .35rem 0;
    }
    .subtitle {
        text-align: center;
        color: #6c757d;
        font-size: .98rem;
        margin-bottom: 1.6rem;
    }

    /* Wrapper do uploader para centralizar */
    .uploader-wrapper {
        display: flex;
        justify-content: center;
        margin: .4rem 0 1rem 0;
    }

    /* Remove label padrão e textos internos redundantes */
    [data-testid="stFileUploader"] label { display: none !important; }
    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploader"] ul,
    [data-testid="stFileUploader"] section > div:first-child {
        display: none !important;
    }

    /* Área clicável vira botão minimalista */
    [data-testid="stFileUploader"] section {
        background: #ffffff;
        color: #0e3b5e;
        border: 2px solid #0e86c7; /* azul suave */
        border-radius: 12px;
        min-height: 52px;
        min-width: 280px;
        padding: 0 18px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        cursor: pointer;
        font-weight: 700;
        font-size: 1rem;
        transition: border-color .2s ease, box-shadow .2s ease, transform .06s ease, background .2s ease;
        box-shadow: 0 2px 10px rgba(14, 134, 199, 0.08);
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #0b6fa2;
        box-shadow: 0 6px 18px rgba(14, 134, 199, 0.14);
        transform: translateY(-1px);
        background: #fbfdff;
    }
    [data-testid="stFileUploader"] section:active {
        transform: translateY(0);
        box-shadow: 0 3px 10px rgba(14, 134, 199, 0.10);
    }

    /* Ícone e rótulo personalizados */
    [data-testid="stFileUploader"] section::before {
        content: "📄";
        display: inline-block;
        width: 34px;
        height: 34px;
        border-radius: 10px;
        background: #eaf6fd;
        color: #0b6fa2;
        display: grid;
        place-items: center;
        font-size: 1.1rem;
    }
    [data-testid="stFileUploader"] section::after {
        content: "Selecionar PDF";
        display: inline-block;
        letter-spacing: .2px;
    }

    /* Nome do arquivo carregado */
    .file-name {
        margin-top: 8px;
        font-weight: 700;
        color: #0e3b5e;
        text-align: center;
    }

    /* Botões de download coerentes com o tema */
    .stDownloadButton button {
        background-color: #ffffff;
        color: #0b6fa2;
        border: 2px solid #0b6fa2;
        border-radius: 10px;
        font-weight: 700;
        transition: all .2s ease;
    }
    .stDownloadButton button:hover {
        background-color: #0b6fa2;
        color: #ffffff;
    }

    /* Dataframe e textarea */
    .stDataFrame { border-radius: 12px; overflow: hidden; }
    .stTextArea textarea {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: .92rem;
        background-color: #f9fbfd;
        border: 1px solid #e3e8ef;
        border-radius: 10px;
    }
</style>
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

# Uploader centralizado com visual minimalista
st.markdown('<div class="uploader-wrapper">', unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["pdf"], label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

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
