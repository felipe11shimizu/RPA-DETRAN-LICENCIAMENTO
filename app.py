import streamlit as st
import pandas as pd
import time
import io
import asyncio
import subprocess
import pyautogui
import pyperclip
from pywinauto import Desktop
import re

# Configurações de caminhos globais
EXECUTABLE_PATH = r"C:\Users\Detran\OneDrive - PRODESP\Área de Trabalho\Projetos_e_Robos\BGBI\BGBI_ORIGINAL_BACKUP.exe"
RDP_WINDOW_TITLE = "Conexão de Área de Trabalho Remota"

st.set_page_config(page_title="Portal de Automação", page_icon="🤖", layout="wide")

# Inicializa o estado da sessão (Memória do App)
if "df_atual" not in st.session_state:
    st.session_state.df_atual = None

# --- GADGET DE CONTROLE (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    st.markdown("Configure a execução da automação.")
    
    automacao_selecionada = st.selectbox(
        "Selecione a Automação:",
        ["BGBI - Consulta Veicular", "BTNB - Automação", "AUML - Licenciamento", "ELIC - Automação"]
    )
    
    col_retorno_atual = f"RETORNO_{automacao_selecionada.split(' - ')[0]}"
    
    # Controles de Velocidade Separados
    st.markdown("### ⚡ Velocidades")
    vel_digitacao = st.select_slider(
        "Velocidade de Digitação (Teclas):",
        options=["Lenta", "Normal", "Rápida"],
        value="Normal",
        help="Controla o quão rápido o robô digita as teclas."
    )
    map_digita = {"Lenta": 0.1, "Normal": 0.05, "Rápida": 0.01}
    interval_tecla = map_digita[vel_digitacao]
    
    tempo_sistema = st.select_slider(
        "Espera do Sistema (X CLOCK):",
        options=["Curto", "Médio", "Longo"],
        value="Médio",
        help="Controla os delays (pausas) após o robô apertar ENTER para esperar o mainframe carregar."
    )
    map_tempo = {"Curto": 0.5, "Médio": 1.5, "Longo": 3.0}
    delay_sistema = map_tempo[tempo_sistema]
    
    st.divider()
    st.info(f"O sistema gravará as respostas na coluna: **{col_retorno_atual}**")


st.title("🤖 Portal de Automação")
st.markdown("Arraste uma planilha, ajuste os filtros se necessário, e inicie a automação. Para encadear (ex: rodar BTNB e depois AUML), basta trocar o seletor lateral e processar novamente os registros.")

# --- FUNÇÕES COMUNS DE INFRAESTRUTURA ---
def open_executable(exec_path):
    try:
        process = subprocess.Popen([exec_path])
        time.sleep(3)
        return process
    except FileNotFoundError:
        return None

def focus_mainframe_window():
    try:
        desktop = Desktop(backend="uia")
        window = desktop.windows(title_re=f".*{RDP_WINDOW_TITLE}.*")[0]
        window.set_focus()
        window.maximize()
        time.sleep(1.5)
        screenWidth, screenHeight = pyautogui.size()
        pyautogui.click(screenWidth / 2, screenHeight / 2)
        time.sleep(1)
        return True
    except Exception:
        return False

# --- FUNÇÃO GENÉRICA PARA CAPTURA ---
def capturar_tela():
    pyperclip.copy("")
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(0.5)
    
    texto_tela = pyperclip.paste()
    pyautogui.press('esc')
    pyautogui.press('right') 
    time.sleep(0.2)
    
    linhas = texto_tela.splitlines()
    if linhas:
        linhas_nao_vazias = [l.strip() for l in linhas if l.strip()]
        return linhas_nao_vazias[-1] if linhas_nao_vazias else "Vazio"
    return "Não foi possível capturar o retorno."


