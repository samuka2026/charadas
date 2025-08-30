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
TOKEN = os.getenv("BOT_TOKEN")
URL = os.getenv("RENDER_EXTERNAL_URL")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN não definido nas variáveis de ambiente!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ranking e estado
ranking = {}
rodada = {
    "ativa": False,
    "chat_id": None,
    "resposta": None,
    "emoji": None,
    "dicas": [],
    "indice_dica": 0,
    "timer": None,
    "numero": 0
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

def enviar_balão_charada():
    """Envia o balão de charada estilizado com ranking"""
    charada_texto = f"🎲✨ DESAFIO DE EMOJIS ✨🎲\n\n"
    charada_texto += f"🔮 Rodada #{rodada['numero']}\n"
    charada_texto += f"🟦 Charada:\n{rodada['emoji']}\n\n"

    # Dica atual
    if rodada['indice_dica'] > 0:
        charada_texto += f"💡 Dica {rodada['indice_dica']}: {rodada['dicas'][rodada['indice_dica']-1]}\n\n"

    # Ranking
    if ranking:
        charada_texto += "🏆 Ranking Atual:\n"
        ordenado = sorted(ranking.items(), key=lambda x: x[1], reverse=True)
        for i, (user, pts) in enumerate(ordenado, start=1):
            medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "⭐"
            charada_texto += f"{medalha} {user} — {pts} pts\n"

    bot.send_message(rodada['chat_id'], charada_texto, parse_mode="Markdown")

def iniciar_timer():
    def dicas_progressivas():
        while rodada["ativa"] and rodada["indice_dica"] < len(rodada["dicas"]):
            time.sleep(60)  # 1 minuto
            if rodada["ativa"]:
                rodada["indice_dica"] += 1
                dica = rodada["dicas"][rodada["indice_dica"]-1]
                bot.send_message(rodada["chat_id"], f"💡 Dica {rodada['indice_dica']}: {dica}")
                enviar_balão_charada()
    t = threading.Thread(target=dicas_progressivas)
    t.start()
    rodada["timer"] = t

def encerrar_rodada(revelar=True):
    if rodada["ativa"]:
        if revelar:
            bot.send_message(
                rodada["chat_id"],
                f"⏱️ Ninguém acertou! A resposta era: *{rodada['resposta']}*",
                parse_mode="Markdown"
            )
        rodada.update({
            "ativa": False, "chat_id": None, "resposta": None,
            "emoji": None, "dicas": [], "indice_dica": 0, "timer": None
        })

# ======================
# 🤖 COMANDOS DO BOT
# ======================
@bot.message_handler(commands=["emoji"])
def start_round(message):
    if rodada["ativa"]:
        bot.reply_to(message, "⚠️ Já existe uma rodada em andamento!")
        return

    charadas = carregar_charadas()
    charada = random.choice(charadas)

    rodada["ativa"] = True
    rodada["chat_id"] = message.chat.id
    rodada["resposta"] = charada["resposta"].lower()
    rodada["emoji"] = charada["emoji"]
    rodada["dicas"] = charada["dicas"]
    rodada["indice_dica"] = 0
    rodada["numero"] += 1

    enviar_balão_charada()
    iniciar_timer()

@bot.message_handler(commands=["emoji_rank"])
def mostrar_ranking(message):
    if not ranking:
        bot.reply_to(message, "🏆 Ranking vazio ainda.")
        return
    texto = "🏆 *Ranking Geral*\n\n"
    ordenado = sorted(ranking.items(), key=lambda x: x[1], reverse=True)
    for i, (user, pts) in enumerate(ordenado, start=1):
        medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "⭐"
        texto += f"{medalha} {user}: {pts} pts\n"
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
        pontos_por_dica = [10, 6, 3, 1]
        indice = rodada['indice_dica'] if rodada['indice_dica'] < 4 else 3
        pontos = pontos_por_dica[indice]

        ranking[user] = ranking.get(user, 0) + pontos
        salvar_ranking()

        bot.send_message(
            message.chat.id,
            f"✅ {user} acertou! Era *{rodada['resposta']}* 🎉 (+{pontos} pts)",
            parse_mode="Markdown"
        )
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
