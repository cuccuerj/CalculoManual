import streamlit as st
import PyPDF2
import pandas as pd
import re
from io import BytesIO

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

        # CORREÇÃO: Captura FSX e FSY APENAS da linha "determined from the total fluence"
        # Ignora completamente a linha com "CBSF lookup"
        # Suporta tanto inglês quanto português
        #fluencia_matches = []
        
        # Extração de FSX e FSY usando o padrão unificado
        fluencia_matches = re.findall(
            r"(?:total fluence|fluência total).*?fsx\s*=\s*(\d+)\s*mm,\s*fsy\s*=\s*(\d+)\s*mm",
            c, re.IGNORECASE
        )

        # Se não encontrar, tenta linha a linha (fallback)
        if not fluencia_matches:
            for line in self.lines:
                match = re.search(
                    r"(?:total fluence|fluência total).*?fsx\s*=\s*(\d+)\s*mm,\s*fsy\s*=\s*(\d+)\s*mm",
                    line, re.IGNORECASE
                )
                if match:
                    fluencia_matches.append(match.groups())

        # Para debug: mostrar o que foi encontrado
        if fluencia_matches:
            st.write("**Debug:** Fluência total encontrada:", fluencia_matches)
        else:
            st.write("**Debug:** Nenhuma fluência total encontrada.")
        
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

            # Fluência só se não houver filtro
            f_x_val, f_y_val = "-", "-"
            has_filtro = False
            if i < len(filtros) and filtros[i] not in ('-', 'nan', ''):
                has_filtro = True

            if not has_filtro and fluencia_matches:
                # Tenta pegar a fluência correspondente ao campo
                if i < len(fluencia_matches):
                    f_x_val, f_y_val = fluencia_matches[i]
                else:
                    # Se não houver correspondência, usa a última
                    f_x_val, f_y_val = fluencia_matches[-1]

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
        # Lê o PDF do objeto UploadedFile do Streamlit
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = "\n".join([p.extract_text() or "" for p in reader.pages])
    except Exception as e:
        return f"Erro ao ler PDF: {e}", None, None

    extractor = TeletherapyExtractor(full_text)
    text, df, nome = extractor.process()

    return text, df, nome

# Interface Streamlit
st.title("🏥 Processador de Teleterapia")
st.markdown("Extração automática de dados de planejamento clínico")

# Criar abas
tab1, tab2 = st.tabs(["📄 Arquivo Único", "📄📄 Comparar Dois Arquivos"])

# ABA 1: Arquivo único
with tab1:
    st.subheader("Processar um arquivo PDF")
    uploaded_file = st.file_uploader("Selecionar PDF", type=["pdf"], key="single_file")

    if uploaded_file is not None:
        if st.button("Processar", key="btn_single"):
            with st.spinner("Processando PDF..."):
                text, df, nome = process_pdf(uploaded_file)
                
                if df is not None:
                    st.success("✅ Processamento concluído!")
                    
                    # Mostra informações extraídas
                    st.subheader("📋 Dados Extraídos")
                    st.text(text)
                    
                    # Mostra tabela
                    st.subheader("📊 Tabela de Dados")
                    st.dataframe(df, use_container_width=True)
                    
                    # Botão para download do TXT
                    st.download_button(
                        label="📥 Baixar TXT",
                        data=text,
                        file_name=f"{nome if nome else 'resultado'}.txt",
                        mime="text/plain",
                        key="download_single"
                    )
                else:
                    st.error("❌ Erro ao processar o arquivo")

# ABA 2: Dois arquivos
with tab2:
    st.subheader("Processar dois arquivos PDF")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Arquivo 1**")
        uploaded_file1 = st.file_uploader("Selecionar primeiro PDF", type=["pdf"], key="file1")
    
    with col2:
        st.markdown("**Arquivo 2**")
        uploaded_file2 = st.file_uploader("Selecionar segundo PDF", type=["pdf"], key="file2")
    
    if uploaded_file1 is not None and uploaded_file2 is not None:
        if st.button("Processar Ambos", key="btn_dual"):
            with st.spinner("Processando PDFs..."):
                # Processa arquivo 1
                text1, df1, nome1 = process_pdf(uploaded_file1)
                
                # Processa arquivo 2
                text2, df2, nome2 = process_pdf(uploaded_file2)
                
                if df1 is not None and df2 is not None:
                    st.success("✅ Processamento concluído!")
                    
                    # Exibir lado a lado
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader(f"📄 Arquivo 1: {nome1 if nome1 else 'PDF 1'}")
                        st.text(text1)
                        st.dataframe(df1, use_container_width=True)
                        st.download_button(
                            label="📥 Baixar TXT 1",
                            data=text1,
                            file_name=f"{nome1 if nome1 else 'resultado1'}.txt",
                            mime="text/plain",
                            key="download1"
                        )
                    
                    with col2:
                        st.subheader(f"📄 Arquivo 2: {nome2 if nome2 else 'PDF 2'}")
                        st.text(text2)
                        st.dataframe(df2, use_container_width=True)
                        st.download_button(
                            label="📥 Baixar TXT 2",
                            data=text2,
                            file_name=f"{nome2 if nome2 else 'resultado2'}.txt",
                            mime="text/plain",
                            key="download2"
                        )
                else:
                    st.error("❌ Erro ao processar um ou ambos os arquivos")
    elif uploaded_file1 is not None or uploaded_file2 is not None:
        st.info("ℹ️ Por favor, selecione ambos os arquivos PDF para processar")
