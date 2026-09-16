import logging
import os
from config import TELEGRAM_BOT_TOKEN
from quiz import quiz_conv_handler
from services import (
    check_spelling_and_style,
    convert_to_new_alphabet,
    generate_infographic_pdf,
    process_docx_file,
    process_pdf_file,
    process_txt_file,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Asosiy menyu tugmalari keyboardi."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🔤 Yangi alifboga o'girish", callback_data="mode_convert"
            )
        ],
        [
            InlineKeyboardButton(
                "📝 Imlo & Soflik indeksi", callback_data="mode_check"
            )
        ],
        [
            InlineKeyboardButton(
                "🏆 Yangi Alifbo Viktorinasi (Quiz)", callback_data="quiz_start"
            )
        ],
        [
            InlineKeyboardButton(
                "📄 Hujjatlarni tahrirlash (.docx, .pdf, .txt)",
                callback_data="mode_docs",
            )
        ],
        [
            InlineKeyboardButton(
                "🏢 PDF Plakat Yaratish (OTM/Tashkilotlar)",
                callback_data="generate_poster",
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Har bir amaldan so'ng menyuga qaytish tugmasi."""
    keyboard = [
        [InlineKeyboardButton("🔝 Asosiy Menyuga Qaytish", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def send_or_edit_menu(query, text: str, reply_markup=None):
    """Xabarni tahrirlaydi, agar u fayl xabari bo'lsa yangitdan yuboradi."""
    try:
        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        # Faylli xabarlarda edit_message_text ishlamasa, eski xabarni o'chirib yangisini yuboramiz
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.reply_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome_text = (
        f"Assalomu alaykum, **{user.first_name}**!\n\n"
        "🇺🇿 **“Jonajon o‘zbek tilim”** tanlovi doirasida yaratilgan **Yangi Alifbo va Imlo Ekotizimiga** xush kelibsiz!\n\n"
        "Quyidagi imkoniyatlardan birini tanlang:"
    )

    reply_markup = get_main_keyboard()

    if update.callback_query:
        await send_or_edit_menu(update.callback_query, welcome_text, reply_markup)
    else:
        await update.message.reply_text(
            welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )


async def button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "main_menu":
        welcome_text = (
            "🇺🇿 **Asosiy Menyu**\n\nQuyidagi imkoniyatlardan birini tanlang:"
        )
        await send_or_edit_menu(query, welcome_text, get_main_keyboard())

    elif query.data == "mode_convert":
        context.user_data["mode"] = "convert"
        await send_or_edit_menu(
            query,
            "🔤 **Yangi alifboga o'girish rejimi yoqildi.**\n\nMenga ixtiyoriy matn yuboring, men uni yangi lotin alifbosiga o'girib beraman.",
            get_back_keyboard(),
        )

    elif query.data == "mode_check":
        context.user_data["mode"] = "check"
        await send_or_edit_menu(
            query,
            "📝 **Imlo va Soflik indeksi rejimi yoqildi.**\n\nMenga matn yuboring, men undagi xatolar va soflik ballini chiqarib beraman.",
            get_back_keyboard(),
        )

    elif query.data == "mode_docs":
        await send_or_edit_menu(
            query,
            "📄 **Hujjatlarni tahrirlash rejimi:**\n\nMenga `.docx`, `.pdf` yoki `.txt` formatidagi fayl yuboring. Men uning matnlarini yangi alifboga o'tkazib beraman.",
            get_back_keyboard(),
        )

    elif query.data == "generate_poster":
        status_msg = await query.message.reply_text(
            "🎨 PDF Plakat shakllantirilmoqda, kuting..."
        )
        pdf_path = "alifbo_qoidalari_plakat.pdf"
        generate_infographic_pdf(pdf_path)

        await status_msg.delete()
        with open(pdf_path, "rb") as doc_file:
            await query.message.reply_document(
                document=doc_file,
                caption="✅ **Tashkilot va OTMlar uchun Yangi Alifbo PDF Plakati tayyor!**",
                reply_markup=get_back_keyboard(),
                read_timeout=60,
                write_timeout=60,
            )
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    mode = context.user_data.get("mode", "convert")
    user_text = update.message.text

    status_msg = await update.message.reply_text("🔄 Tahlil qilinmoqda, kuting...")

    try:
        if mode == "check":
            result = check_spelling_and_style(user_text)
        else:
            result = convert_to_new_alphabet(user_text)

        await status_msg.delete()

        try:
            await update.message.reply_text(
                result,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_back_keyboard(),
            )
        except Exception:
            await update.message.reply_text(
                result, reply_markup=get_back_keyboard()
            )

    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await update.message.reply_text(
            "⚠️ Matnni tahlil qilishda xatolik yuz berdi.",
            reply_markup=get_back_keyboard(),
        )


async def handle_document(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    document = update.message.document
    file_name = document.file_name.lower()

    if not (
        file_name.endswith(".docx")
        or file_name.endswith(".pdf")
        or file_name.endswith(".txt")
    ):
        await update.message.reply_text(
            "⚠️ Iltimos, faqat `.docx`, `.pdf` yoki `.txt` formatidagi fayllarni yuboring.",
            reply_markup=get_back_keyboard(),
        )
        return

    status_msg = await update.message.reply_text(
        "📥 Fayl yuklab olinmoqda va yangi alifboga o'tkazilmoqda..."
    )

    input_path = f"input_{document.file_name}"
    output_path = f"new_alphabet_{document.file_name}"

    try:
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(input_path)

        if file_name.endswith(".docx"):
            process_docx_file(input_path, output_path)
        elif file_name.endswith(".txt"):
            process_txt_file(input_path, output_path)
        elif file_name.endswith(".pdf"):
            process_pdf_file(input_path, output_path)

        await status_msg.edit_text("📤 Tayyor hujjat yuklanmoqda...")

        with open(output_path, "rb") as doc_file:
            await update.message.reply_document(
                document=doc_file,
                caption="✅ Hujjat matnlari Yangi O'zbek Alifbosiga muvaffaqiyatli o'tkazildi!",
                reply_markup=get_back_keyboard(),
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Hujjat xatolik: {e}")
        try:
            await status_msg.edit_text(
                "⚠️ Hujjatni qayta ishlashda xatolik yuz berdi. Qayta urinib ko'ring.",
                reply_markup=get_back_keyboard(),
            )
        except Exception:
            await update.message.reply_text(
                "⚠️ Hujjatni qayta ishlashda xatolik yuz berdi.",
                reply_markup=get_back_keyboard(),
            )

    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(quiz_conv_handler)
    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern="^(main_menu|mode_convert|mode_check|mode_docs|generate_poster)$",
        )
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("Bot ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()