# --- AUTOMAÇÕES RPA ---
async def processar_rpa(df: pd.DataFrame, apenas_pendentes: bool) -> pd.DataFrame:
    resultado_df = df.copy()
    
    if col_retorno_atual not in resultado_df.columns:
        resultado_df[col_retorno_atual] = ""
        
    total_linhas = len(resultado_df)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("Focando na janela do Mainframe e ativando teclado...")
    focou = focus_mainframe_window()
    if not focou:
        st.warning("Não foi possível focar automaticamente. Traga a janela para a frente!")
        await asyncio.sleep(3)
        
    pyautogui.FAILSAFE = True
    
    # --- SETUP INICIAL POR MÓDULO ---
    if "BTNB" in automacao_selecionada:
        status_text.text("Realizando setup inicial BTNB...")
        pyautogui.press('home')
        time.sleep(0.3)
        pyautogui.write('BTNB', interval=interval_tecla)
        time.sleep(0.2)
        pyautogui.press('enter')
        time.sleep(delay_sistema)
    elif "AUML" in automacao_selecionada:
        # AUML pode ou não ter setup antes de iterar, assumindo que a transação é feita por registro
        pass

    for index, row in resultado_df.iterrows():
        # Filtro de Continuar
        if apenas_pendentes:
            retorno_existente = str(row[col_retorno_atual]).strip()
            if retorno_existente != "" and "Falha de Sistema" not in retorno_existente:
                progress_bar.progress(int(((index + 1) / total_linhas) * 100))
                continue
                
        placa = str(row.get('placa', '')).strip().upper()
        # Tratamento do municipio
        try:
            mun_val = row.get('cod_municipio', 0)
            if pd.isna(mun_val): mun_val = 0
            cod_municipio = str(int(float(mun_val))).zfill(5)
        except Exception:
            cod_municipio = str(row.get('cod_municipio', '')).strip().zfill(5)
            
        status_text.text(f"Processando [{automacao_selecionada}] {index + 1}/{total_linhas}: {placa}...")
        
        try:
            if index > 0:
                time.sleep(delay_sistema * 0.8)
                
            pyautogui.press('home')
            time.sleep(0.2)
            pyautogui.press('home')
            time.sleep(0.3)
            
            # --- LÓGICA ESPECÍFICA POR MÓDULO ---
            if "BGBI" in automacao_selecionada:
                transacao = f"BGBI{placa} {cod_municipio}".upper()
                pyautogui.write(transacao, interval=interval_tecla)
                time.sleep(0.2)
                pyautogui.press('enter')
                time.sleep(delay_sistema)
                retorno = capturar_tela()
                
            elif "BTNB" in automacao_selecionada:
                # O legacy script digita Home, BTNB, Enter A CADA ITERAÇÃO
                pyautogui.write('BTNB', interval=interval_tecla)
                time.sleep(0.2)
                pyautogui.press('enter')
                time.sleep(delay_sistema)
                
                pyautogui.write(placa, interval=interval_tecla)
                pyautogui.write(cod_municipio, interval=interval_tecla)
                pyautogui.press('enter')
                time.sleep(delay_sistema)
                retorno = capturar_tela()
                
            elif "AUML" in automacao_selecionada:
                # AUML + Placa + Espaco + Cod_Municipio
                transacao_auml = f"AUML{placa} {cod_municipio}".upper()
                pyautogui.write(transacao_auml, interval=interval_tecla)
                pyautogui.press('enter')
                time.sleep(delay_sistema)
                
                # Segunda tela (Motivo 01)
                pyautogui.write('01', interval=interval_tecla)
                pyautogui.press('enter')
                time.sleep(delay_sistema)
                retorno = capturar_tela()
                
            elif "ELIC" in automacao_selecionada:
                # ELIC + Placa + Espaço + Municipio + Espaço + 99999
                transacao_elic = f"ELIC{placa} {cod_municipio} 99999".upper()
                pyautogui.write(transacao_elic, interval=interval_tecla)
                pyautogui.press('enter')
                time.sleep(delay_sistema)
                
                # Captura para verificar se pediu confirmacao ou se já deu erro
                retorno = capturar_tela()
                
                # Se a mensagem contiver a palavra "CONFIRA", significa que foi para a segunda tela
                if "CONFIRA" in retorno.upper():
                    pyautogui.press('enter')
                    time.sleep(delay_sistema)
                    # Captura o retorno final após a confirmação
                    retorno = capturar_tela()

            # Grava retorno
            resultado_df.at[index, col_retorno_atual] = retorno
            
        except pyautogui.FailSafeException:
            st.error("Automação abortada (Failsafe acionado).")
            resultado_df.at[index, col_retorno_atual] = "Falha de Sistema (FailSafe)"
            break
        except Exception as e:
            resultado_df.at[index, col_retorno_atual] = f"Erro de Sistema: {e}"
            
        progress_bar.progress(int(((index + 1) / total_linhas) * 100))

    status_text.text("Processamento concluído!")
    return resultado_df


