import streamlit as st
import PyPDF2
import pandas as pd
import re

class TeletherapyExtractor:
    def __init__(self, content: str):
        self.raw_content = content or ""
        self.clean_content = "\n".join(
            " ".join(line.split()) for line in self.raw_content.splitlines()
        )

    def _extract_section(self, start, end=None):
        """Extrai bloco de texto entre dois marcadores."""
        text = self.clean_content
        pattern = fr'{re.escape(start)}(.*?){re.escape(end)}' if end else fr'{re.escape(start)}(.*)'
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    def _extract_vals(self, block, regex):
        return re.findall(regex, block, re.IGNORECASE) if block else []

    def _split_info_campos(self):
        """Divide 'Informações do Campo' em blocos por Campo N."""
        idx = self.clean_content.lower().find("informações do campo")
        if idx == -1:
            return {}
        info_section = self.clean_content[idx:]
        parts = re.split(r'\n\s*Campo\s+(\d+)\s*\n', info_section, flags=re.IGNORECASE)
        info_blocks = {}
        for i in range(1, len(parts), 2):
            try:
                num = int(parts[i])
                bloco = parts[i + 1]
                info_blocks[num] = bloco
            except:
                continue
        return info_blocks

    def _extract_fs(self, block):
        """Extrai FSX/FSY de um bloco de Informações."""
        if not block:
            return None
        m = re.search(
            r'flu[eê]ncia\s+total.*?fsx\s*=\s*([\d.,]+)\s*mm.*?fsy\s*=\s*([\d.,]+)\s*mm',
            block, re.IGNORECASE | re.DOTALL
        )
        if m:
            return (m.group(1), m.group(2))
        m2 = re.search(
            r'(?:fluence|flu[eê]ncia).*?fsx\s*=\s*([\d.,]+)\s*mm.*?fsy\s*=\s*([\d.,]+)\s*mm',
            block, re.IGNORECASE | re.DOTALL
        )
        if m2:
            return (m2.group(1), m2.group(2))
        return None

    def process(self):
        c = self.clean_content

        # Dados básicos
        nome = re.search(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)', c)
        nome = nome.group(1).strip() if nome else None
        matricula = re.search(r'Matricula:\s*(\d+)', c)
        matricula = matricula.group(1) if matricula else None
        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # Seções
        bloco_energia = self._extract_section("Energia", "Tamanho do Campo Aberto X")
        bloco_x = self._extract_section("Tamanho do Campo Aberto X", "Tamanho do Campo Aberto Y")
        bloco_y = self._extract_section("Tamanho do Campo Aberto Y", "Jaw Y1")
        bloco_y1 = self._extract_section("Jaw Y1", "Jaw Y2")
        bloco_y2 = self._extract_section("Jaw Y2", "Filtro")
        bloco_filtro = self._extract_section("Filtro", "MU")
        bloco_mu = self._extract_section("MU", "Dose")
        bloco_dose = self._extract_section("Dose", "SSD")
        bloco_ssd = self._extract_section("SSD", "Profundidade")
        bloco_prof = self._extract_section("Profundidade", "Profundidade Efetiva")
        bloco_pef = self._extract_section("Profundidade Efetiva", "Informações do Campo")

        # Listas
        energias = self._extract_vals(bloco_energia, r'Campo\s+\d+\s+(\S+)')
        x_sizes = self._extract_vals(bloco_x, r'Campo\s+\d+\s+([\d.]+)\s*cm')
        y_sizes = self._extract_vals(bloco_y, r'Campo\s+\d+\s+([\d.]+)\s*cm')
        y1_vals = self._extract_vals(bloco_y1, r'Y1:\s*([+-]?\d+\.\d+)')
        y2_vals = self._extract_vals(bloco_y2, r'Y2:\s*([+-]?\d+\.\d+)')
        filtros = self._extract_vals(bloco_filtro, r'Campo\s+\d+\s+([-\w]+)')
        mu_vals = self._extract_vals(bloco_mu, r'Campo\s+\d+\s*([\d.]+)\s*MU')
        dose_vals = self._extract_vals(bloco_dose, r'Campo\s+\d+\s*([\d.]+)\s*cGy')
        ssd_vals = self._extract_vals(bloco_ssd, r'Campo\s+\d+\s*([\d.]+)\s*cm')
        prof_vals = self._extract_vals(bloco_prof, r'Campo\s+\d+\s*([\d.]+)\s*cm')
        pef_vals = self._extract_vals(bloco_pef, r'Campo\s+\d+\s*([\d.]+)\s*cm')

        num_campos = len(energias)
        info_blocks = self._split_info_campos()

        # Monta tabela
        table_data = []
        for i in range(num_campos):
            fsx, fsy = "-", "-"
            bloco_info = info_blocks.get(i+1, "")
            if filtros[i] == "-" and bloco_info:
                fs_pair = self._extract_fs(bloco_info)
                if fs_pair:
                    fsx, fsy = fs_pair

            row = [
                energias[i],
                x_sizes[i],
                y_sizes[i],
                y1_vals[i],
                y2_vals[i],
                filtros[i],
                mu_vals[i],
                dose_vals[i],
                ssd_vals[i],
                prof_vals[i],
                pef_vals[i],
                fsx,
                fsy
            ]
            table_data.append(row)

        df = pd.DataFrame(table_data, columns=[
            "Energia", "X", "Y", "Y1", "Y2", "Filtro", "MU", "Dose", "SSD", "Prof", "P.Ef", "FSX", "FSY"
        ])

        # Texto resumo
        output_lines = []
        if nome: output_lines.append(f"Nome do Paciente: {nome}")
        if matricula: output_lines.append(f"Matricula: {matricula}")
        if unidade != "N/A": output_lines.append(f"Unidade de tratamento: {unidade} | Energia: {energia_unidade}")
        for row in table_data:
            output_lines.append(", ".join([str(x) for x in row]))

        result_text = "\n".join(output_lines)
        return result_text, df

def process_pdf(uploaded_file):
    if uploaded_file is None:
        return "Nenhum arquivo enviado.", None
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = "\n".join([p.extract_text() or "" for p in reader.pages])
    except Exception as e:
        return f"Erro ao ler PDF: {e}", None
    extractor = TeletherapyExtractor(full_text)
    return extractor.process()

# --------------------------
# Interface Streamlit
# --------------------------

st.title("🏥 Processador de Teleterapia")
st.markdown("Extração automática de dados de planejamento clínico")

uploaded_file = st.file_uploader("Selecionar PDF", type=['pdf'])

if uploaded_file is not None:
    if st.button("Processar"):
        with st.spinner("Processando PDF..."):
            text, df = process_pdf(uploaded_file)
            st.subheader("📄 Texto Extraído")
            st.text_area("Resultado", text, height=250)
            st.subheader("📊 Dados Tabulados")
            if df is not None and not df.empty:
                st.dataframe(df, use_container_width=True)
            st.download_button(
                label="📥 Baixar TXT",
                data=text,
                file_name="resultado_extracao.txt",
                mime="text/plain"
            )
