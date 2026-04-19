@'
import logging
import sqlite3
import secrets
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8206275772:AAGGRf1u50iDCziHS0SCHSyijddw4Z8DAL8"
YOUR_ID = 6018936021

logging.basicConfig(level=logging.INFO)

# База данных
conn = sqlite3.connect('anon_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        link_code TEXT UNIQUE,
        name TEXT,
        username TEXT,
        registered_at TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        to_user_id INTEGER,
        to_link_code TEXT,
        text TEXT,
        timestamp TEXT,
        is_read INTEGER DEFAULT 0,
        reply_to_id INTEGER DEFAULT NULL
    )
''')

try:
    cursor.execute("ALTER TABLE messages ADD COLUMN reply_to_id INTEGER DEFAULT NULL")
except:
    pass

conn.commit()

def generate_link_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(6))
        cursor.execute("SELECT 1 FROM users WHERE link_code = ?", (code,))
        if not cursor.fetchone():
            return code

def get_main_keyboard():
    """Клавиатура с кнопками для быстрого доступа"""
    keyboard = [
        [KeyboardButton("📋 Моя ссылка"), KeyboardButton("📬 Полученные")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context):
    args = context.args
    target_code = args[0] if args else None
    user_id = update.effective_user.id
    
    cursor.execute("SELECT link_code FROM users WHERE telegram_id = ?", (user_id,))
    existing_user = cursor.fetchone()
    
    if target_code:
        cursor.execute("SELECT name, telegram_id FROM users WHERE link_code = ?", (target_code,))
        target_user = cursor.fetchone()
        
        if target_user:
            context.user_data['reply_to_code'] = target_code
            context.user_data['reply_to_user_id'] = target_user[1]
            await update.message.reply_text(
                "📝 Напиши сообщение. Оно будет отправлено анонимно.",
                reply_markup=None
            )
            return
    
    if not existing_user:
        link_code = generate_link_code()
        cursor.execute('''
            INSERT INTO users (telegram_id, link_code, name, username, registered_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, link_code, update.effective_user.first_name, update.effective_user.username, datetime.now().isoformat()))
        conn.commit()
        
        bot_username = (await context.bot.get_me()).username
        profile_link = f"https://t.me/{bot_username}?start={link_code}"
        
        await update.message.reply_text(
            f"🔐 Твоя ссылка для анонимных сообщений:\n`{profile_link}`\n\n"
            f"Вставь её в профиль. Любой, кто перейдет, сможет написать тебе.\n"
            f"Ты можешь отвечать на сообщения кнопкой «Ответить».",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await main_menu(update, context)

async def main_menu(update: Update, context):
    user_id = update.effective_user.id
    cursor.execute("SELECT link_code FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        bot_username = (await context.bot.get_me()).username
        profile_link = f"https://t.me/{bot_username}?start={user[0]}"
        await update.message.reply_text(
            f"📎 Твоя ссылка: `{profile_link}`\n\n"
            f"Вставь её в профиль, чтобы получать анонимные сообщения.",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "Нажми /start чтобы получить ссылку.",
            reply_markup=get_main_keyboard()
        )

async def my_link(update: Update, context):
    user_id = update.effective_user.id
    cursor.execute("SELECT link_code FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        bot_username = (await context.bot.get_me()).username
        profile_link = f"https://t.me/{bot_username}?start={user[0]}"
        await update.message.reply_text(
            f"📎 Твоя ссылка:\n`{profile_link}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Напиши /start чтобы получить ссылку.")

async def inbox_command(update: Update, context):
    user_id = update.effective_user.id
    cursor.execute("SELECT link_code FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        await update.message.reply_text("Напиши /start чтобы получить ссылку.")
        return
    
    user_code = user[0]
    
    cursor.execute('''
        SELECT id, text, timestamp 
        FROM messages 
        WHERE to_link_code = ? 
        ORDER BY timestamp DESC
    ''', (user_code,))
    
    messages = cursor.fetchall()
    
    if not messages:
        await update.message.reply_text("📭 Нет сообщений.")
        return
    
    for msg in messages:
        cursor.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (msg[0],))
    conn.commit()
    
    response = f"📬 Получено сообщений: {len(messages)}\n\n"
    for i, msg in enumerate(messages[:10], 1):
        response += f"{i}. {msg[2][:16]}\n   {msg[1][:150]}\n\n"
    
    await update.message.reply_text(response)

async def help_command(update: Update, context):
    await update.message.reply_text(
        "📌 Как это работает\n\n"
        "• Получи свою ссылку через /start\n"
        "• Вставь ссылку в профиль\n"
        "• Любой, кто перейдет по ссылке, сможет написать тебе анонимно\n"
        "• На полученные сообщения можно ответить кнопкой «Ответить»\n"
        "• Все ответы тоже анонимны",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context):
    user = update.effective_user
    message_text = update.message.text
    
    # Обработка текстовых команд с клавиатуры
    if message_text == "📋 Моя ссылка":
        await my_link(update, context)
        return
    elif message_text == "📬 Полученные":
        await inbox_command(update, context)
        return
    elif message_text == "❓ Помощь":
        await help_command(update, context)
        return
    
    # Проверка на ответ
    reply_to_user_id = context.user_data.get('reply_to_user_id')
    reply_to_msg_id = context.user_data.get('reply_to_msg_id')
    
    if reply_to_user_id and reply_to_msg_id:
        try:
            cursor.execute("SELECT from_user_id, text, to_link_code FROM messages WHERE id = ?", (reply_to_msg_id,))
            original = cursor.fetchone()
            
            if original:
                original_sender_id = original[0]
                original_text = original[1]
                
                keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"reply_to_{reply_to_msg_id}")]]
                
                await context.bot.send_message(
                    chat_id=reply_to_user_id,
                    text=f"🔔 Ответ\n\n"
                         f"Твой вопрос:\n{original_text[:100]}\n\n"
                         f"Ответ:\n{message_text}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                cursor.execute('''
                    INSERT INTO messages (from_user_id, to_user_id, to_link_code, text, timestamp, reply_to_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user.id, original_sender_id, original[2], message_text, datetime.now().isoformat(), reply_to_msg_id))
                conn.commit()
                
                await context.bot.send_message(
                    chat_id=YOUR_ID,
                    text=f"🔄 Ответ\nОт: {user.first_name} (@{user.username or 'нет'})\nID: {user.id}\nКому: {original_sender_id}\nТекст: {message_text}"
                )
                
                await update.message.reply_text("✅ Ответ отправлен.")
                
                context.user_data.pop('reply_to_user_id', None)
                context.user_data.pop('reply_to_msg_id', None)
                return
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
            return
    
    # Отправка анонимки
    target_code = context.user_data.get('reply_to_code')
    target_user_id = context.user_data.get('reply_to_user_id')
    
    if target_code and target_user_id:
        cursor.execute('''
            INSERT INTO messages (from_user_id, to_user_id, to_link_code, text, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user.id, target_user_id, target_code, message_text, datetime.now().isoformat()))
        conn.commit()
        
        msg_id = cursor.lastrowid
        keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"reply_to_{msg_id}")]]
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🔔 Новое сообщение\n\n{message_text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass
        
        await context.bot.send_message(
            chat_id=YOUR_ID,
            text=f"🔔 Сообщение\nОт: {user.first_name} (@{user.username or 'нет'})\nID: {user.id}\nКому: {target_user_id}\nТекст: {message_text}"
        )
        
        await update.message.reply_text("✅ Отправлено.")
        context.user_data.pop('reply_to_code', None)
        context.user_data.pop('reply_to_user_id', None)
    else:
        await main_menu(update, context)

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("reply_to_"):
        original_msg_id = int(data.split("_")[2])
        context.user_data['reply_to_msg_id'] = original_msg_id
        
        cursor.execute("SELECT from_user_id FROM messages WHERE id = ?", (original_msg_id,))
        msg = cursor.fetchone()
        if msg:
            context.user_data['reply_to_user_id'] = msg[0]
            await query.edit_message_text("✏️ Напиши ответ:")

async def admin_stats(update: Update, context):
    if update.effective_user.id != YOUR_ID:
        return
    
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM messages")
    messages = cursor.fetchone()[0]
    
    await update.message.reply_text(f"📊 Пользователей: {users}\nСообщений: {messages}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("inbox", inbox_command))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
'@ | Out-File -FilePath bot.py -Encoding utf8