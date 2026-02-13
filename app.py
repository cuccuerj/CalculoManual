import streamlit as st
import PyPDF2
import pandas as pd
import re
from io import BytesIO

class TeletherapyExtractor:
    def __init__(self, content: str):
        self.raw_content = content or ""
        # Limpa o texto: substitui quebras por espaços e normaliza espaços múltiplos
        self.clean_content = ' '.join(self.raw_content.split())

    def _extract_regex(self, pattern, content_block=None, group=1, find_all=False):
        target = content_block if content_block else self.clean_content
        try:
            if find_all:
                return re.findall(pattern, target, re.IGNORECASE | re.DOTALL)
            match = re.search(pattern, target, re.IGNORECASE | re.DOTALL)
            return match.group(group).strip() if match else None
        except:
            return None

    def _get_block(self, start_marker, end_marker):
        pattern = fr'{re.escape(start_marker)}(.*?){re.escape(end_marker)}'
        return self._extract_regex(pattern, group=1)

    def process(self):
        c = self.clean_content

        # Dados do paciente
        nome = self._extract_regex(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)')
        matricula = self._extract_regex(r'Matricula:\s*(\d+)')
        curso = self._extract_regex(r'Curso:\s*(\w+)')
        plano = self._extract_regex(r'Plano:\s*(\w+)')

        # Unidade de tratamento e energia
        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # Identifica campos e energias
        campos_raw = re.findall(r'Campo (\d+)\s+(\d+X)', c)
        energias_campos = [item[1] for item in campos_raw]
        num_campos = len(energias_campos)

        # Extrai blocos de parâmetros
        block_x = self._get_block('Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
        block_y = self._get_block('Tamanho do Campo Aberto Y', 'Jaw Y1')
        block_jaw_y1 = self._get_block('Jaw Y1', 'Jaw Y2')
        block_jaw_y2 = self._get_block('Jaw Y2', 'Filtro')
        block_filtros = self._get_block('Filtro', 'MU')
        block_mu = self._get_block('MU', 'Dose')
        block_dose = self._get_block('Dose', 'SSD')  # Pode não existir, usaremos regex global depois
        block_ssd = self._get_block('SSD', 'Profundidade')
        block_prof = self._get_block('Profundidade', 'Profundidade Efetiva')
        block_prof_eff = self._get_block('Profundidade Efetiva', 'Informações do Campo')
        if not block_prof_eff:
            block_prof_eff = self._get_block('Profundidade Efetiva', 'Campo 1')

        # Função auxiliar para extrair valores numéricos de um bloco
        def get_vals(block, regex):
            return re.findall(regex, block) if block else []

        # Extrai valores de cada parâmetro
        x_sizes = get_vals(block_x, r'Campo \d+\s*([\d.]+)\s*cm')
        y_sizes = get_vals(block_y, r'Campo \d+\s*([\d.]+)\s*cm')
        jaw_y1 = get_vals(block_jaw_y1, r'Y1:\s*([+-]?\d+\.\d+)')
        jaw_y2 = get_vals(block_jaw_y2, r'Y2:\s*([+-]?\d+\.\d+)')
        filtros = get_vals(block_filtros, r'Campo \d+\s*([-\w]+)')
        um_vals = get_vals(block_mu, r'Campo \d+\s*([\d.]+)\s*MU')
        dose_vals = re.findall(r'Campo \d+\s+([\d.]+)\s*cGy', c)  # fallback global
        ssd_vals = get_vals(block_ssd, r'Campo \d+\s*([\d.]+)\s*cm')
        prof_vals = get_vals(block_prof, r'Campo \d+\s*([\d.]+)\s*cm')
        prof_eff_vals = get_vals(block_prof_eff, r'Campo \d+\s*([\d.]+)\s*cm')

        # Extrai FSX/FSY da fluência total (ignora a linha de CBSF)
        fluencia_matches = []
        # Padrão inglês
        pattern_en = re.findall(
            r'determined from the total fluence:\s*fsx\s*=\s*(\d+)\s*mm\s*,\s*fsy\s*=\s*(\d+)\s*mm',
            c, re.IGNORECASE
        )
        # Padrão português
        pattern_pt = re.findall(
            r'determinado a partir da flu[eê]ncia total:\s*fsx\s*=\s*(\d+)\s*mm\s*,\s*fsy\s*=\s*(\d+)\s*mm',
            c, re.IGNORECASE
        )
        fluencia_matches = pattern_en + pattern_pt

        # Monta os dados do paciente para exibição
        paciente_info = {
            "Nome": nome if nome else "N/A",
            "Matrícula": matricula if matricula else "N/A",
            "Curso": curso if curso else "N/A",
            "Plano": plano if plano else "N/A",
            "Unidade": unidade,
            "Energia (geral)": energia_unidade
        }

        # Prepara os dados tabulares
        table_data = []
        for i in range(num_campos):
            def safe(lst, idx, default="N/A"):
                return lst[idx] if idx < len(lst) else default

            # Verifica se há filtro (valores diferentes de '-')
            tem_filtro = False
            if i < len(filtros) and filtros[i] not in ('-', 'nan', ''):
                tem_filtro = True

            # FSX/FSY só são extraídos se não houver filtro
            fsx_val, fsy_val = "-", "-"
            if not tem_filtro and fluencia_matches:
                if i < len(fluencia_matches):
                    fsx_val, fsy_val = fluencia_matches[i]
                else:
                    fsx_val, fsy_val = fluencia_matches[-1]  # fallback

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
                fsx_val,
                fsy_val
            ]
            table_data.append(row)

        # Cria DataFrame
        columns = [
            "Energia", "X (cm)", "Y (cm)", "Y1 (cm)", "Y2 (cm)",
            "Filtro", "MU", "Dose (cGy)", "SSD (cm)", "Prof (cm)",
            "Prof Ef (cm)", "FSX (mm)", "FSY (mm)"
        ]
        df = pd.DataFrame(table_data, columns=columns)

        # Texto simples para download (formato antigo, mantido para compatibilidade)
        output_lines = [f"Nome: {paciente_info['Nome']} | Matrícula: {paciente_info['Matrícula']}"]
        for row in table_data:
            output_lines.append(", ".join([str(x) for x in row]))
        result_text = "\n".join(output_lines)

        return result_text, df, paciente_info

