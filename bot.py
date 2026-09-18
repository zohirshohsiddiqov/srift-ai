import logging
import os
from threading import Thread
from flask import Flask

# Environment o'zgaruvchilari
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# Baza bilan ishlash funksiyalari
from database import (
    add_user,
    block_user,
    get_all_active_user_ids,
    get_stats,
    init_db,
    is_user_blocked,
    unblock_user,
)
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

# Ma'lumotlar bazasini ishga tushirish
init_db()

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Render Web Service uchun Flask HTTP Server (Keep-Alive)
app = Flask("")


@app.route("/")
def home():
    return "Şrift AI Bot Web Service ishlamoqda!"


def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Asosiy menyu keyboardi (Adminlar uchun alohida tugma bilan)."""
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

    if user_id == ADMIN_ID:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⚙️ Admin Panel", callback_data="admin_panel"
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Admin menyu tugmalari."""
    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Bot Statistikasi", callback_data="admin_stats"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Ommaviy Xabar Yuborish", callback_data="admin_broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                "🚫 Bloklash", callback_data="admin_block_prompt"
            ),
            InlineKeyboardButton(
                "✅ Blokdan chiqarish", callback_data="admin_unblock_prompt"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔝 Asosiy Menyuga Qaytish", callback_data="main_menu"
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Har bir amaldan so'ng menyuga qaytish tugmasi."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🔝 Asosiy Menyuga Qaytish", callback_data="main_menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def send_or_edit_menu(query, text: str, reply_markup=None):
    """Xabarni tahrirlaydi yoki yangidan yuboradi."""
    try:
        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.reply_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    # Bazaga foydalanuvchini qo'shish
    add_user(user.id, user.full_name, user.username or "")

    if is_user_blocked(user.id):
        await update.message.reply_text(
            "⛔️ Siz botdan foydalanishdan bloklangansiz."
        )
        return

    welcome_text = (
        f"Assalomu alaykum, **{user.first_name}**!\n\n"
        "🇺🇿 **“Jonajon o‘zbek tilim”** tanlovi doirasida yaratilgan **Yangi Alifbo va Imlo Ekotizimiga** xush kelibsiz!\n\n"
        "Quyidagi imkoniyatlardan birini tanlang:"
    )

    reply_markup = get_main_keyboard(user.id)

    if update.callback_query:
        await send_or_edit_menu(update.callback_query, welcome_text, reply_markup)
    else:
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )


