import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import yt_dlp
from groq import Groq
import google.generativeai as genai
import edge_tts

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

async def processar_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not ("youtube.com" in url or "youtu.be" in url):
        await update.message.reply_text("Envie um link válido do YouTube.")
        return

    msg = await update.message.reply_text("1/4: A transferir áudio original...")

    audio_original = f"orig_{update.message.message_id}.mp3"
    audio_traduzido = f"ptbr_{update.message.message_id}.mp3"

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': audio_original.replace('.mp3', '.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await msg.edit_text("2/4: A transcrever o áudio...")

        with open(audio_original, "rb") as file:
            transcricao = groq_client.audio.transcriptions.create(
                file=(audio_original, file.read()),
                model="whisper-large-v3",
                response_format="text"
            )

        await msg.edit_text("3/4: A traduzir e a adaptar para português...")

        prompt = (
            "Traduza a transcrição a seguir para o português brasileiro falado. "
            "Mantenha um tom natural e coloquial, adaptando termos técnicos para o público brasileiro. "
            "Entregue apenas o texto para ser lido em áudio, sem introduções ou observações:\n\n"
            f"{transcricao}"
        )
        resposta = gemini_model.generate_content(prompt)
        texto_ptbr = resposta.text

        await msg.edit_text("4/4: A gerar voz em português...")

        comunicador = edge_tts.Communicate(texto_ptbr, "pt-BR-AntonioNeural")
        await comunicador.save(audio_traduzido)

        await msg.edit_text("Concluído! A enviar o áudio...")
        with open(audio_traduzido, "rb") as audio:
            await update.message.reply_audio(audio=audio, title="Vídeo Traduzido (Áudio)")
        await msg.delete()

    except Exception as e:
        await update.message.reply_text(f"Erro no processamento: {str(e)}")

    finally:
        for f in [audio_original, audio_traduzido]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == '__main__':
    print("A iniciar Jarvis...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_video))
    app.run_polling()
