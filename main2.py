from telegram import Update
from telegram.ext import *
from import_credential import TELEGRAM_BOT_TOKEN
from user_response_from_llm import user_response_from_llm
from telegram_prettier import format_for_telegram, escape_html_outside_tags, split_message
from voice_to_text import transcribe_audio, record_audio
from AI_voice_gen import generate_and_play
while 1 :
    user_id = "1234"
        # print(context)
        # print(user_id)
    record_audio()
    user_message = transcribe_audio()
    # user_message = input("Enter your Human Prompt")
    ans = user_response_from_llm(user_id, user_message)
    formatted = format_for_telegram(ans)
    safe = escape_html_outside_tags(formatted)
    safe = safe.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")  # ✅ Fix
    print(safe)
    generate_and_play(formatted)

# print()
# for chunk in split_message(safe):
#     await update.message.reply_text(chunk, parse_mode="HTML")