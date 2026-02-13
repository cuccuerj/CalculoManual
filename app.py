import streamlit as st
import PyPDF2
import pandas as pd
import re

class TeletherapyExtractor:
    def __init__(self, content: str):
        self.raw_content = content or ""
        # Remove espaços extras mas mantém o texto contínuo para buscas simples
        self.clean_content = re.sub(r'\s+', ' ', self.raw_content)
        self.lines = self.raw_content.split('\n')

    def _extract_regex(self, pattern, text=None, group=1, flags=re.IGNORECASE):
        text = text or self.clean_content
        try:
            match = re.search(pattern, text, flags)
            return match.group(group).strip() if match else None
        except:
            return None

    def _extract_all_regex(self, pattern, text=None, flags=re.IGNORECASE):
        text = text or self.clean_content
        return re.findall(pattern, text, flags)

    def process(self):
        c = self.clean_content

        # Dados do paciente
        nome = self._extract_regex(r'Nome do Paciente:\s*(.+?)(?=\s+Matricula)')
        matricula = self._extract_regex(r'Matricula:\s*(\d+)')
        curso = self._extract_regex(r'Curso:\s*(\w+)')
        plano = self._extract_regex(r'Plano:\s*(\w+)')

        # Unidade
        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # Campos e energias
        campos_raw = re.findall(r'Campo (\d+)\s+(\d+X)', c)
        energias_campos = [item[1] for item in campos_raw]
        num_campos = len(energias_campos)

        # Função auxiliar para extrair lista de valores com flags opcionais
        def extract_values(pattern, flags=0):
            return re.findall(pattern, c, flags)

        # Extração dos parâmetros
        x_sizes = extract_values(r'Campo \d+\s+([\d.]+)\s*cm(?=\s+Campo|\s*$)')
        y_sizes = extract_values(r'Tamanho do Campo Aberto Y.*?Campo \d+\s+([\d.]+)\s*cm', re.DOTALL)
        jaw_y1 = extract_values(r'Jaw Y1.*?Y1:\s*([+-]?\d+\.\d+)', re.DOTALL)
        jaw_y2 = extract_values(r'Jaw Y2.*?Y2:\s*([+-]?\d+\.\d+)', re.DOTALL)
        filtros = extract_values(r'Filtro.*?Campo \d+\s+([-\w]+)', re.DOTALL)
        um_vals = extract_values(r'MU.*?Campo \d+\s+([\d.]+)\s*MU', re.DOTALL)
        dose_vals = extract_values(r'Dose.*?Campo \d+\s+([\d.]+)\s*cGy', re.DOTALL)
        ssd_vals = extract_values(r'SSD.*?Campo \d+\s+([\d.]+)\s*cm', re.DOTALL)
        prof_vals = extract_values(r'Profundidade\s+(?!Efetiva).*?Campo \d+\s+([\d.]+)\s*cm', re.DOTALL)
        prof_eff_vals = extract_values(r'Profundidade Efetiva.*?Campo \d+\s+([\d.]+)\s*cm', re.DOTALL)

        # Extração de FSX e FSY da fluência total
        fluencia_matches = []
        # Padrão em português (com "ê" ou "e")
        pattern_pt = r'determinado a partir da flu[eê]ncia total:\s*fsx\s*=\s*(\d+)\s*mm\s*,\s*fsy\s*=\s*(\d+)\s*mm'
        # Padrão em inglês
        pattern_en = r'determined from the total fluence:\s*fsx\s*=\s*(\d+)\s*mm\s*,\s*fsy\s*=\s*(\d+)\s*mm'

        # Primeiro tenta no texto limpo
        fluencia_matches = re.findall(pattern_pt, c, re.IGNORECASE) + re.findall(pattern_en, c, re.IGNORECASE)

        # Se não achou, tenta linha a linha
        if not fluencia_matches:
            for line in self.lines:
                match_pt = re.search(pattern_pt, line, re.IGNORECASE)
                if match_pt:
                    fluencia_matches.append(match_pt.groups())
                match_en = re.search(pattern_en, line, re.IGNORECASE)
                if match_en:
                    fluencia_matches.append(match_en.groups())

        # Para debug: mostrar o que foi encontrado (pode remover depois)
        if fluencia_matches:
            st.write("**Debug:** Fluência total encontrada:", fluencia_matches)
        else:
            st.write("**Debug:** Nenhuma fluência total encontrada.")

        # Associa FSX/FSY a cada campo (ordem presumida)
        fsx_list = []
        fsy_list = []
        for i in range(num_campos):
            if i < len(fluencia_matches):
                fsx_list.append(fluencia_matches[i][0])
                fsy_list.append(fluencia_matches[i][1])
            else:
                fsx_list.append("-")
                fsy_list.append("-")

        # Informações do paciente
        paciente_info = {
            "Nome": nome if nome else "N/A",
            "Matrícula": matricula if matricula else "N/A",
            "Curso": curso if curso else "N/A",
            "Plano": plano if plano else "N/A",
            "Unidade": unidade,
            "Energia (geral)": energia_unidade
        }

        # Monta tabela
        table_data = []
        for i in range(num_campos):
            def safe(lst, idx, default="N/A"):
                return lst[idx] if idx < len(lst) else default

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
                safe(fsx_list, i),
                safe(fsy_list, i)
            ]
            table_data.append(row)

        columns = [
            "Energia", "X (cm)", "Y (cm)", "Y1 (cm)", "Y2 (cm)",
            "Filtro", "MU", "Dose (cGy)", "SSD (cm)", "Prof (cm)",
            "Prof Ef (cm)", "FSX (mm)", "FSY (mm)"
        ]
        df = pd.DataFrame(table_data, columns=columns)

        # Texto simples para download
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
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return None, None, None

    extractor = TeletherapyExtractor(full_text)
    return extractor.process()

def display_results(df, paciente_info, key_suffix=""):
    if df is None or df.empty:
        st.warning("Nenhum dado extraído.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Paciente", paciente_info["Nome"])
    with col2:
        st.metric("Matrícula", paciente_info["Matrícula"])
    with col3:
        st.metric("Curso", paciente_info["Curso"])
    with col4:
        st.metric("Plano", paciente_info["Plano"])

    st.subheader("📊 Parâmetros dos Campos")
    st.dataframe(df, use_container_width=True, hide_index=True)

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
        txt_lines = [f"Nome: {paciente_info['Nome']} | Matrícula: {paciente_info['Matrícula']}"]
        for _, row in df.iterrows():
            txt_lines.append(", ".join([str(v) for v in row.values]))
        txt_data = "\n".join(txt_lines)
        st.download_button(
            label="📥 Baixar TXT",
            data=txt_data,
            file_name=f"{paciente_info['Nome']}_dados.txt",
            mime="text/plain",
            key=f"txt_{key_suffix}"
        )

# Interface Streamlit
st.set_page_config(page_title="Extrator de Teleterapia", layout="wide")
st.title("🏥 Processador de Planejamento de Teleterapia")
st.markdown("Extraia automaticamente dados de PDFs de planejamento clínico e exporte para planilhas.")

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
        file1 = st.file_uploader("Selecione o primeiro PDF", type=["pdf"], key="file1")
    with col2:
        file2 = st.file_uploader("Selecione o segundo PDF", type=["pdf"], key="file2")
    if file1 and file2:
        if st.button("Processar Ambos", key="btn_dual"):
            with st.spinner("Processando PDFs..."):
                text1, df1, info1 = process_pdf(file1)
                text2, df2, info2 = process_pdf(file2)
                if df1 is not None and df2 is not None:
                    st.success("✅ Processamento concluído!")
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
