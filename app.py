import json
import os
from openai import OpenAI
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# --- 1. INICIALIZAÇÃO E CONFIGURAÇÃO ---

# Carrega variáveis de ambiente (como a OPENAI_API_KEY) de um arquivo .env
load_dotenv()

# Inicializa o Flask App e o cliente da OpenAI
app = Flask(__name__)
client = OpenAI() # A chave será lida automaticamente das variáveis de ambiente

# --- 2. CARREGAMENTO DA BASE DE CONHECIMENTO (FEITO UMA VEZ) ---

# Define os caminhos para os arquivos de dados
base_path = "banco de dados"
instrucoes_path = os.path.join(base_path, "instruções_soane.txt")
conteudos = os.path.join(base_path, "conteudos.json")
faq_path = os.path.join(base_path, "faq.json")

# Tenta carregar todos os arquivos necessários quando o servidor inicia
try:
    with open(instrucoes_path, "r", encoding="utf-8") as f:
        instrucao = f.read()
    with open(conteudos, "r", encoding="utf-8") as f:
        cerebro_principal = json.load(f)
    with open(faq_path, "r", encoding="utf-8") as f:
        faq = json.load(f)
except FileNotFoundError as e:
    print(f"Erro Crítico: Arquivo de dados não encontrado - {e}.")
    exit()

# Monta a instrução de sistema completa que será usada para cada novo usuário
instrucao_completa = (
    instrucao +
    "\n\n--- BASE DE CONHECIMENTO PRINCIPAL ---\n" +
    json.dumps(cerebro_principal, ensure_ascii=False, indent=2) +
    "\n\n--- PERGUNTAS E RESPOSTAS FREQUENTES ---\n" +
    json.dumps(faq, ensure_ascii=False, indent=2)
)

# --- 3. GERENCIADOR DE CONVERSAS (MEMÓRIA DO BOT) ---

# Dicionário para armazenar o estado e o histórico de cada usuário
conversas_ativas = {}

# --- 4. A ROTA DA API (O WEBHOOK QUE RECEBE AS MENSAGENS) ---

@app.route('https://bot-soane-api.onrender.com', methods=['POST'])
def webhook():
    # Extrai os dados enviados pelo n8n ou provedor do WhatsApp
    dados_recebidos = request.get_json()

    # Validação básica dos dados recebidos
    if not dados_recebidos or 'id_usuario' not in dados_recebidos or 'mensagem' not in dados_recebidos:
        return jsonify({"erro": "Dados inválidos. 'id_usuario' e 'mensagem' são obrigatórios."}), 400

    id_usuario = dados_recebidos['id_usuario']
    mensagem_usuario = dados_recebidos['mensagem']
    
    # Busca o "dossiê" do usuário (histórico e estados)
    dados_usuario = conversas_ativas.get(id_usuario)

    # Se for um novo usuário, cria um novo dossiê para ele
    if not dados_usuario:
        dados_usuario = {
            "historico": [{"role": "system", "content": instrucao_completa}],
            "estado_agendamento": "nenhum",
            "estado_urgencia": "nenhum"
        }
        print(f"Novo usuário detectado: {id_usuario}")

    # Adiciona a nova mensagem do usuário ao seu histórico pessoal
    dados_usuario["historico"].append({"role": "user", "content": mensagem_usuario})

    try:
        # Chama a API da OpenAI com o histórico específico deste usuário
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=dados_usuario["historico"],
            response_format={"type": "json_object"}
        )

        resposta_bruta = response.choices[0].message.content
        dados_resposta = json.loads(resposta_bruta)

        texto_para_usuario = dados_resposta.get("resposta_para_usuario", "Desculpe, não consegui processar sua solicitação.")
        gatilho_agendamento = dados_resposta.get("precisa_agendar", False)
        gatilho_urgencia = dados_resposta.get("conversa_urgente", False)

        # Adiciona a resposta da IA ao histórico do usuário
        dados_usuario["historico"].append({"role": "assistant", "content": texto_para_usuario})

        # --- Lógica da Máquina de Estados ---
        if gatilho_agendamento and dados_usuario["estado_agendamento"] == "nenhum":
            dados_usuario["estado_agendamento"] = "iniciado"
            print(f"Gatilho de AGENDAMENTO acionado para o usuário {id_usuario}")
        
        # Aqui você pode adicionar lógicas para resetar o estado, se necessário

        # Salva o dossiê atualizado de volta na memória
        conversas_ativas[id_usuario] = dados_usuario
        
        # Devolve uma resposta estruturada para o n8n
        return jsonify({
            "resposta_para_usuario": texto_para_usuario,
            "gatilho_agendamento": gatilho_agendamento and dados_usuario["estado_agendamento"] == "iniciado",
            "gatilho_urgencia": gatilho_urgencia # Ajustar com máquina de estados se necessário
        })

    except Exception as e:
        print(f"Erro ao processar a mensagem para {id_usuario}: {e}")
        return jsonify({"erro": "Ocorreu um erro interno no servidor."}), 500

# --- 5. COMANDO PARA INICIAR O SERVIDOR ---
if __name__ == '__main__':
    # O host='0.0.0.0' permite que a API seja acessível de fora do container/máquina

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
