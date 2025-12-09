import streamlit as st
import PyPDF2
import pandas as pd
import re
import altair as alt

# --------------------------
# Configuração da página e estilo
# --------------------------
st.set_page_config(page_title="Processador de Teleterapia", page_icon="🏥", layout="wide")

st.markdown("""
<style>
/* Fundo e tipografia */
[data-testid="stAppViewContainer"] {
  background: #f6f8fb;
  font-family: "Segoe UI", Roboto, "Helvetica Neue", Arial;
}
h1, h2, h3 {
  color: #0b3d91;
  font-weight: 700;
}
.stButton>button {
  background-color: #0b66c3;
  color: white;
  border-radius: 8px;
  padding: 8px 14px;
  font-weight: 600;
}
.stDownloadButton>button {
  background-color: #16a34a;
  color: white;
  border-radius: 8px;
  padding: 8px 14px;
  font-weight: 600;
}
.card {
  background: white;
  padding: 16px;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(16,24,40,0.06);
}
.small-muted {
  color: #6b7280;
  font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

# --------------------------
# Classe de extração
# --------------------------
class TeletherapyExtractor:
    def __init__(self, content: str):
        self.raw_content = content or ""
        # Normaliza espaços por linha, mantendo quebras para blocos
        self.clean_content = "\n".join(" ".join(line.split()) for line in self.raw_content.splitlines())

    def _extract_section(self, start, end=None):
        text = self.clean_content
        if end:
            pattern = fr'{re.escape(start)}(.*?){re.escape(end)}'
        else:
            pattern = fr'{re.escape(start)}(.*)'
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    def _extract_vals(self, block, regex):
        return re.findall(regex, block, re.IGNORECASE) if block else []

    def _split_info_campos(self):
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
        if not block:
            return None
        # prioridade: "determinado a partir da fluência total" / "tamanho de campo efetivo determinado a partir da fluência total"
        m = re.search(
            r'flu[eê]ncia\s+total.*?fsx\s*=\s*([\d.,]+)\s*mm.*?fsy\s*=\s*([\d.,]+)\s*mm',
            block, re.IGNORECASE | re.DOTALL
        )
        if m:
            return (m.group(1), m.group(2))
        # variações: "fluence:" / "fluência:" / "fluencia:"
        m2 = re.search(
            r'(?:fluence|flu[eê]ncia)\s*[:\s].*?fsx\s*=\s*([\d.,]+)\s*mm.*?fsy\s*=\s*([\d.,]+)\s*mm',
            block, re.IGNORECASE | re.DOTALL
        )
        if m2:
            return (m2.group(1), m2.group(2))
        return None

    def process(self):
        c = self.clean_content

        # Dados básicos
        nome_m = re.search(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)', c, re.IGNORECASE)
        nome = nome_m.group(1).strip() if nome_m else None
        mat_m = re.search(r'Matricula:\s*(\d+)', c, re.IGNORECASE)
        matricula = mat_m.group(1) if mat_m else None
        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c, re.IGNORECASE)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # Extrai seções fixas (linha a linha)
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

        # Regexs para cada coluna (mais restritos)
        energias = self._extract_vals(bloco_energia, r'Campo\s+\d+\s+(\S+)')
        x_sizes = self._extract_vals(bloco_x, r'Campo\s+\d+\s+([\d.]+)\s*cm')
        y_sizes = self._extract_vals(bloco_y, r'Campo\s+\d+\s+([\d.]+)\s*cm')
        y1_vals = self._extract_vals(bloco_y1, r'Y1:\s*([+-]?\d+\.\d+)')
        y2_vals = self._extract_vals(bloco_y2, r'Y2:\s*([+-]?\d+\.\d+)')
        # filtro: captura EDW... ou '-' ou outros identificadores alfanuméricos
        filtros = self._extract_vals(bloco_filtro, r'Campo\s+\d+\s+([A-Za-z0-9\-]+)')
        mu_vals = self._extract_vals(bloco_mu, r'Campo\s+\d+\s*([\d.]+)\s*MU')
        dose_vals = self._extract_vals(bloco_dose, r'Campo\s+\d+\s*([\d.]+)\s*cGy')
        ssd_vals = self._extract_vals(bloco_ssd, r'Campo\s+\d+\s*([\d.]+)\s*cm')
        prof_vals = self._extract_vals(bloco_prof, r'Campo\s+\d+\s*([\d.]+)\s*cm')
        pef_vals = self._extract_vals(bloco_pef, r'Campo\s+\d+\s*([\d.]+)\s*cm')

        num_campos = len(energias)
        info_blocks = self._split_info_campos()

        # Garante que listas tenham tamanho num_campos, preenchendo com "N/A" quando faltar
        def pad(lst, n, fill="N/A"):
            return lst + [fill] * (n - len(lst)) if len(lst) < n else lst[:n]

        energias = pad(energias, num_campos, "")
        x_sizes = pad(x_sizes, num_campos)
        y_sizes = pad(y_sizes, num_campos)
        y1_vals = pad(y1_vals, num_campos)
        y2_vals = pad(y2_vals, num_campos)
        filtros = pad(filtros, num_campos, "N/A")
        mu_vals = pad(mu_vals, num_campos)
        dose_vals = pad(dose_vals, num_campos)
        ssd_vals = pad(ssd_vals, num_campos)
        prof_vals = pad(prof_vals, num_campos)
        pef_vals = pad(pef_vals, num_campos)

        # Monta tabela final
        table_data = []
        for i in range(num_campos):
            campo_idx = i + 1
            fsx, fsy = "-", "-"
            bloco_info = info_blocks.get(campo_idx, "")
            # Se filtro for '-' (sem wedge), tenta extrair FS do bloco de informações
            filtro_i = filtros[i]
            has_filter = filtro_i not in ('-', 'N/A', '', None)
            if not has_filter and bloco_info:
                fs_pair = self._extract_fs(bloco_info)
                if fs_pair:
                    fsx, fsy = fs_pair

            row = [
                energias[i],
                x_sizes[i],
                y_sizes[i],
                y1_vals[i],
                y2_vals[i],
                filtro_i,
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

# --------------------------
# Função de processamento do PDF
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
    return extractor.process()

# --------------------------
# Interface Streamlit (layout)
# --------------------------
st.title("🏥 Processador de Teleterapia")
st.markdown("Extração automática de dados de planejamento clínico — visual e gráficos interativos")

with st.sidebar:
    st.header("Opções")
    st.markdown("Envie um PDF de planejamento e clique em Processar.")
    show_raw = st.checkbox("Mostrar texto extraído (debug)", value=False)
    st.markdown("---")
    st.markdown("Tema rápido")
    theme = st.selectbox("Tema", ["Claro (padrão)", "Escuro (contraste)"])
    if theme == "Escuro (contraste)":
        st.markdown("<style>body{background:#0b1220;color:#e6eef8}</style>", unsafe_allow_html=True)

col1, col2 = st.columns([1, 2])

with col1:
    uploaded_file = st.file_uploader("Selecionar PDF", type=['pdf'])
    if uploaded_file:
        st.markdown("**Arquivo carregado:**")
        st.write(uploaded_file.name)

    if st.button("Processar"):
        if not uploaded_file:
            st.warning("Envie um PDF antes de processar.")
        else:
            with st.spinner("Processando PDF..."):
                text, df = process_pdf(uploaded_file)
                st.session_state['last_text'] = text
                st.session_state['last_df'] = df

with col2:
    st.subheader("Resultado")
    if 'last_df' in st.session_state and st.session_state['last_df'] is not None:
        df = st.session_state['last_df'].copy()
        text = st.session_state.get('last_text', "")

        # Mostra texto bruto opcional
        if show_raw:
            with st.expander("Texto extraído (primeiros 2000 caracteres)"):
                st.text_area("Texto", text[:2000], height=300)

        # Limpeza e conversão numérica para gráficos
        df_plot = df.copy()
        # Substitui vírgula por ponto e converte colunas numéricas
        for col in ["MU", "Dose", "FSX", "FSY", "X", "Y", "SSD", "Prof", "P.Ef"]:
            if col in df_plot.columns:
                df_plot[col] = df_plot[col].astype(str).str.replace(",", ".").str.replace("N/A", "")
                df_plot[col] = pd.to_numeric(df_plot[col], errors='coerce')

        # Painel de visualização
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📊 Tabela de Campos")
        st.dataframe(df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Gráficos
        st.markdown("### 📈 Visualizações interativas")
        # MU vs Dose
        if df_plot["MU"].notna().any() and df_plot["Dose"].notna().any():
            chart_mu_dose = alt.Chart(df_plot).mark_circle(size=120).encode(
                x=alt.X('MU:Q', title='MU'),
                y=alt.Y('Dose:Q', title='Dose (cGy)'),
                color=alt.Color('Energia:N', title='Energia'),
                tooltip=['Energia', 'Filtro', alt.Tooltip('MU:Q', format=".2f"), alt.Tooltip('Dose:Q', format=".2f")]
            ).interactive()
            st.altair_chart(chart_mu_dose, use_container_width=True)
        else:
            st.info("Dados insuficientes para MU vs Dose.")

        # FSX vs FSY
        if df_plot["FSX"].notna().any() and df_plot["FSY"].notna().any():
            chart_fs = alt.Chart(df_plot.dropna(subset=['FSX', 'FSY'])).mark_point(filled=True, size=150).encode(
                x=alt.X('FSX:Q', title='FSX (mm)'),
                y=alt.Y('FSY:Q', title='FSY (mm)'),
                color=alt.Color('Filtro:N', title='Filtro'),
                tooltip=['Energia', 'Filtro', alt.Tooltip('FSX:Q', format=".1f"), alt.Tooltip('FSY:Q', format=".1f")]
            ).interactive()
            st.altair_chart(chart_fs, use_container_width=True)
        else:
            st.info("FSX/FSY não encontrados para plotagem (verifique campos sem filtro).")

        # Pequeno resumo estatístico
        with st.expander("Resumo rápido"):
            st.write("Contagem de campos:", len(df))
            st.write("Filtros encontrados:", df['Filtro'].unique().tolist())
            st.write("Valores MU (min, max):", df_plot['MU'].min(), df_plot['MU'].max())

        # Botões de download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar CSV", data=csv, file_name="extracao_teleterapia.csv", mime="text/csv")
        st.download_button("📥 Baixar TXT (resumo)", data=text or "", file_name="resultado_extracao.txt", mime="text/plain")
    else:
        st.info("Nenhum resultado disponível. Carregue um PDF e clique em Processar.")

# --------------------------
# Fim do app
# --------------------------
