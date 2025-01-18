# bot/bot.py
import os
import telebot

from django.conf import settings
from .models import TelegramBotUser

# Initialize the bot with the token from settings
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your-telegram-bot-token")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user, created = TelegramBotUser.objects.get_or_create(
        user_id=message.chat.id,
        defaults={
            'username': message.chat.username,
            'first_name': message.chat.first_name,
            'last_name': message.chat.last_name
        }
    )
    if created:
        response = "Welcome! You are now registered."
    else:
        response = "Welcome back!"
    bot.reply_to(message, response)

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, message.text)

# Start polling
if __name__ == "__main__":
    bot.polling()