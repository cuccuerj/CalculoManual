import streamlit as st
import PyPDF2
import pandas as pd
import re
from io import BytesIO
import tempfile

class TeletherapyExtractor:
    def __init__(self, content: str):
        self.raw_content = content or ""
        self.clean_content = ' '.join(self.raw_content.split())

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

        # Extrações básicas
        nome = self._extract_regex(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)')
        matricula = self._extract_regex(r'Matricula:\s*(\d+)')

        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # Campos e energias
        campos_raw = re.findall(r'Campo (\d+)\s+(\d+X)', c)
        energias_campos = [item[1] for item in campos_raw]
        num_campos = len(energias_campos)

        # Blocos de texto
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
        
        # CORREÇÃO: Regex mais específica para filtros
        # Pega apenas o que vem depois de "Campo X" dentro do bloco de Filtro
        filtros = get_vals(block_filtros, r'Campo \d+\s+([-\w]+)(?:\s|$)')
        
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

        # Extração de FSX e FSY (apenas "determined from the total fluence")
        # Aceita tanto inglês quanto português
        fluencia_matches = re.findall(
            r'(?:fluence|flu[eê]ncia)\s*:\s*.*?fsx\s*=\s*([\d.,]+)\s*mm.*?fsy\s*=\s*([\d.,]+)\s*mm',
            c,
            re.IGNORECASE | re.DOTALL
        )

        
        # DEBUG temporário
        st.info(f"🔍 Debug: {len(fluencia_matches)} pares FSX/FSY encontrados")
        st.info(f"🔍 Bloco de Filtros: '{block_filtros[:200] if block_filtros else 'NULO'}'")
        st.info(f"🔍 Filtros extraídos: {filtros}")
        st.info(f"🔍 Número de campos: {num_campos}")

        # Monta saída textual e tabela
        output_lines = []
        if nome:
            output_lines.append(f"Nome do Paciente: {nome}")
        if matricula:
            output_lines.append(f"Matricula: {matricula}")
        if unidade != "N/A":
            output_lines.append(f"Unidade de tratamento: {unidade} | Energia: {energia_unidade}")

        table_data = []
        for i in range(max(1, num_campos)):
            def safe(lst, idx, default="N/A"):
                return lst[idx] if idx < len(lst) else default

            # Fluência - verifica se tem filtro primeiro
            f_x_val, f_y_val = "-", "-"
            
            # Verifica se NÃO tem filtro (filtro é "-")
            has_filtro = (i < len(filtros) and filtros[i] not in ('-', 'nan', '', 'N/A'))
            
            # Se NÃO tem filtro, pega os valores de fluência
            if not has_filtro and fluencia_matches and i < len(fluencia_matches):
                f_x_val, f_y_val = fluencia_matches[i]

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
            output_lines.append(", ".join([str(x) for x in row]))
            table_data.append(row)

        df = pd.DataFrame(table_data, columns=[
            "Energia", "X", "Y", "Y1", "Y2", "Filtro", "MU", "Dose", "SSD", "Prof", "P.Ef", "FSX", "FSY"
        ])

        result_text = "\n".join(output_lines) if output_lines else "Nenhum dado extraído."
        return result_text, df, nome

def process_pdf(uploaded_file):
    if uploaded_file is None:
        return "Nenhum arquivo enviado.", None, None

    try:
        # Streamlit fornece um objeto UploadedFile
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = "\n".join([p.extract_text() or "" for p in reader.pages])
    except Exception as e:
        return f"Erro ao ler PDF: {e}", None, None

    extractor = TeletherapyExtractor(full_text)
    text, df, nome = extractor.process()

    return text, df

# Interface Streamlit
st.title("🏥 Processador de Teleterapia")
st.markdown("Extração automática de dados de planejamento clínico")

uploaded_file = st.file_uploader("Selecionar PDF", type=['pdf'])

if uploaded_file is not None:
    if st.button("Processar"):
        with st.spinner("Processando PDF..."):
            text, df = process_pdf(uploaded_file)
            
            st.subheader("📄 Texto Extraído")
            st.text_area("Resultado", text, height=200)
            
            st.subheader("📊 Dados Tabulados")
            st.dataframe(df, use_container_width=True)
            
            # Download do texto
            st.download_button(
                label="📥 Baixar TXT",
                data=text,
                file_name="resultado_extracao.txt",
                mime="text/plain"
            )