async def button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if is_user_blocked(user.id):
        await query.message.reply_text(
            "⛔️ Siz botdan foydalanishdan bloklangansiz."
        )
        return

    if query.data != "admin_broadcast" and not query.data.startswith("admin_"):
        context.user_data.pop("admin_action", None)

    if query.data == "main_menu":
        welcome_text = (
            "🇺🇿 **Asosiy Menyu**\n\nQuyidagi imkoniyatlardan birini tanlang:"
        )
        await send_or_edit_menu(query, welcome_text, get_main_keyboard(user.id))

    elif query.data == "admin_panel" and user.id == ADMIN_ID:
        admin_text = "⚙️ **Admin Panel**\n\nQuyidagi amallardan birini tanlang:"
        await send_or_edit_menu(query, admin_text, get_admin_keyboard())

    elif query.data == "admin_stats" and user.id == ADMIN_ID:
        total, blocked = get_stats()
        stats_text = (
            "📊 **Bot Statistikasi:**\n\n"
            f"👥 Jami foydalanuvchilar: `{total}` ta\n"
            f"🟢 Faol foydalanuvchilar: `{total - blocked}` ta\n"
            f"🚫 Bloklanganlar: `{blocked}` ta"
        )
        await send_or_edit_menu(query, stats_text, get_admin_keyboard())

    elif query.data == "admin_broadcast" and user.id == ADMIN_ID:
        context.user_data["admin_action"] = "broadcast"
        await send_or_edit_menu(
            query,
            "📢 **Ommaviy xabar yuborish rejimi:**\n\nBarcha foydalanuvchilarga yubormoqchi bo'lgan matningizni yuboring:",
            get_admin_keyboard(),
        )

    elif query.data == "admin_block_prompt" and user.id == ADMIN_ID:
        context.user_data["admin_action"] = "block_user"
        await send_or_edit_menu(
            query,
            "🚫 **Foydalanuvchini bloklash:**\n\nBloklamoqchi bo'lgan foydalanuvchining Telegram ID raqamini yuboring:",
            get_admin_keyboard(),
        )

    elif query.data == "admin_unblock_prompt" and user.id == ADMIN_ID:
        context.user_data["admin_action"] = "unblock_user"
        await send_or_edit_menu(
            query,
            "✅ **Blokdan chiqarish:**\n\nBlokdan chiqarmoqchi bo'lgan foydalanuvchining Telegram ID raqamini yuboring:",
            get_admin_keyboard(),
        )

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
    user = update.effective_user

    if is_user_blocked(user.id):
        await update.message.reply_text(
            "⛔️ Siz botdan foydalanishdan bloklangansiz."
        )
        return

    admin_action = context.user_data.get("admin_action")

    # ADMIN AMALLARI
    if user.id == ADMIN_ID and admin_action:
        text = update.message.text

        if admin_action == "broadcast":
            context.user_data.pop("admin_action", None)
            active_ids = get_all_active_user_ids()
            success, failed = 0, 0

            status_msg = await update.message.reply_text(
                "🚀 Xabar barcha foydalanuvchilarga yuborilmoqda..."
            )

            for uid in active_ids:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"📢 **E'lon:**\n\n{text}",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    success += 1
                except Exception:
                    failed += 1

            await status_msg.edit_text(
                f"✅ **Ommaviy xabar yuborildi!**\n\n"
                f"📥 Muvaffaqiyatli: `{success}` ta\n"
                f"❌ Yuborilmadi: `{failed}` ta",
                reply_markup=get_admin_keyboard(),
            )
            return

        elif admin_action in ["block_user", "unblock_user"]:
            context.user_data.pop("admin_action", None)
            if not text.isdigit():
                await update.message.reply_text(
                    "⚠️ Iltimos, faqat raqamli Telegram ID yuboring.",
                    reply_markup=get_admin_keyboard(),
                )
                return

            target_id = int(text)
            if admin_action == "block_user":
                if block_user(target_id):
                    await update.message.reply_text(
                        f"🚫 ID: `{target_id}` muvaffaqiyatli bloklandi.",
                        reply_markup=get_admin_keyboard(),
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ ID: `{target_id}` bazada topilmadi.",
                        reply_markup=get_admin_keyboard(),
                    )
            else:
                if unblock_user(target_id):
                    await update.message.reply_text(
                        f"✅ ID: `{target_id}` blokdan chiqarildi.",
                        reply_markup=get_admin_keyboard(),
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ ID: `{target_id}` bazada topilmadi.",
                        reply_markup=get_admin_keyboard(),
                    )
            return

    # ODDIY FOYDALANUVCHI AMALLARI
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
    user = update.effective_user

    if is_user_blocked(user.id):
        await update.message.reply_text(
            "⛔️ Siz botdan foydalanishdan bloklangansiz."
        )
        return

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
    # Render porti uchun Flask server
    Thread(target=run_http_server, daemon=True).start()

    if not TELEGRAM_BOT_TOKEN:
        logger.error(
            "TELEGRAM_BOT_TOKEN topilmadi! Environment Variable'ni tekshiring."
        )
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(quiz_conv_handler)
    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern="^(main_menu|admin_panel|admin_stats|admin_broadcast|admin_block_prompt|admin_unblock_prompt|mode_convert|mode_check|mode_docs|generate_poster)$",
        )
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("Bot Admin Panel bilan ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()