from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

# Suhbat bosqichlari
QUESTION = 1

QUIZ_QUESTIONS = [
    {
        "question": "1. Eski lotin alifbosidagi 'Sh sh' harflar birikmasi yangi alifboda qanday ko'rinishda yoziladi?",
        "options": ["Ş ş", "Ç ç", "Ġ ġ", "Ō ō"],
        "answer": 0,
    },
    {
        "question": "2. Yangi alifboga ko'ra 'Chaqaloq' so'zining to'g'ri imlosini tanlang:",
        "options": ["Chaqaloq", "Çaqaloq", "Şaqaloq", "Ġaqaloq"],
        "answer": 1,
    },
    {
        "question": "3. Eski 'G' g'' harfi yangi alifboda qaysi belgi bilan almashtirildi?",
        "options": ["Ō ō", "Ş ş", "Ġ ġ", "Ç ç"],
        "answer": 2,
    },
    {
        "question": "4. Yangi alifboda 'O'zbek' so'zi qanday yoziladi?",
        "options": ["O'zbek", "Ōzbek", "Ozbek", "Özbek"],
        "answer": 1,
    },
]


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Viktorinani boshlash."""
    query = update.callback_query
    await query.answer()

    context.user_data["quiz_score"] = 0
    context.user_data["quiz_index"] = 0

    return await send_question(query, context)


async def send_question(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navbatdagi savolni yuborish."""
    index = context.user_data["quiz_index"]
    q_data = QUIZ_QUESTIONS[index]

    keyboard = []
    for i, opt in enumerate(q_data["options"]):
        keyboard.append(
            [InlineKeyboardButton(opt, callback_data=f"quiz_ans_{i}")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🏆 **Yangi Alifbo Viktorinasi** ({index + 1}/{len(QUIZ_QUESTIONS)})\n\n"
        f"{q_data['question']}",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return QUESTION


async def handle_answer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Foydalanuvchi javobini tekshirish."""
    query = update.callback_query
    await query.answer()

    selected_option = int(query.data.split("_")[-1])
    index = context.user_data["quiz_index"]
    correct_option = QUIZ_QUESTIONS[index]["answer"]

    if selected_option == correct_option:
        context.user_data["quiz_score"] += 1

    context.user_data["quiz_index"] += 1

    if context.user_data["quiz_index"] < len(QUIZ_QUESTIONS):
        return await send_question(query, context)
    else:
        # Viktorina tugadi
        score = context.user_data["quiz_score"]
        total = len(QUIZ_QUESTIONS)
        percent = int((score / total) * 100)

        if percent == 100:
            msg = "🥇 A'lo! Siz yangi alifboni mukammal bilasiz!"
        elif percent >= 75:
            msg = "🥈 Juda yaxshi! Bilimingiz yuqori darajada."
        else:
            msg = "📘 Qoidalarni yana bir bor takrorlab chiqishni maslahat beramiz."

        result_text = (
            f"🎉 **Viktorina yakunlandi!**\n\n"
            f"📊 Sizning natijangiz: **{score}/{total} ({percent}%)**\n"
            f"{msg}\n\n"
            f"Yangi alifboni o'rganishda davom eting!"
        )

        # Qayta topshirish va Asosiy Menyuga qaytish tugmalari
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Qayta topshirish", callback_data="quiz_start"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔝 Asosiy Menyuga Qaytish", callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            result_text, reply_markup=reply_markup, parse_mode="Markdown"
        )
        return ConversationHandler.END


async def cancel_quiz(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Viktorinani bekor qilish."""
    return ConversationHandler.END


quiz_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_quiz, pattern="^quiz_start$")
    ],
    states={
        QUESTION: [
            CallbackQueryHandler(handle_answer, pattern="^quiz_ans_\\d+$")
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_quiz)],
    per_message=False,
)