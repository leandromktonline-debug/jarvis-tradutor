import os
import re
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
import edge_tts

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

def extrair_video_id(url: str):
    padroes = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})'
    ]
    for padrao in padroes:
        match = re.search(padrao, url)
        if match:
            return match.group(1)
    return None

async def processar_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    video_id = extrair_video_id(url)

    if not video_id:
        await update.message.reply_text("Por favor, envie um link válido de vídeo ou Shorts do YouTube.")
        return

    msg = await update.message.reply_text("1/3: Obtendo transcrição do vídeo...")
    audio_traduzido = f"ptbr_{update.message.message_id}.mp3"

    try:
        # 1. Obtém as legendas/transcrição direta sem bloqueio de IP
        transcricao_lista = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'pt', 'es'])
        transcricao_texto = " ".join([item['text'] for item in transcricao_lista])

        await msg.edit_text("2/3: Traduzindo e adaptando com Gemini...")

        # 2. Tradução e adaptação coloquial em português
        prompt = (
            "Traduza e adapte a seguinte transcrição de vídeo para o português brasileiro falado. "
            "Garanta fluidez para locução em voz alta e ritmo coloquial natural. "
            "Responda apenas com o texto para narração, sem introduções ou notas de rodapé:\n\n"
            f"{transcricao_texto}"
        )
        resposta = gemini_model.generate_content(prompt)
        texto_ptbr = resposta.text

        await msg.edit_text("3/3: Gerando locução em português...")

        # 3. Geração do áudio em voz neural
        comunicador = edge_tts.Communicate(texto_ptbr, "pt-BR-AntonioNeural")
        await comunicador.save(audio_traduzido)

        await msg.edit_text("Finalizado! Enviando áudio...")
        with open(audio_traduzido, "rb") as audio:
            await update.message.reply_audio(audio=audio, title="Áudio Traduzido (Jarvis)")
        await msg.delete()

    except Exception as e:
        await update.message.reply_text(f"Erro no processamento: {str(e)}")

    finally:
        if os.path.exists(audio_traduzido):
            os.remove(audio_traduzido)

if __name__ == '__main__':
    print("Iniciando Jarvis...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_video))
    app.run_polling()
