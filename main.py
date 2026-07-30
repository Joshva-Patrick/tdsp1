import os
import json
from flask import Flask, send_from_directory
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from agent import run_agent_task
from logger import log_event, LOG_FILE_PATH

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Make sure your server URL matches your deployment host (e.g. Render/Railway)
PUBLIC_HOST_URL = os.getenv("PUBLIC_HOST_URL", "https://your-app.onrender.com")

app = Flask(__name__)

@app.route("/run.jsonl")
def serve_logs():
    return send_from_directory("static", "run.jsonl", mimetype="application/x-jsonlines")

@app.route("/health")
def health():
    return "OK", 200

# Memory dictionary for tracking multi-turn context
user_chat_history = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()

    # Log incoming request
    log_event({"chat_id": chat_id, "event": "incoming_message", "text": user_text})

    if chat_id not in user_chat_history:
        user_chat_history[chat_id] = []
    user_chat_history[chat_id].append({"role": "user", "content": user_text})

    def agent_logger(log_data):
        log_event({"chat_id": chat_id, **log_data})

    # Run agent loop with Grok
    raw_answer = run_agent_task(user_chat_history[chat_id], agent_logger)

    final_response = {
        "answer": raw_answer.get("answer", raw_answer),
        "log_url": f"{PUBLIC_HOST_URL}/run.jsonl"
    }

    json_response_str = json.dumps(final_response)
    user_chat_history[chat_id].append({"role": "assistant", "content": json_response_str})

    # Send strictly valid JSON output to user
    await update.message.reply_text(json_response_str)

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot started...")
    application.run_polling()