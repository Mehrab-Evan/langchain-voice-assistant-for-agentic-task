from telegram import Update
from telegram.ext import *
from import_credential import TELEGRAM_BOT_TOKEN
from user_response_from_llm import user_response_from_llm
from telegram_prettier import format_for_telegram, escape_html_outside_tags, split_message

print('Starting a bot....')


# Commands
async def start_commmand(update, context):
    await update.message.reply_text('Hello! Welcome To Diamond kebab! use / command')

# async def help(update, context):
#     await update.message.reply_text('You can browse menu using /menu\nknow more buy /want_to_know_more\nYou can order by /want_to_order.\nYou also can text me. :)')
#
#
# async def Menu(update, context):
#     text = "What's on your menu?"
#     ans = "It's your head"
#     await update.message.reply_text(ans)
#
#
# async def Want_to_know_more(update, context):
#     text = "Want to know more about you"
#     ans = "I LOVE U"
#     await update.message.reply_text(ans)
#
#
# async def Want_to_buy(update, context):
#     text = "I want to order"
#     ans = "I WILL Buy for u"
#     await update.message.reply_text(ans)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat.id
    # print(context)
    # print(user_id)
    user_message = update.message.text
    ans = user_response_from_llm(user_id, user_message)
    formatted = format_for_telegram(ans)
    safe = escape_html_outside_tags(formatted)
    safe = safe.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")  # ✅ Fix
    print(safe)

    for chunk in split_message(safe):
        await update.message.reply_text(chunk, parse_mode="HTML")


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update has error {update} the error is {context.error}")

if __name__ == '__main__':
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler('start', start_commmand))
    # application.add_handler(CommandHandler('menu', Menu))
    # application.add_handler(CommandHandler('want_to_know_more', Want_to_know_more))
    # application.add_handler(CommandHandler('want_to_order', Want_to_buy))
    application.add_handler(CommandHandler('help', help))

    # Message
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    # ERRORS
    application.add_error_handler(error)
    # Run bot
    application.run_polling(1.0)