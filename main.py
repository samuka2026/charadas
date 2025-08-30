from flask import Flask, request
import telebot
import os
import json
import random
import threading
import time

# ======================
# 🔧 CONFIGURAÇÕES
# ======================
TOKEN = os.getenv("BOT_TOKEN")  # defina no Render
URL = os.getenv("RENDER_EXTERNAL_URL")  # seu domínio do Render
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ranking e estado
ranking = {}
rodada = {
    "ativa": False,
    "chat_id": None,
    "resposta": None,
    "dicas": [],
    "indice_dica": 0,
    "timer": None
}

# ======================
# 📂 FUNÇÕES AUXILIARES
# ======================
def carregar_charadas():
    with open("charadas.json", "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_ranking():
    with open("ranking.json", "w", encoding="utf-8") as f:
        json.dump(ranking, f, indent=2, ensure_ascii=False)

def carregar_ranking():
    global ranking
    if os.path.exists("ranking.json"):
        with open("ranking.json", "r", encoding="utf-8") as f:
            ranking = json.load(f)

def iniciar_timer():
    def dicas_progressivas():
        while rodada["ativa"] and rodada["indice_dica"] < len(rodada["dicas"]):
            time.sleep(300)  # 5 minutos
            if rodada["ativa"]:
                dica = rodada["dicas"][rodada["indice_dica"]]
                rodada["indice_dica"] += 1
                bot.send_message(rodada["chat_id"], f"💡 Dica: {dica}")
    t = threading.Thread(target=dicas_progressivas)
    t.start()
    rodada["timer"] = t

def encerrar_rodada(revelar=True):
    if rodada["ativa"]:
        if revelar:
            bot.send_message(rodada["chat_id"], f"⏱️ Ninguém acertou! A resposta era: *{rodada['resposta']}*", parse_mode="Markdown")
        rodada.update({"ativa": False, "chat_id": None, "resposta": None, "dicas": [], "indice_dica": 0, "timer": None})

# ======================
# 🤖 COMANDOS DO BOT
# ======================
@bot.message_handler(commands=["emoji_start"])
def start_round(message):
    if rodada["ativa"]:
        bot.reply_to(message, "⚠️ Já existe uma rodada em andamento!")
        return

    charadas = carregar_charadas()
    charada = random.choice(charadas)

    rodada["ativa"] = True
    rodada["chat_id"] = message.chat.id
    rodada["resposta"] = charada["resposta"].lower()
    rodada["dicas"] = charada["dicas"]
    rodada["indice_dica"] = 0

    texto = f"🎭 *Jogo dos Emojis*\n\nCategoria: {charada['categoria']}\n\n🟦 Charada:\n{charada['emoji']}"
    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

    iniciar_timer()

@bot.message_handler(commands=["emoji_rank"])
def mostrar_ranking(message):
    if not ranking:
        bot.reply_to(message, "🏆 Ranking vazio ainda.")
        return
    texto = "🏆 *Ranking Geral*\n\n"
    ordenado = sorted(ranking.items(), key=lambda x: x[1], reverse=True)
    for i, (user, pts) in enumerate(ordenado, start=1):
        texto += f"{i}. {user}: {pts} pts\n"
    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

@bot.message_handler(commands=["emoji_stop"])
def parar_rodada(message):
    encerrar_rodada()
    bot.reply_to(message, "⛔ Rodada encerrada.")

# ======================
# 🎯 VERIFICAR RESPOSTAS
# ======================
@bot.message_handler(func=lambda m: rodada["ativa"])
def verificar_resposta(message):
    resposta = message.text.strip().lower()
    if resposta == rodada["resposta"]:
        user = message.from_user.first_name
        pontos = 10 - (rodada["indice_dica"] * 3)  # menos pontos se já houve dicas
        pontos = max(1, pontos)  # mínimo 1 ponto

        ranking[user] = ranking.get(user, 0) + pontos
        salvar_ranking()

        bot.send_message(message.chat.id, f"✅ {user} acertou! Era *{rodada['resposta']}* 🎉 (+{pontos} pts)", parse_mode="Markdown")
        encerrar_rodada(revelar=False)

# ======================
# 🌐 WEBHOOK FLASK
# ======================
@app.route("/" + TOKEN, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot ativo!", 200

# ======================
# ▶️ INICIAR
# ======================
if __name__ == "__main__":
    carregar_ranking()
    bot.remove_webhook()
    bot.set_webhook(url=URL + "/" + TOKEN)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
