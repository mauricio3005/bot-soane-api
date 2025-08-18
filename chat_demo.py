import streamlit as st
import requests
import uuid

# --- CONFIGURAÇÃO DA PÁGINA E TÍTULO ---
st.set_page_config(page_title="Demo Assistente Soane", layout="centered")
st.title("💬 Demonstração da Assistente Virtual")
st.caption("Interaja com a Clara, a assistente virtual da Dra. Soane.")

# --- URL DA SUA API (QUE ESTÁ NO RENDER) ---
# Verifique se esta URL está correta. É o endereço do seu serviço no Render.
URL_DO_BOT_API = "https://bot-soane-api.onrender.com/webhook" 

# --- GERENCIAMENTO DA MEMÓRIA DA CONVERSA NO STREAMLIT ---
# O Streamlit usa um "session_state" para guardar informações de cada usuário
# que acessa a página, garantindo que as conversas não se misturem.

# Inicializa o histórico de mensagens se ele não existir
if "messages" not in st.session_state:
    st.session_state.messages = []

# Gera um ID de usuário único para esta sessão de chat
if "user_id" not in st.session_state:
    st.session_state.user_id = "demo_streamlit_" + str(uuid.uuid4())

# --- FUNÇÃO PARA CHAMAR SUA API NO RENDER ---
def chamar_api_do_bot(id_usuario, mensagem):
    """Envia a mensagem do usuário para a sua API e retorna a resposta."""
    try:
        # Monta o pacote de dados (payload) no formato que sua API espera
        payload = {
            "id_usuario": id_usuario,
            "mensagem": mensagem
        }
        # Faz a chamada POST para a sua API, com um timeout de 60 segundos
        response = requests.post(URL_DO_BOT_API, json=payload, timeout=60)
        
        # Verifica se a chamada foi bem-sucedida
        if response.status_code == 200:
            return response.json()
        else:
            # Retorna uma mensagem de erro se a API falhar
            return {"erro": f"Erro na API: Status {response.status_code}", "resposta_para_usuario": "Desculpe, estou com um problema técnico no momento. Tente novamente mais tarde."}
    
    except requests.exceptions.RequestException as e:
        # Retorna uma mensagem de erro se não conseguir se conectar à API
        return {"erro": f"Erro de conexão: {e}", "resposta_para_usuario": "Não consegui me conectar ao meu cérebro. Verifique a conexão com o servidor."}

# --- LÓGICA DA INTERFACE DE CHAT ---

# Exibe o histórico de mensagens na tela
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Cria o campo de entrada de texto no final da página
if prompt := st.chat_input("Digite sua dúvida aqui..."):
    # Adiciona a mensagem do usuário ao histórico e à tela
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Mostra uma animação de "digitando..." enquanto espera a resposta
    with st.spinner("Clara está digitando..."):
        # Chama a sua API no Render para obter a resposta inteligente
        resposta_api = chamar_api_do_bot(st.session_state.user_id, prompt)

    # Extrai os dados da resposta da API
    resposta_bot = resposta_api.get("resposta_para_usuario", "Não recebi uma resposta válida.")
    gatilho_agendamento = resposta_api.get("gatilho_agendamento", False)
    gatilho_urgencia = resposta_api.get("gatilho_urgencia", False)

    # Adiciona a resposta do bot ao histórico e à tela
    st.session_state.messages.append({"role": "assistant", "content": resposta_bot})
    with st.chat_message("assistant"):
        st.markdown(resposta_bot)
        # Se algum gatilho for ativado, "printamos" um aviso visual na tela da demo
        if gatilho_agendamento:
            st.info("ℹ️ *Gatilho de Agendamento foi detectado pelo sistema!*")
        if gatilho_urgencia:
            st.warning("⚠️ *Gatilho de Urgência foi detectado pelo sistema!*")