# --- PÓS PROCESSAMENTO (PANDAS) ---
def gerar_relatorio_excel(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Base Consolidada')
    return output.getvalue()


# --- INTERFACE PRINCIPAL ---
uploaded_file = st.file_uploader("Arraste e solte o arquivo Excel (.xlsx) aqui para carregar a base inicial", type=["xlsx"])

# Atualizar state se houver novo upload
if uploaded_file is not None:
    try:
        # Lê o dataframe e armazena na sessao apenas se for um arquivo novo
        # Uma forma simples de detectar é comparar se o session state ta vazio
        if st.session_state.df_atual is None:
            df_temp = pd.read_excel(uploaded_file)
            st.session_state.df_atual = df_temp
            st.success("Planilha carregada na memória com sucesso!")
    except Exception as e:
        st.error(f"Ocorreu um erro ao ler o arquivo: {e}")

# Só mostra as opções de automação se houver dados na memória
if st.session_state.df_atual is not None:
    df_memoria = st.session_state.df_atual
    
    st.markdown("### Base de Dados em Memória (Filtros e Encadeamento)")
    st.markdown("Você pode editar células ou deletar linhas indesejadas antes de rodar a automação. Todas as automações selecionadas gravarão na mesma planilha.")
    
    # Data editor permite modificar a tabela interativamente
    df_editado = st.data_editor(df_memoria, use_container_width=True, num_rows="dynamic")
    # Salva edições
    st.session_state.df_atual = df_editado
    
    st.markdown("---")
    
    # NOVA SEÇÃO: FILTRO E REPROCESSAMENTO
    st.markdown("### 🧹 Filtro e Reprocessamento Específico")
    if col_retorno_atual in df_memoria.columns:
        retornos_unicos = df_memoria[col_retorno_atual].dropna().unique().tolist()
        retornos_validos = [r for r in retornos_unicos if str(r).strip() != ""]
        
        if retornos_validos:
            col_filtro, col_btn = st.columns([3, 1])
            with col_filtro:
                filtro_selecionado = st.selectbox(
                    "Selecione um Status (Retorno) específico que você deseja tentar rodar de novo:", 
                    ["Nenhum (Selecione...)"] + retornos_validos
                )
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True) # Espaçamento para alinhar com selectbox
                if st.button("🔄 FILTRAR E REINICIAR", use_container_width=True):
                    if filtro_selecionado != "Nenhum (Selecione...)":
                        # Apaga os retornos que bateram com o filtro (para torná-los 'pendentes' novamente)
                        df_memoria.loc[df_memoria[col_retorno_atual] == filtro_selecionado, col_retorno_atual] = ""
                        st.session_state.df_atual = df_memoria
                        
                        with st.spinner(f"Reprocessando as placas que estavam com o status '{filtro_selecionado}'..."):
                            # O processar_rpa com apenas_pendentes=True vai naturalmente puxar essas linhas agora!
                            novo_df = asyncio.run(processar_rpa(st.session_state.df_atual, apenas_pendentes=True))
                            st.session_state.df_atual = novo_df
                        st.rerun()

    st.markdown("---")
    
    # NOVA SEÇÃO: ENCADEAMENTO (FILTRAR PARA OUTRO RPA)
    st.markdown("### 🔗 Encadeamento: Filtrar para Outro RPA")
    colunas_retorno = [c for c in df_memoria.columns if c.startswith("RETORNO_")]
    if colunas_retorno:
        st.markdown("Use esta opção se você quiser **descartar** registros com base no resultado de uma automação anterior, mantendo apenas um grupo específico para rodar no próximo robô.")
        col_rpa_filtro, col_val_filtro, col_btn_filtro = st.columns([2, 2, 1.2])
        
        with col_rpa_filtro:
            rpa_origem = st.selectbox("1. Qual coluna de retorno usar?", ["Selecione..."] + colunas_retorno)
        
        with col_val_filtro:
            valores_origem = ["Selecione..."]
            if rpa_origem != "Selecione...":
                valores_origem += df_memoria[rpa_origem].dropna().unique().tolist()
            valor_filtro = st.selectbox("2. Manter apenas placas que responderam:", valores_origem)
            
        with col_btn_filtro:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✂️ APLICAR FILTRO", use_container_width=True):
                if rpa_origem != "Selecione..." and valor_filtro != "Selecione...":
                    # Filtra a memoria permanentemente para conter apenas os registros desejados
                    df_filtrado = df_memoria[df_memoria[rpa_origem] == valor_filtro].copy()
                    st.session_state.df_atual = df_filtrado
                    st.success(f"Tabela filtrada! Restaram {len(df_filtrado)} registros. Agora troque o robô no painel lateral e processe.")
                    time.sleep(2)
                    st.rerun()

    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 PROCESSAR TODOS OS REGISTROS", type="primary", use_container_width=True):
            with st.spinner(f"Executando {automacao_selecionada}..."):
                novo_df = asyncio.run(processar_rpa(st.session_state.df_atual, apenas_pendentes=False))
                st.session_state.df_atual = novo_df
            st.rerun() # Atualiza a tabela na tela
            
    with col2:
        if st.button("🔄 CONTINUAR (Pular Sucessos)", type="secondary", use_container_width=True, 
                     help="Inicia o robô ignorando as linhas que já possuem resposta, ótimo para Failsafe ou Quedas de RDP."):
            with st.spinner(f"Continuando {automacao_selecionada}..."):
                novo_df = asyncio.run(processar_rpa(st.session_state.df_atual, apenas_pendentes=True))
                st.session_state.df_atual = novo_df
            st.rerun()
            
    st.markdown("---")
    
    # Download da planilha consolidada (contém todas as colunas de RETORNO acumuladas)
    processed_data = gerar_relatorio_excel(st.session_state.df_atual)
    st.download_button(
        label="📥 Baixar Relatório Consolidado",
        data=processed_data,
        file_name="Relatorio_Encadeado_Portal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
