import json
import os
import redis
from openai import OpenAI
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

# --- 1. INICIALIZAÇÃO E CONFIGURAÇÃO (Sem alterações) ---
load_dotenv()
app = Flask(__name__)
CORS(app)
client = OpenAI()

redis_url = os.environ.get("REDIS_URL")
if not redis_url:
    raise Exception("A variável de ambiente REDIS_URL não foi configurada.")
redis_client = redis.from_url(redis_url, decode_responses=True)

# --- 2. CARREGAMENTO DA BASE DE CONHECIMENTO (Sem alterações) ---
try:
    with open(os.path.join("banco de dados", "instruções_soane.txt"), "r", encoding="utf-8") as f:
        instrucao_completa = f.read() # Carregamos o prompt completo uma vez
    with open(os.path.join("banco de dados", "conteudos.json"), "r", encoding="utf-8") as f:
        cerebro_principal = json.load(f)
    with open(os.path.join("banco de dados", "faq.json"), "r", encoding="utf-8") as f:
        faq = json.load(f)
except FileNotFoundError as e:
    print(f"Erro Crítico: Arquivo de dados não encontrado - {e}.")
    exit()

# Adiciona a base de conhecimento à instrução principal
instrucao_completa += (
    "\n\n--- BASE DE CONHECIMENTO PRINCIPAL ---\n" +
    json.dumps(cerebro_principal, ensure_ascii=False, indent=2) +
    "\n\n--- PERGUNTAS E RESPOSTAS FREQUENTES ---\n" +
    json.dumps(faq, ensure_ascii=False, indent=2)
)

# --- 3. A ROTA DA API (COM A NOVA LÓGICA REDIS) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    dados_recebidos = request.get_json()
    if not dados_recebidos or 'id_usuario' not in dados_recebidos or 'mensagem' not in dados_recebidos:
        return jsonify({"erro": "Dados inválidos."}), 400

    id_usuario = dados_recebidos['id_usuario']
    mensagem_usuario = dados_recebidos['mensagem']
    
    # --- MUDANÇA: BUSCA OS DADOS DE FORMA ESTRUTURADA DO REDIS ---
    profile_key = f"user:{id_usuario}:profile"
    history_key = f"user:{id_usuario}:history"

    # Pega o perfil (metadados e estados) do usuário. É um Hash.
    dados_perfil = redis_client.hgetall(profile_key)
    
    if not dados_perfil:
        print(f"Novo usuário detectado: {id_usuario}")
        # Cria um perfil inicial para o novo usuário
        dados_perfil = {
            "estado_agendamento": "nenhum",
            "estado_urgencia": "nenhum",
            "precisa_atendimento_humano": "false" # Usamos strings para Hashes
        }
        redis_client.hset(profile_key, mapping=dados_perfil)
        # O histórico começa apenas com a instrução do sistema
        historico_conversa = [{"role": "system", "content": instrucao_completa}]
    else:
        # Carrega o histórico existente. É uma Lista.
        # lrange(key, 0, -1) pega todos os itens da lista.
        historico_json = redis_client.lrange(history_key, 0, -1)
        historico_conversa = [json.loads(item) for item in historico_json]

    # Adiciona a nova mensagem do usuário à conversa
    historico_conversa.append({"role": "user", "content": mensagem_usuario})

    try:
        # --- (A chamada à OpenAI continua igual) ---
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=historico_conversa,
            response_format={"type": "json_object"}
        )
        resposta_bruta = response.choices[0].message.content
        dados_resposta = json.loads(resposta_bruta)

        texto_para_usuario = dados_resposta.get("resposta_para_usuario", "Desculpe...")
        gatilho_agendamento = dados_resposta.get("precisa_agendar", False)
        gatilho_urgencia = dados_resposta.get("conversa_urgente", False)
        gatilho_humano = dados_resposta.get("precisa_atendimento_humano", False)
        
        # Adiciona a resposta da IA à conversa
        historico_conversa.append({"role": "assistant", "content": texto_para_usuario})

        # --- MUDANÇA: SALVA OS DADOS DE FORMA ESTRUTURADA NO REDIS ---
        # 1. Atualiza o estado no perfil (Hash)
        if gatilho_agendamento and dados_perfil.get("estado_agendamento") == "nenhum":
            redis_client.hset(profile_key, "estado_agendamento", "iniciado")
        
        # 2. Adiciona as duas últimas mensagens (user e assistant) ao histórico (Lista)
        redis_client.rpush(history_key, json.dumps({"role": "user", "content": mensagem_usuario}))
        redis_client.rpush(history_key, json.dumps({"role": "assistant", "content": texto_para_usuario}))
        
        # 3. Se necessário, adiciona o usuário à fila de atendimento (Set)
        if gatilho_humano:
            redis_client.hset(profile_key, "precisa_atendimento_humano", "true")
            redis_client.sadd("queue:human_attention", id_usuario)

        # Define um tempo de expiração para todas as chaves do usuário
        redis_client.expire(profile_key, 86400) # 24 horas
        redis_client.expire(history_key, 86400)

        return jsonify(dados_resposta)

    except Exception as e:
        print(f"Erro ao processar a mensagem para {id_usuario}: {e}")
        return jsonify({"erro": "Ocorreu um erro interno no servidor."}), 500

# --- 5. COMANDO PARA INICIAR O SERVIDOR (Sem alterações) ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))


