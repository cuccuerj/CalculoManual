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
    .main { background-color: #f8f9fa; }
    h1 { color: #2c3e50; font-family: 'Helvetica Neue', sans-serif; font-weight: 700; text-align: center; }
    h3 { color: #7f8c8d; font-size: 1.1rem; text-align: center; margin-bottom: 2rem; }

    /* Customização do File Uploader */
    [data-testid='stFileUploader'] { width: 100%; max-width: 400px; margin: 0 auto; }
    [data-testid='stFileUploader'] section {
        padding: 0; background-color: #3498db; border: none; border-radius: 8px;
        transition: background-color 0.3s; height: 60px;
        display: flex; align-items: center; justify-content: center;
    }
    [data-testid='stFileUploader'] section:hover { background-color: #2980b9; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    [data-testid='stFileUploader'] section > button { display: none; }
    [data-testid='stFileUploader'] section span { display: none; }
    [data-testid='stFileUploader'] section::after {
        content: "📂 Carregar PDF de Tratamento"; color: white; font-weight: bold; font-size: 1rem; pointer-events: none;
    }
    .upload-help { text-align: center; font-size: 0.8rem; color: #95a5a6; margin-top: -10px; margin-bottom: 20px; }
    .stTextArea textarea { font-family: 'Courier New', monospace; color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

# ===== Classe de Processamento Corrigida =====
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
        # Procura o primeiro padrão start e o primeiro end que aparece depois dele
        pattern = fr'{re.escape(start_marker)}(.*?){re.escape(end_marker)}'
        return self._extract_regex(pattern, group=1)

    def process(self):
        c = self.clean_content
        
        # 1. Dados do Paciente
        nome = self._extract_regex(r'Nome do Paciente:\s*(.+?)(?=\s*Matricula)')
        matricula = self._extract_regex(r'Matricula:\s*(\d+)')
        
        # 2. Unidade e Energia
        unidade_match = re.search(r'Unidade de tratamento:\s*([^,]+),\s*energia:\s*(\S+)', c)
        unidade = unidade_match.group(1).strip() if unidade_match else "N/A"
        energia_unidade = unidade_match.group(2).strip() if unidade_match else "N/A"

        # 3. Identificação de Campos e Energias
        # Pega todas as ocorrências de Campo X Energia (ex: Campo 1 6X)
        campos_raw = re.findall(r'Campo (\d+)\s+(\d+X)', c)
        energias_campos = [item[1] for item in campos_raw]
        num_campos = len(energias_campos)

        # 4. Extração de Blocos (Estratégia mais segura que busca global)
        block_x = self._get_block('Tamanho do Campo Aberto X', 'Tamanho do Campo Aberto Y')
        block_y = self._get_block('Tamanho do Campo Aberto Y', 'Jaw Y1')
        block_jaw_y1 = self._get_block('Jaw Y1', 'Jaw Y2')
        block_jaw_y2 = self._get_block('Jaw Y2', 'Filtro')
        block_filtros = self._get_block('Filtro', 'MU')
        # CORREÇÃO MU: Usa bloco específico em vez de busca solta
        block_mu = self._get_block('MU', 'Dose') 
        
        def get_vals_from_block(block, prefix_regex):
            if not block: return []
            return re.findall(prefix_regex, block)

        x_sizes = get_vals_from_block(block_x, r'Campo \d+\s*([\d.]+)\s*cm')
        y_sizes = get_vals_from_block(block_y, r'Campo \d+\s*([\d.]+)\s*cm')
        jaw_y1 = get_vals_from_block(block_jaw_y1, r'Y1:\s*([+-]?\d+\.\d+)')
        jaw_y2 = get_vals_from_block(block_jaw_y2, r'Y2:\s*([+-]?\d+\.\d+)')
        filtros = get_vals_from_block(block_filtros, r'Campo \d+\s*([-\w]+)')
        # CORREÇÃO MU: Regex ajustado para pegar dentro do bloco MU
        um_vals = get_vals_from_block(block_mu, r'Campo \d+\s*([\d.]+)\s*MU')
        
        dose_vals = re.findall(r'Campo \d+\s+([\d.]+)\s*cGy', c)
        
        # Blocos finais
        block_ssd = self._get_block('SSD', 'Profundidade')
        ssd_vals = get_vals_from_block(block_ssd, r'Campo \d+\s*([\d.]+)\s*cm')
        
        block_prof = self._get_block('Profundidade', 'Profundidade Efetiva')
        prof_vals = get_vals_from_block(block_prof, r'Campo \d+\s*([\d.]+)\s*cm')
        
        block_eff = self._get_block('Profundidade Efetiva', 'Informações do Campo') # Ajuste no marcador final se necessário
        # Fallback se 'Informações do Campo' não for encontrado logo após
        if not block_eff: 
             block_eff = self._get_block('Profundidade Efetiva', 'Campo 1')

        prof_eff_vals = get_vals_from_block(block_eff, r'Campo \d+\s*([\d.]+)\s*cm')

        # 5. CORREÇÃO FLUÊNCIA TOTAL
        # O regex agora aceita sujeira (ex: "fsx c=" ou "fsy y=") entre a variável e o "="
        # [a-zA-Z]* consome letras aleatórias que o OCR possa ter pego
        fluencia_matches = re.findall(
            r'flu[eê]ncia\s+total.*?fsx\s*[a-zA-Z]*\s*=\s*([\d\.]+)\s*mm,\s*fsy\s*[a-zA-Z]*\s*=\s*([\d\.]+)\s*mm', 
            c, 
            re.IGNORECASE | re.DOTALL
        )

        # ===== Montagem das Linhas de Saída =====
        output_lines = []
        
        if nome:
            fmt_nome = ', '.join(nome.split())
            output_lines.append(f"Nome, do, Paciente:, {fmt_nome}")
        if matricula:
            output_lines.append(f"Matricula:, '{matricula}'")
        if unidade != "N/A":
            output_lines.append(f"Informações:, 'Unidade, 'de, 'tratamento:, '{unidade},, 'energia:, '{energia_unidade}'")

        table_data = []

        for i in range(num_campos):
            def safe_get(lst, idx, prefix="'"):
                return f"{prefix}{lst[idx]}" if idx < len(lst) else "'N/A"

            # Lógica Fluência Corrigida
            # Se houver uma lista de fluencias (ex: uma por pagina de log), tenta alinhar com o campo
            # Se só tiver uma fluencia global, usa ela para todos
            f_x_val = "'-"
            f_y_val = "'-"
            
            # Verifica se o campo tem filtro 'Físico' (não '-')
            has_filtro = False
            if i < len(filtros):
                 if filtros[i] != '-' and filtros[i].lower() != 'nan':
                     has_filtro = True
            
            # Se NÃO tem filtro (é '-', ou seja, campo aberto/comum), procuramos a fluencia
            # O texto original sugeria que quando tem Filtro, a fluencia é '-'
            if not has_filtro:
                fsx_temp, fsy_temp = None, None
                
                if fluencia_matches:
                    # Se tivermos exatamente o mesmo nº de fluencias que campos, casamos 1 pra 1
                    if len(fluencia_matches) == num_campos:
                        fsx_temp, fsy_temp = fluencia_matches[i]
                    # Se tivermos fluencias mas quantidade diferente, pegamos a última (padrão antigo) ou a primeira
                    elif len(fluencia_matches) > 0:
                        fsx_temp, fsy_temp = fluencia_matches[-1]
                
                if fsx_temp:
                    f_x_val = f"'{fsx_temp}"
                    f_y_val = f"'{fsy_temp}"

            row = [
                safe_get(energias_campos, i, prefix=""),
                safe_get(x_sizes, i),
                safe_get(y_sizes, i),
                safe_get(jaw_y1, i),
                safe_get(jaw_y2, i),
                safe_get(filtros, i),
                safe_get(um_vals, i), # Agora pegando do bloco correto
                safe_get(dose_vals, i),
                safe_get(ssd_vals, i),
                safe_get(prof_vals, i),
                safe_get(prof_eff_vals, i),
                f_x_val,
                f_y_val
            ]
            
            output_lines.append(", ".join(row))
            table_data.append([r.replace("'", "") for r in row])

        final_text = "\n".join(output_lines)
        
        df = pd.DataFrame(table_data, columns=[
            "Energia", "X Size", "Y Size", "Jaw Y1", "Jaw Y2", "Filtro", 
            "UM", "Dose", "SSD", "Prof", "Prof Eff", "FSX", "FSY"
        ])
        
        return final_text, df, nome

# ===== Layout Principal =====

st.title("🏥 Processador de Teleterapia")
st.markdown("<h3>Converta PDFs de tratamento em dados estruturados</h3>", unsafe_allow_html=True)

with st.container():
    uploaded_file = st.file_uploader("", type="pdf")
    st.markdown('<div class="upload-help">Arraste o arquivo ou clique no botão azul acima</div>', unsafe_allow_html=True)

if uploaded_file is not None:
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
            
        extractor = TeletherapyExtractor(full_text)
        result_text, df_preview, paciente_nome = extractor.process()
        
        st.divider()
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.success("✅ Processamento Concluído!")
            st.markdown(f"**Paciente:** {paciente_nome if paciente_nome else 'Não identificado'}")
        
        with col2:
            file_name = f"teleterapia_{paciente_nome.replace(' ', '_')}.txt" if paciente_nome else "dados.txt"
            st.download_button(
                label="⬇️ Baixar Arquivo .txt",
                data=result_text,
                file_name=file_name,
                mime="text/plain",
                use_container_width=True
            )

        tab1, tab2 = st.tabs(["📊 Visualização Tabela", "📝 Texto Formatado"])
        with tab1:
            st.dataframe(df_preview, use_container_width=True)
        with tab2:
            st.text_area("", value=result_text, height=300)
            
    except Exception as e:
        st.error(f"Erro ao processar: {str(e)}")
