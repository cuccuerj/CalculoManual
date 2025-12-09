import streamlit as st
import PyPDF2
import pandas as pd
import re

# --------------------------
# Utilidades de extração
# --------------------------

class TeletherapyExtractor:
    def __init__(self, content: str):
        self.raw_content = content or ""
        # Normaliza espaços mantendo linhas para blocagem por "Campo X"
        self.clean_content = "\n".join(
            " ".join(line.split()) for line in self.raw_content.splitlines()
        )

    def _extract_one(self, pattern, text=None, group=1, flags=re.IGNORECASE | re.DOTALL):
        target = text if text is not None else self.clean_content
        m = re.search(pattern, target, flags)
        return m.group(group).strip() if m else None

    def _extract_all(self, pattern, text=None, flags=re.IGNORECASE | re.DOTALL):
        target = text if text is not None else self.clean_content
        return re.findall(pattern, target, flags)

    def _get_block(self, start_marker, end_marker):
        pattern = fr'{re.escape(start_marker)}(.*?){re.escape(end_marker)}'
        return self._extract_one(pattern, group=1)

    def _split_info_campos(self, text):
        """
        Divide a seção 'Informações do Campo' em blocos por Campo 1, Campo 2...
        Retorna dict {numero_campo: bloco_texto}
        """
        # Pegue tudo após "Informações do Campo"
        idx = text.lower().find("informações do campo")
        if idx == -1:
            return {}

        info_section = text[idx:]
        # Split por linhas que começam com "Campo N"
        parts = re.split(r'\n\s*Campo\s+(\d+)\s*\n', info_section, flags=re.IGNORECASE)
        # re.split retorna: [prefixo, num1, bloco1, num2, bloco2, ...]
        info_blocks = {}
        if len(parts) >= 3:
            # Ignora prefixo parts[0]
            for i in range(1, len(parts), 2):
                try:
                    num = int(parts[i])
                    bloco = parts[i + 1]
                    # Corta no próximo separador de linhas de traços, se existir
                    bloco = re.split(r'\n-+\n', bloco, maxsplit=1)[0]
                    info_blocks[num] = bloco
                except:
                    continue
        return info_blocks

    def _extract_fs_from_block(self, block):
        """
        Tenta extrair FSX/FSY dentro de um bloco de Informações por Campo
        em diversas variações de texto.
        Prioridade:
          1) 'fluência total' (mais confiável para seu caso)
          2) 'fluence/fluência/fluencia: fsx=..., fsy=...'
        Retorna (fsx, fsy) como strings sem 'mm', ou None se não achou.
        """
        if not block:
            return None

        # 1) Determinado a partir da fluência total
        m = re.search(
            r'flu[eê]ncia\s+total.*?fsx\s*=\s*([\d.,]+)\s*mm.*?fsy\s*=\s*([\d.,]+)\s*mm',
            block,
            re.IGNORECASE | re.DOTALL
        )
        if m:
            return (m.group(1), m.group(2))

        # 2) Variações com 'fluence:' / 'fluência:' / 'fluencia:'
        m2 = re.search(
            r'(?:fluence|flu[eê]ncia)\s*:\s*.*?fsx\s*=\s*([\d.,]+)\s*mm.*?fsy\s*=\s*([\d.,]+)\s*mm',
            block,
            re.IGNORECASE | re.DOTALL
        )
        if m2:
            return (m2.group(1), m2.group(2))

        # 3) Caso apareça sem dois pontos (mais permissivo)
        m3 = re.search(
            r'(?:fluence|flu[eê]ncia)\s+.*?fsx\s*=\s*([\d.,]+)\s*mm.*?fsy\s*=\s*([\d.,]+)\s*mm',
            block,
            re.IGNORECASE | re.DOTALL
        )
        if m3:
            return (m3.group(1), m3.group(2))

        return None

    def process(self):
        c = self.clean_content

        # Básicos
        nome = self._extract_one(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)')
        matricula = self._extract_one(r'Matricula:\s*(\d+)')

        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c, re.IGNORECASE)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # Campos e energias
        campos_raw = self._extract_all(r'Campo\s+(\d+)\s+(\d+X)', c)
        energias_campos = [item[1] for item in campos_raw]
        num_campos = len(energias_campos) if energias_campos else 0

        # Blocos de texto
        block_x = self._get_block('Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
        block_y = self._get_block('Tamanho do Campo Aberto Y', 'Jaw Y1')
        block_jaw_y1 = self._get_block('Jaw Y1', 'Jaw Y2')
        block_jaw_y2 = self._get_block('Jaw Y2', 'Filtro')
        block_filtros = self._get_block('Filtro', 'MU')
        block_mu = self._get_block('MU', 'Dose')

        def get_vals(block, regex):
            return re.findall(regex, block, re.IGNORECASE) if block else []

        x_sizes = get_vals(block_x, r'Campo\s+\d+\s+([\d.]+)\s*cm')
        y_sizes = get_vals(block_y, r'Campo\s+\d+\s+([\d.]+)\s*cm')
        jaw_y1 = get_vals(block_jaw_y1, r'Y1:\s*([+-]?\d+\.\d+)')
        jaw_y2 = get_vals(block_jaw_y2, r'Y2:\s*([+-]?\d+\.\d+)')
        filtros = get_vals(block_filtros, r'Campo\s+\d+\s+([-\w]+)')
        mu_vals = get_vals(block_mu, r'Campo\s+\d+\s*([\d.]+)\s*MU')
        dose_vals = re.findall(r'Dose\s*\n(?:Campo\s+\d+\s+)?([\d.]+)\s*cGy', c, re.IGNORECASE)

        block_ssd = self._get_block('SSD', 'Profundidade')
        ssd_vals = get_vals(block_ssd, r'Campo\s+\d+\s*([\d.]+)\s*cm')

        block_prof = self._get_block('Profundidade', 'Profundidade Efetiva')
        prof_vals = get_vals(block_prof, r'Campo\s+\d+\s*([\d.]+)\s*cm')

        block_eff = self._get_block('Profundidade Efetiva', 'Informações do Campo')
        if not block_eff:
            # Fallback caso o relatório mude o marcador seguinte
            block_eff = self._get_block('Profundidade Efetiva', 'Campo 1')
        prof_eff_vals = get_vals(block_eff, r'Campo\s+\d+\s*([\d.]+)\s*cm')

        # Separa blocos "Informações do Campo" por Campo N para extrair FSX/FSY por campo
        info_blocks = self._split_info_campos(c)

        # Monta saída e tabela
        output_lines = []
        if nome:
            output_lines.append(f"Nome do Paciente: {nome}")
        if matricula:
            output_lines.append(f"Matricula: {matricula}")
        if unidade != "N/A":
            output_lines.append(f"Unidade de tratamento: {unidade} | Energia: {energia_unidade}")

        table_data = []

        total_rows = max(num_campos, len(x_sizes), len(y_sizes), len(jaw_y1), len(jaw_y2), len(filtros),
                         len(mu_vals), len(dose_vals), len(ssd_vals), len(prof_vals), len(prof_eff_vals))
        total_rows = max(total_rows, 1)

        def safe(lst, idx, default="N/A"):
            return lst[idx] if idx < len(lst) else default

        for i in range(total_rows):
            campo_idx = i + 1  # Campos são 1-based no relatório

            # Filtro do campo
            filtro_i = safe(filtros, i, "N/A")

            # FSX/FSY: apenas quando não há filtro (filtro == '-')
            fsx_val, fsy_val = "-", "-"
            bloco_info = info_blocks.get(campo_idx)
            fs_pair = self._extract_fs_from_block(bloco_info)

            # Condição: sem filtro → usa fs do bloco, com filtro → mantém '-'
            has_filter = (filtro_i not in ('-', 'nan', '', 'N/A')) if filtro_i is not None else False
            if not has_filter and fs_pair:
                fsx_val, fsy_val = fs_pair

            row = [
                safe(energias_campos, i, ""),
                safe(x_sizes, i),
                safe(y_sizes, i),
                safe(jaw_y1, i),
                safe(jaw_y2, i),
                filtro_i,
                safe(mu_vals, i),
                safe(dose_vals, i),
                safe(ssd_vals, i),
                safe(prof_vals, i),
                safe(prof_eff_vals, i),
                fsx_val,
                fsy_val
            ]

            output_lines.append(", ".join([str(x) for x in row]))
            table_data.append(row)

        df = pd.DataFrame(table_data, columns=[
            "Energia", "X", "Y", "Y1", "Y2", "Filtro", "MU", "Dose", "SSD", "Prof", "P.Ef", "FSX", "FSY"
        ])

        result_text = "\n".join(output_lines) if output_lines else "Nenhum dado extraído."
        return result_text, df

# --------------------------
# Processamento de PDF
# --------------------------

def process_pdf(uploaded_file):
    if uploaded_file is None:
        return "Nenhum arquivo enviado.", None

    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = "\n".join([p.extract_text() or "" for p in reader.pages])
    except Exception as e:
        return f"Erro ao ler PDF: {e}", None

    extractor = TeletherapyExtractor(full_text)
    text, df = extractor.process()
    return text, df

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
            else:
                st.info("Nenhum dado extraído.")

            st.download_button(
                label="📥 Baixar TXT",
                data=text or "",
                file_name="resultado_extracao.txt",
                mime="text/plain"
            )
