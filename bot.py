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
    get_required_channel,
    get_stats,
    init_db,
    is_user_blocked,
    set_required_channel,
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

# Render Web Service uchun Flask HTTP Server
app = Flask("")


@app.route("/")
def home():
    return "Şrift AI Bot Web Service ishlamoqda!"


def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


async def check_subscription(
    user_id: int, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Foydalanuvchi majburiy kanalga a'zo ekanligini tekshiradi."""
    required_channel = get_required_channel()
    if not required_channel or user_id == ADMIN_ID:
        return True
    try:
        member = await context.bot.get_chat_member(
            chat_id=required_channel, user_id=user_id
        )
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logger.error(f"Kanal obunasini tekshirishda xatolik: {e}")
        return True


def get_sub_keyboard() -> InlineKeyboardMarkup:
    """Kanalga obuna bo'lish tugmasi keyboardi."""
    required_channel = get_required_channel()
    channel_link = f"https://t.me/{required_channel.replace('@', '')}"
    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Kanalimizga obuna bo'lish", url=channel_link
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Obunani tekshirish", callback_data="check_sub"
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Asosiy menyu keyboardi."""
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
    current_channel = get_required_channel() or "Sozlanmagan (O'chirilgan)"
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
                "📢 Majburiy Kanalni Sozlash",
                callback_data="admin_set_channel_prompt",
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
    """Menyuga qaytish tugmasi."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🔝 Asosiy Menyuga Qaytish", callback_data="main_menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def send_or_edit_menu(query, text: str, reply_markup=None):
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

    add_user(user.id, user.full_name, user.username or "")

    if is_user_blocked(user.id):
        await update.message.reply_text(
            "⛔️ Siz botdan foydalanishdan bloklangansiz."
        )
        return

    # Majburiy obunani tekshirish
    is_subbed = await check_subscription(user.id, context)
    if not is_subbed:
        req_chan = get_required_channel()
        sub_text = (
            f"⚠️ **Botdan foydalanish uchun rasmiy kanalimizga obuna bo'ling!**\n\n"
            f"Kanalimiz: {req_chan}\n\n"
            "Obuna bo'lgach, **'✅ Obunani tekshirish'** tugmasini bosing."
        )
        if update.callback_query:
            await send_or_edit_menu(
                update.callback_query, sub_text, get_sub_keyboard()
            )
        else:
            await update.message.reply_text(
                sub_text,
                reply_markup=get_sub_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
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

    if query.data == "check_sub":
        if await check_subscription(user.id, context):
            await query.answer(
                "✅ Rahmat! Obuna tasdiqlandi.", show_alert=True
            )
            welcome_text = (
                f"Assalomu alaykum, **{user.first_name}**!\n\n"
                "🇺🇿 **“Jonajon o‘zbek tilim”** tanlovi doirasida yaratilgan **Yangi Alifbo va Imlo Ekotizimiga** xush kelibsiz!\n\n"
                "Quyidagi imkoniyatlardan birini tanlang:"
            )
            await send_or_edit_menu(
                query, welcome_text, get_main_keyboard(user.id)
            )
        else:
            await query.answer(
                "❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True
            )
        return

    if not await check_subscription(user.id, context):
        req_chan = get_required_channel()
        sub_text = (
            f"⚠️ **Botdan foydalanish uchun rasmiy kanalimizga obuna bo'ling!**\n\n"
            f"Kanalimiz: {req_chan}\n\n"
            "Obuna bo'lgach, **'✅ Obunani tekshirish'** tugmasini bosing."
        )
        await send_or_edit_menu(query, sub_text, get_sub_keyboard())
        return

    if query.data != "admin_broadcast" and not query.data.startswith("admin_"):
        context.user_data.pop("admin_action", None)

    if query.data == "main_menu":
        welcome_text = (
            "🇺🇿 **Asosiy Menyu**\n\nQuyidagi imkoniyatlardan birini tanlang:"
        )
        await send_or_edit_menu(query, welcome_text, get_main_keyboard(user.id))

    elif query.data == "admin_panel" and user.id == ADMIN_ID:
        current_chan = get_required_channel() or "O'chirilgan"
        admin_text = (
            f"⚙️ **Admin Panel**\n\n"
            f"📢 Joriy majburiy kanal: `{current_chan}`\n\n"
            "Quyidagi amallardan birini tanlang:"
        )
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

    elif query.data == "admin_set_channel_prompt" and user.id == ADMIN_ID:
        context.user_data["admin_action"] = "set_channel"
        current_chan = get_required_channel() or "O'chirilgan"
        await send_or_edit_menu(
            query,
            f"📢 **Majburiy kanalni sozlash:**\n\n"
            f"Hozirgi kanal: `{current_chan}`\n\n"
            "Yangi kanal username'ini kiriting (masalan: `@srift_uz`):\n"
            "*(Majburiy obunani o'chirish uchun `off` deb yuboring)*",
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
        text = update.message.text.strip()

        if admin_action == "set_channel":
            context.user_data.pop("admin_action", None)
            if text.lower() == "off":
                set_required_channel("")
                await update.message.reply_text(
                    "✅ Majburiy obuna muvaffaqiyatli o'chirildi!",
                    reply_markup=get_admin_keyboard(),
                )
            else:
                if not text.startswith("@"):
                    text = "@" + text
                set_required_channel(text)
                await update.message.reply_text(
                    f"✅ Majburiy kanal `{text}` ga o'zgartirildi!\n\n"
                    "⚠️ *Eslatma:* Botingiz shu kanalda ADMIN bo'lishi kerak.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_admin_keyboard(),
                )
            return

        elif admin_action == "broadcast":
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

    # Obunani tekshirish (Oddiy foydalanuvchilar uchun)
    if not await check_subscription(user.id, context):
        req_chan = get_required_channel()
        sub_text = (
            f"⚠️ **Botdan foydalanish uchun rasmiy kanalimizga obuna bo'ling!**\n\n"
            f"Kanalimiz: {req_chan}\n\n"
            "Obuna bo'lgach, **'✅ Obunani tekshirish'** tugmasini bosing."
        )
        await update.message.reply_text(
            sub_text,
            reply_markup=get_sub_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

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

    if not await check_subscription(user.id, context):
        req_chan = get_required_channel()
        sub_text = (
            f"⚠️ **Botdan foydalanish uchun rasmiy kanalimizga obuna bo'ling!**\n\n"
            f"Kanalimiz: {req_chan}\n\n"
            "Obuna bo'lgach, **'✅ Obunani tekshirish'** tugmasini bosing."
        )
        await update.message.reply_text(
            sub_text,
            reply_markup=get_sub_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
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
            pattern="^(main_menu|check_sub|admin_panel|admin_stats|admin_broadcast|admin_set_channel_prompt|admin_block_prompt|admin_unblock_prompt|mode_convert|mode_check|mode_docs|generate_poster)$",
        )
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("Bot Majburiy Obuna Dynamic Sozlamasi bilan ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()