def process_pdf(uploaded_file):
    if uploaded_file is None:
        return None, None, None

    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = "\n".join([p.extract_text() or "" for p in reader.pages])
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return None, None, None

    extractor = TeletherapyExtractor(full_text)
    text, df, paciente_info = extractor.process()
    return text, df, paciente_info

def display_results(df, paciente_info, key_suffix=""):
    """Exibe os resultados de forma organizada e botões de download."""
    if df is None or df.empty:
        st.warning("Nenhum dado extraído.")
        return

    # Informações do paciente
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Paciente", paciente_info["Nome"])
    with col2:
        st.metric("Matrícula", paciente_info["Matrícula"])
    with col3:
        st.metric("Curso", paciente_info["Curso"])
    with col4:
        st.metric("Plano", paciente_info["Plano"])

    # Tabela de dados
    st.subheader("📊 Parâmetros dos Campos")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Botões de download
    col_csv, col_txt = st.columns(2)
    with col_csv:
        csv = df.to_csv(index=False, sep=';').encode('utf-8')
        st.download_button(
            label="📥 Baixar CSV (para planilhas)",
            data=csv,
            file_name=f"{paciente_info['Nome']}_dados.csv",
            mime="text/csv",
            key=f"csv_{key_suffix}"
        )
    with col_txt:
        # Gera um texto simples para download
        txt_lines = [f"Nome: {paciente_info['Nome']} | Matrícula: {paciente_info['Matrícula']}"]
        for _, row in df.iterrows():
            txt_lines.append(", ".join([str(v) for v in row.values]))
        txt_data = "\n".join(txt_lines)
        st.download_button(
            label="📥 Baixar TXT (simples)",
            data=txt_data,
            file_name=f"{paciente_info['Nome']}_dados.txt",
            mime="text/plain",
            key=f"txt_{key_suffix}"
        )

# Interface Streamlit
st.set_page_config(page_title="Extrator de Teleterapia", layout="wide")
st.title("🏥 Processador de Planejamento de Teleterapia")
st.markdown("Extraia automaticamente dados de PDFs de planejamento clínico e exporte para planilhas.")

# Abas
tab1, tab2 = st.tabs(["📄 Arquivo Único", "📄📄 Comparar Dois Arquivos"])

with tab1:
    st.subheader("Processar um arquivo PDF")
    uploaded_file = st.file_uploader("Selecione o arquivo PDF", type=["pdf"], key="single_file")

    if uploaded_file is not None:
        if st.button("Processar", key="btn_single"):
            with st.spinner("Processando PDF..."):
                text, df, paciente_info = process_pdf(uploaded_file)
                if df is not None:
                    st.success("✅ Processamento concluído!")
                    display_results(df, paciente_info, key_suffix="single")
                else:
                    st.error("❌ Falha ao processar o arquivo.")

with tab2:
    st.subheader("Comparar dois arquivos PDF")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Arquivo 1**")
        file1 = st.file_uploader("Selecione o primeiro PDF", type=["pdf"], key="file1")
    with col2:
        st.markdown("**Arquivo 2**")
        file2 = st.file_uploader("Selecione o segundo PDF", type=["pdf"], key="file2")

    if file1 and file2:
        if st.button("Processar Ambos", key="btn_dual"):
            with st.spinner("Processando PDFs..."):
                text1, df1, info1 = process_pdf(file1)
                text2, df2, info2 = process_pdf(file2)

                if df1 is not None and df2 is not None:
                    st.success("✅ Processamento concluído!")

                    # Exibe lado a lado
                    colA, colB = st.columns(2)
                    with colA:
                        st.markdown(f"### 📄 Arquivo 1: {info1['Nome']}")
                        display_results(df1, info1, key_suffix="dual1")
                    with colB:
                        st.markdown(f"### 📄 Arquivo 2: {info2['Nome']}")
                        display_results(df2, info2, key_suffix="dual2")
                else:
                    st.error("❌ Erro ao processar um ou ambos os arquivos.")
    elif file1 or file2:
        st.info("ℹ️ Selecione ambos os arquivos para comparar.")
