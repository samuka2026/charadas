from flask import Flask, request
import telebot
import os
import json
import random
import threading
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ======================
# CONFIGURAÇÕES
# ======================
TOKEN = os.getenv("BOT_TOKEN")
URL = os.getenv("RENDER_EXTERNAL_URL")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN não definido nas variáveis de ambiente!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ======================
# ESTADO DO JOGO
# ======================
ranking = {}
rodada = {
    "ativa": False,
    "chat_id": None,
    "resposta": None,
    "emoji": None,
    "categoria": None,
    "dicas": [],
    "indice_dica": 0,
    "timer": None,
    "opcoes": [],
    "tentativas": {}  # Guarda os usuários que já tentaram nesta dica
}

# ======================
# FUNÇÕES AUXILIARES
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

def montar_inline_buttons():
    markup = InlineKeyboardMarkup()
    for i, opcao in enumerate(rodada['opcoes']):
        markup.add(InlineKeyboardButton(opcao, callback_data=str(i)))
    return markup

def montar_balão_inicial():
    texto = "🎲 *DESAFIO DE EMOJIS* 🎲\n\n"
    texto += f"🔮 Categoria: *{rodada['categoria']}*\n\n"
    texto += f"🟦 Charada: {rodada['emoji']}\n\n"  # Charada na mesma linha
    texto += "💡 Pontuação por acerto:\n"
    texto += "🔹 Sem dica: 10 pts\n"
    texto += "🔹 1ª dica: 6 pts\n"
    texto += "🔹 2ª dica: 3 pts\n"
    texto += "🔹 3ª dica: 1 pt\n"
    texto += "🔹 Ninguém acerta: 0 pts\n\n"
    if ranking:
        texto += "🏆 Ranking Atual:\n"
        ordenado = sorted(ranking.items(), key=lambda x: x[1], reverse=True)
        for i, (user, pts) in enumerate(ordenado, start=1):
            medalha = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "⭐"
            texto += f"{medalha} {user} — {pts} pts\n"
    return texto

def iniciar_timer():
    def dicas_progressivas():
        while rodada["ativa"] and rodada["indice_dica"] < len(rodada["dicas"]):
            time.sleep(60)  # 1 minuto entre dicas
            if rodada["ativa"]:
                dica = rodada["dicas"][rodada["indice_dica"]]
                rodada["indice_dica"] += 1
                rodada["tentativas"] = {}  # resetar tentativas para a próxima dica
                bot.send_message(rodada["chat_id"], f"💡 Dica {rodada['indice_dica']}: {dica}")
        # Se ninguém acertou até o final
        if rodada["ativa"]:
            bot.send_message(rodada["chat_id"], f"⏱️ Ninguém acertou! A resposta era: *{rodada['resposta']}*", parse_mode="Markdown")
            rodada.update({k: None if k != "ativa" else False for k in rodada})
    t = threading.Thread(target=dicas_progressivas)
    t.start()
    rodada["timer"] = t

# ======================
# COMANDOS
# ======================
@bot.message_handler(commands=["emoji_start"])
def start_round(message):
    if rodada["ativa"]:
        bot.reply_to(message, "⚠️ Já existe uma rodada em andamento!")
        return

    charadas = carregar_charadas()
    charada = random.choice(charadas)

    todas_respostas = [
    c['resposta']
    for c in charadas
    if c['resposta'] != charada['resposta'] and c['categoria'] == charada['categoria']
]
    opcoes = random.sample(todas_respostas, 7)
    opcoes.append(charada['resposta'])
    random.shuffle(opcoes)

    rodada.update({
        "ativa": True,
        "chat_id": message.chat.id,
        "resposta": charada["resposta"],
        "emoji": charada["emoji"],
        "categoria": charada["categoria"],
        "dicas": charada["dicas"],
        "indice_dica": 0,
        "opcoes": opcoes,
        "tentativas": {}
    })

    bot.send_message(
        rodada["chat_id"],
        montar_balão_inicial(),
        parse_mode="Markdown",
        reply_markup=montar_inline_buttons()
    )

    iniciar_timer()

@bot.message_handler(commands=["emoji_rank"])
def mostrar_ranking(message):
    if not ranking:
        bot.reply_to(message, "🏆 Ranking vazio ainda.")
        return
    texto = "🏆 *Ranking Geral*\n\n"
    ordenado = sorted(ranking.items(), key=lambda x: x[1], reverse=True)
    for i, (user, pts) in enumerate(ordenado, start=1):
        medalha = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "⭐"
        texto += f"{medalha} {user}: {pts} pts\n"
    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

@bot.message_handler(commands=["emoji_stop"])
def parar_rodada(message):
    if rodada["ativa"]:
        rodada.update({k: None if k != "ativa" else False for k in rodada})
        bot.reply_to(message, "⛔ Rodada encerrada.")
    else:
        bot.reply_to(message, "⚠️ Não há nenhuma rodada em andamento.")

# ======================
# CALLBACK
# ======================
@bot.callback_query_handler(func=lambda call: rodada["ativa"])
def callback_resposta(call):
    user = call.from_user.first_name
    indice = int(call.data)
    escolha = rodada["opcoes"][indice]

    if user in rodada["tentativas"]:
        bot.answer_callback_query(call.id, f"⏳ {user}, você só pode tentar novamente na próxima dica!")
        return

    rodada["tentativas"][user] = True
    bot.answer_callback_query(call.id, f"{user} respondeu.")  # Balão pequeno

    pontos_por_dica = [10, 6, 3, 1]
    pontos = pontos_por_dica[rodada["indice_dica"]] if rodada["indice_dica"] < 4 else 1

    if escolha == rodada["resposta"]:
        ranking[user] = ranking.get(user, 0) + pontos
        salvar_ranking()
        bot.send_message(
            rodada["chat_id"],
            f"✅ *{user} acertou!* 🎉\nVocê ganhou *{pontos} pts*\n\n🎯 Para iniciar um novo desafio, use /emoji_start",
            parse_mode="Markdown"
        )
        rodada.update({k: None if k != "ativa" else False for k in rodada})

# ======================
# WEBHOOK FLASK
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
# INICIAR
# ======================
if __name__ == "__main__":
    carregar_ranking()
    bot.remove_webhook()
    bot.set_webhook(url=URL + "/" + TOKEN)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
