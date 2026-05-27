import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN
from db import find_seller_by_username, get_seller_reviews, add_review, get_seller_avg_rating

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

user_states = {}

def rating_keyboard():
    buttons = [
        [InlineKeyboardButton("⭐ 1", callback_data="rating_1"),
         InlineKeyboardButton("⭐⭐ 2", callback_data="rating_2"),
         InlineKeyboardButton("⭐⭐⭐ 3", callback_data="rating_3"),
         InlineKeyboardButton("⭐⭐⭐⭐ 4", callback_data="rating_4"),
         InlineKeyboardButton("⭐⭐⭐⭐⭐ 5", callback_data="rating_5")]
    ]
    return InlineKeyboardMarkup(buttons)

async def show_seller(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str, is_callback: bool = False):
    """Показать информацию о продавце"""
    seller = find_seller_by_username(username)
    
    if not seller:
        msg = f"❌ Продавец {username} не найден."
        if is_callback:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    avg_rating, reviews_count = get_seller_avg_rating(seller['id'])
    reviews = get_seller_reviews(seller['id'])
    
    rating_display = "⭐" * int(avg_rating) if avg_rating > 0 else "Нет оценок"
    
    msg = (
        f"📦 <b>Продавец: @{seller['username']}</b>\n\n"
        f"📝 <b>Описание:</b>\n{seller['description'] or 'Нет описания'}\n\n"
        f"📊 <b>Рейтинг:</b> {avg_rating} {rating_display}\n"
        f"👥 <b>Всего отзывов:</b> {reviews_count}\n\n"
        f"📋 <b>Последние отзывы:</b>\n"
    )
    
    for i, review in enumerate(reviews[:5], 1):
        stars = "⭐" * review['rating']
        msg += f"\n{i}. {stars} - {review['reviewer_name']}\n"
        if review['comment']:
            msg += f"   💬 {review['comment'][:100]}\n"
    
    keyboard = [
        [InlineKeyboardButton("✍️ Оставить отзыв", callback_data=f"leave_review_{seller['id']}_{seller['username']}")],
        [InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_{seller['id']}_{seller['username']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        await update.callback_query.edit_message_text(msg, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode='HTML', reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для отзывов о продавцах.\n\n"
        "🔍 Чтобы посмотреть отзывы о продавце, отправь его @username\n"
        "📝 Чтобы оставить отзыв, сначала найди продавца, потом нажми «Оставить отзыв»"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка поиска продавца"""
    text = update.message.text.strip()
    
    if text.startswith('@') or (not text.startswith('/') and ' ' not in text and text):
        username = text.lstrip('@')
        await show_seller(update, context, username)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if data.startswith("leave_review_"):
        parts = data.split("_")
        seller_id = int(parts[2])
        seller_username = parts[3]
        
        user_states[user_id] = {
            "step": "waiting_rating",
            "seller_id": seller_id,
            "seller_username": seller_username
        }
        
        await query.edit_message_text(
            f"⭐ Оцените продавца @{seller_username} от 1 до 5:",
            reply_markup=rating_keyboard()
        )
    
    elif data.startswith("rating_"):
        rating = int(data.split("_")[1])
        
        if user_id in user_states and user_states[user_id].get("step") == "waiting_rating":
            user_states[user_id]["rating"] = rating
            user_states[user_id]["step"] = "waiting_comment"
            
            await query.edit_message_text(
                f"✅ Вы выбрали оценку: {'⭐' * rating}\n\n"
                f"✍️ Теперь напишите текстовый отзыв:"
            )
    
    elif data.startswith("refresh_"):
        parts = data.split("_")
        seller_username = parts[2]
        await show_seller(update, context, seller_username, is_callback=True)

async def handle_review_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка комментария и фото"""
    user_id = update.effective_user.id
    
    if user_id not in user_states or user_states[user_id].get("step") != "waiting_comment":
        return
    
    comment = update.message.text
    user_name = update.effective_user.first_name
    seller_id = user_states[user_id]["seller_id"]
    rating = user_states[user_id]["rating"]
    
    # Сохраняем отзыв (пока без фото)
    add_review(seller_id, rating, comment, user_name)
    
    # Очищаем состояние
    del user_states[user_id]
    
    await update.message.reply_text(
        f"✅ Спасибо за отзыв!\n\n"
        f"Ваша оценка: {'⭐' * rating}\n"
        f"Комментарий: {comment}\n\n"
        f"Вы можете отправить фото к отзыву, но это пока не реализовано 😊"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_review_comment))
    
    print("🤖 Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()