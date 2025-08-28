import streamlit as st
import requests
import uuid

# --- CONFIGURAÇÃO DA PÁGINA E TÍTULO ---
st.set_page_config(page_title="Demo Assistente Soane", layout="centered")
st.title("💬 Demonstração da Assistente Virtual")
st.caption("Interaja com a Clara, a assistente virtual da Dra. Soane.")

# --- URL DA SUA API (QUE ESTÁ NO RENDER) ---
URL_DO_BOT_API = "https://bot-soane-api.onrender.com/webhook"

# --- GERENCIAMENTO DA MEMÓRIA DA CONVERSA NO STREAMLIT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_id" not in st.session_state:
    st.session_state.user_id = "demo_streamlit_" + str(uuid.uuid4())

# --- FUNÇÃO PARA CHAMAR SUA API NO RENDER ---
def chamar_api_do_bot(id_usuario, mensagem):
    """Envia a mensagem do usuário para a sua API e retorna a resposta."""
    try:
        payload = {
            "id_usuario": id_usuario,
            "mensagem": mensagem
        }
        response = requests.post(URL_DO_BOT_API, json=payload, timeout=60)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"erro": f"Erro na API: Status {response.status_code}", "resposta_para_usuario": "Desculpe, estou com um problema técnico no momento. Tente novamente mais tarde."}
    
    except requests.exceptions.RequestException as e:
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
        resposta_api = chamar_api_do_bot(st.session_state.user_id, prompt)

    # --- MUDANÇA: Extrai TODOS os gatilhos da resposta da API ---
    resposta_bot = resposta_api.get("resposta_para_usuario", "Não recebi uma resposta válida.")
    gatilho_agendamento = resposta_api.get("gatilho_agendamento", False)
    gatilho_urgencia = resposta_api.get("gatilho_urgencia", False)
    gatilho_humano = resposta_api.get("gatilho_humano", False)
    gatilho_contato = resposta_api.get("gatilho_contato", False)
    gatilho_dr_tiago = resposta_api.get("gatilho_dr_tiago", False)
    # ------------------------------------------------------------

    # Adiciona a resposta do bot ao histórico e à tela
    st.session_state.messages.append({"role": "assistant", "content": resposta_bot})
    with st.chat_message("assistant"):
        st.markdown(resposta_bot)
        
        # --- MUDANÇA: Exibe um aviso visual para CADA gatilho ativado ---
        if gatilho_agendamento:
            st.info("ℹ️ *Gatilho de Agendamento foi detectado!*")
        if gatilho_urgencia:
            st.warning("⚠️ *Gatilho de Urgência foi detectado!*")
        if gatilho_humano:
            st.error("🚨 *Gatilho de Atendimento Humano foi detectado!*")
        if gatilho_contato:
            st.info("📞 *Gatilho de Pedido de Contato foi detectado!*")
        if gatilho_dr_tiago:
            st.success("⭐ *Gatilho de Paciente Dr. Tiago foi detectado!*")
        # -----------------------------------------------------------------
