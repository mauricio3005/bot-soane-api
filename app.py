import json
import os
import redis # <-- MUDANÇA: Importa a biblioteca do Redis
from openai import OpenAI
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# --- 1. INICIALIZAÇÃO E CONFIGURAÇÃO ---
load_dotenv()
app = Flask(__name__)
client = OpenAI()

# --- MUDANÇA: Conexão com o Banco de Dados Redis ---
# Pega a URL do Redis das variáveis de ambiente que configuramos no Render
redis_url = os.environ.get("REDIS_URL")
if not redis_url:
    raise Exception("A variável de ambiente REDIS_URL não foi configurada.")
# Conecta ao Redis. O 'decode_responses=True' facilita o trabalho com strings.
redis_client = redis.from_url(redis_url, decode_responses=True)
# --------------------------------------------------

# --- 2. CARREGAMENTO DA BASE DE CONHECIMENTO ---
base_path = "banco de dados"
# ... (o resto do carregamento dos arquivos continua igual)
try:
    with open(os.path.join(base_path, "instruções_soane.txt"), "r", encoding="utf-8") as f:
        instrucao = f.read()
    with open(os.path.join(base_path, "conteudo_principal.json"), "r", encoding="utf-8") as f:
        cerebro_principal = json.load(f)
    with open(os.path.join(base_path, "faq.json"), "r", encoding="utf-8") as f:
        faq = json.load(f)
except FileNotFoundError as e:
    print(f"Erro Crítico: Arquivo de dados não encontrado - {e}.")
    exit()

instrucao_completa = (
    instrucao +
    "\n\n--- BASE DE CONHECIMENTO PRINCIPAL ---\n" +
    json.dumps(cerebro_principal, ensure_ascii=False, indent=2) +
    "\n\n--- PERGUNTAS E RESPOSTAS FREQUENTES ---\n" +
    json.dumps(faq, ensure_ascii=False, indent=2)
)

# --- MUDANÇA: A variável 'conversas_ativas' foi REMOVIDA. Agora os dados vivem no Redis. ---

# --- 4. A ROTA DA API (O WEBHOOK) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    dados_recebidos = request.get_json()
    if not dados_recebidos or 'id_usuario' not in dados_recebidos or 'mensagem' not in dados_recebidos:
        return jsonify({"erro": "Dados inválidos."}), 400

    id_usuario = dados_recebidos['id_usuario']
    mensagem_usuario = dados_recebidos['mensagem']
    
    # --- MUDANÇA: Busca os dados do usuário do Redis, não do dicionário ---
    dados_usuario_json = redis_client.get(id_usuario)
    dados_usuario = json.loads(dados_usuario_json) if dados_usuario_json else None
    # -------------------------------------------------------------------

    if not dados_usuario:
        dados_usuario = {
            "historico": [{"role": "system", "content": instrucao_completa}],
            "estado_agendamento": "nenhum",
            "estado_urgencia": "nenhum"
        }
        print(f"Novo usuário detectado: {id_usuario}")

    dados_usuario["historico"].append({"role": "user", "content": mensagem_usuario})

    try:
        # ... (A chamada para a OpenAI e o processamento da resposta continuam iguais)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=dados_usuario["historico"],
            response_format={"type": "json_object"}
        )
        resposta_bruta = response.choices[0].message.content
        dados_resposta = json.loads(resposta_bruta)
        texto_para_usuario = dados_resposta.get("resposta_para_usuario", "Desculpe...")
        gatilho_agendamento = dados_resposta.get("precisa_agendar", False)
        gatilho_urgencia = dados_resposta.get("conversa_urgente", False)

        dados_usuario["historico"].append({"role": "assistant", "content": texto_para_usuario})

        if gatilho_agendamento and dados_usuario["estado_agendamento"] == "nenhum":
            dados_usuario["estado_agendamento"] = "iniciado"
        
        # --- MUDANÇA: Salva o dossiê atualizado de volta no Redis ---
        redis_client.set(id_usuario, json.dumps(dados_usuario))
        # Opcional: define um tempo de expiração para a conversa (ex: 24 horas)
        redis_client.expire(id_usuario, 86400)
        # -------------------------------------------------------------
        
        return jsonify({
            "resposta_para_usuario": texto_para_usuario,
            "gatilho_agendamento": gatilho_agendamento,
            "gatilho_urgencia": gatilho_urgencia
        })

    except Exception as e:
        print(f"Erro ao processar a mensagem para {id_usuario}: {e}")
        return jsonify({"erro": "Ocorreu um erro interno no servidor."}), 500

# --- 5. COMANDO PARA INICIAR O SERVIDOR ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
