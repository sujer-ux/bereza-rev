import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN
from db import find_seller_by_username, get_seller_reviews, add_review, get_seller_avg_rating

# Включаем логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Хранилище временных данных пользователей (в реале лучше использовать БД или кэш)
user_states = {}

# Клавиатура для оценки
def rating_keyboard():
    buttons = [
        [InlineKeyboardButton("⭐ 1", callback_data="rating_1"),
         InlineKeyboardButton("⭐⭐ 2", callback_data="rating_2"),
         InlineKeyboardButton("⭐⭐⭐ 3", callback_data="rating_3"),
         InlineKeyboardButton("⭐⭐⭐⭐ 4", callback_data="rating_4"),
         InlineKeyboardButton("⭐⭐⭐⭐⭐ 5", callback_data="rating_5")]
    ]
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот для отзывов о продавцах.\n\n"
        "🔍 Чтобы посмотреть отзывы о продавце, отправь его @username\n"
        "📝 Чтобы оставить отзыв, сначала найди продавца, потом нажми «Оставить отзыв»"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений (поиск продавца по @username)"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Проверяем, похоже ли на username
    if text.startswith('@') or (not text.startswith('/') and ' ' not in text):
        username = text.lstrip('@')
        seller = find_seller_by_username(username)
        
        if seller:
            avg_rating, reviews_count = get_seller_avg_rating(seller['id'])
            reviews = get_seller_reviews(seller['id'])
            
            # Формируем сообщение о продавце
            rating_display = "⭐" * int(avg_rating) if avg_rating > 0 else "Нет оценок"
            
            msg = (
                f"📦 <b>Продавец: @{seller['username']}</b>\n\n"
                f"📝 <b>Описание:</b>\n{seller['description'] or 'Нет описания'}\n\n"
                f"📊 <b>Рейтинг:</b> {avg_rating} {rating_display}\n"
                f"👥 <b>Всего отзывов:</b> {reviews_count}\n\n"
                f"📋 <b>Последние отзывы:</b>\n"
            )
            
            # Добавляем последние 5 отзывов
            for i, review in enumerate(reviews[:5], 1):
                stars = "⭐" * review['rating']
                msg += f"\n{i}. {stars} - {review['reviewer_name']}\n"
                if review['comment']:
                    msg += f"   💬 {review['comment'][:100]}\n"
                if review.get('image_url'):
                    msg += f"   🖼️ <a href='{review['image_url']}'>📸 Фото</a>\n"
            
            # Кнопки
            keyboard = [
                [InlineKeyboardButton("✍️ Оставить отзыв", callback_data=f"leave_review_{seller['id']}")],
                [InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_{seller['id']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(msg, parse_mode='HTML', reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                f"❌ Продавец {text} не найден.\n\n"
                f"Убедись, что username написан правильно, или попробуй найти другого продавца."
            )
    else:
        await update.message.reply_text(
            "ℹ️ Отправь @username продавца, чтобы посмотреть его профиль и отзывы."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if data.startswith("leave_review_"):
        # Начинаем процесс оставления отзыва
        seller_id = int(data.split("_")[2])
        user_states[user_id] = {"step": "waiting_rating", "seller_id": seller_id}
        
        await query.edit_message_text(
            f"⭐ Оцените продавца от 1 до 5:",
            reply_markup=rating_keyboard()
        )
    
    elif data.startswith("rating_"):
        # Пользователь выбрал оценку
        rating = int(data.split("_")[1])
        
        if user_id in user_states and user_states[user_id].get("step") == "waiting_rating":
            user_states[user_id]["rating"] = rating
            user_states[user_id]["step"] = "waiting_comment"
            
            await query.edit_message_text(
                f"✅ Вы выбрали оценку: {'⭐' * rating}\n\n"
                f"✍️ Теперь напишите текстовый отзыв (можно отправить фото позже).\n"
                f"Просто напишите сообщение с комментарием:"
            )
    
    elif data.startswith("refresh_"):
        # Обновляем информацию о продавце
        seller_id = int(data.split("_")[1])
        seller = find_seller_by_username(...)  # Нужно получить username по id
        
        # Перезагружаем данные и показываем заново
        # (тут код аналогичный показу продавца)
        await query.message.delete()
        # Отправляем свежее сообщение

async def handle_review_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстового комментария для отзыва"""
    user_id = update.effective_user.id
    comment = update.message.text
    user_name = update.effective_user.first_name
    
    if user_id in user_states and user_states[user_id].get("step") == "waiting_comment":
        seller_id = user_states[user_id]["seller_id"]
        rating = user_states[user_id]["rating"]
        
        # Сохраняем отзыв
        add_review(seller_id, rating, comment, user_name)
        
        # Очищаем состояние
        del user_states[user_id]
        
        await update.message.reply_text(
            f"✅ Спасибо за отзыв!\n\n"
            f"Ваша оценка: {'⭐' * rating}\n"
            f"Комментарий: {comment}\n\n"
            f"Вы можете отправить фото к отзыву, если хотите."
        )
    else:
        # Если пользователь не в процессе оставления отзыва
        pass

def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_review_comment))
    
    # Запускаем бота
    print("🤖 Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()