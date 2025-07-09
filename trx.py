import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, events, Button
import aiosqlite
import logging

# برای لاگ‌گیری بهتر خطاها
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- اطلاعات ربات و ادمین ---
# توصیه می‌شود این اطلاعات را از متغیرهای محیطی (Environment Variables) بخوانید
API_ID = '18377832'
API_HASH = 'ed8556c450c6d0fd68912423325dd09c'
BOT_TOKEN = "8186718003:AAGoJsGyE7SajlKv2SDbII5_NUuo-ptk40A"
ADMIN_ID = 1848591768
DB_NAME = "exam_bot.db"

# --- دیکشنری آزمون‌ها ---
EXAMS = {
    "شهروند الکترونیک": "shahrvand.json",
    "فتوشاپ": "photoshop.json",
    "ایلیستریتور": "illustrator.json",
    "کرل": "corel.json"
}

# --- مدیریت وضعیت آزمون‌های در حال اجرا ---
# FIX: این دیکشنری وضعیت آزمون کاربر را در حافظه نگه می‌دارد.
# اگر ربات ری‌استارت شود، اطلاعات از بین می‌رود. برای پروژه‌های بزرگ‌تر،
# این وضعیت را نیز در پایگاه داده ذخیره کنید.
user_exams_in_progress = {}

# --- ساخت کلاینت تلگرام ---
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- مدیریت پایگاه داده ---
async def setup_database():
    """پایگاه داده و جداول را در صورت عدم وجود ایجاد می‌کند."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            exam TEXT NOT NULL,
            score INTEGER NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS answers (
            answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            exam TEXT NOT NULL,
            q_no INTEGER NOT NULL,
            user_answer INTEGER NOT NULL,
            correct_answer INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )""")
        await db.commit()
    logging.info("Database setup complete.")

async def send_exam_menu(chat_id: int, text: str = "📝 یکی از آزمون‌های زیر را انتخاب کنید:"):
    """منوی انتخاب آزمون را ارسال می‌کند."""
    buttons = [Button.inline(title, f"exam:{title}") for title in EXAMS]
    await bot.send_message(chat_id, text, buttons=[buttons])

# --- کنترل‌کننده‌های رویدادها ---

@bot.on(events.NewMessage(pattern='/start'))
async def handle_start(event):
    """کنترل‌کننده دستور /start. کاربر را ثبت‌نام کرده یا منو را نمایش می‌دهد."""
    user_id = event.sender_id
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                user = await cur.fetchone()
                if user:
                    await send_exam_menu(event.chat_id, f"سلام {user[1]} عزیز، خوش آمدید!")
                else:
                    await event.reply("👋 سلام! به ربات آزمون خوش آمدید.\nلطفاً نام و نام خانوادگی خود را برای ثبت‌نام وارد کنید:")
    except Exception as e:
        logging.error(f"Error in /start for user {user_id}: {e}")
        await event.reply("خطایی در سیستم رخ داده است. لطفاً بعدا تلاش کنید.")

@bot.on(events.NewMessage(pattern='/panel'))
async def handle_panel(event):
    """کنترل‌کننده دستور /panel برای نمایش نتایج به ادمین."""
    if event.sender_id == ADMIN_ID:
        await admin_panel(event)
    else:
        await event.reply("⛔️ شما مجوز دسترسی به این بخش را ندارید.")

@bot.on(events.NewMessage)
async def handle_messages(event):
    """کنترل‌کننده عمومی برای تمام پیام‌های متنی."""
    if event.text.startswith('/'):
        return  # دستورات توسط کنترل‌کننده‌های دیگر مدیریت می‌شوند

    user_id = event.sender_id

    # FIX: اگر کاربر در حال آزمون دادن باشد، به پیام‌های متنی او پاسخ نامرتبط نمی‌دهیم.
    if user_id in user_exams_in_progress:
        await event.reply("⏳ لطفاً آزمون خود را تمام کرده یا با استفاده از دکمه‌ها به سوالات پاسخ دهید.")
        return

    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                user_exists = await cur.fetchone()
            
            if not user_exists:
                # ثبت نام کاربر جدید
                full_name = event.text.strip()
                if not full_name:
                    await event.reply("نام معتبری وارد نشده است. لطفاً دوباره تلاش کنید.")
                    return
                
                await db.execute("INSERT INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
                await db.commit()
                await event.reply(f"✅ ثبت نام شما با نام \"{full_name}\" با موفقیت انجام شد.")
                await send_exam_menu(event.chat_id)
            else:
                # اگر کاربر ثبت‌نام کرده ولی دستوری وارد نکرده
                await send_exam_menu(event.chat_id, "برای شروع یک آزمون جدید، از منوی زیر انتخاب کنید:")

    except Exception as e:
        logging.error(f"Error in message handler for user {user_id}: {e}")
        await event.reply("خطا در سیستم. لطفاً دوباره تلاش کنید.")

@bot.on(events.CallbackQuery)
async def handle_callback_queries(event):
    """کنترل‌کننده عمومی برای تمام دکمه‌های شیشه‌ای (callback query)."""
    data = event.data.decode()
    
    if data.startswith("exam:"):
        await handle_exam_selection(event)
    elif data.startswith("answer:"):
        await handle_answer_submission(event)

# --- منطق اصلی آزمون ---

async def handle_exam_selection(event):
    """پاسخ به کلیک روی دکمه انتخاب آزمون و شروع آن."""
    exam_title = event.data.decode().split(":")[1]
    user_id = event.sender_id

    # FIX: بررسی اینکه آیا کاربر هم‌اکنون آزمون دیگری در حال اجرا دارد یا خیر
    if user_id in user_exams_in_progress:
        await event.answer("⛔️ شما یک آزمون دیگر در حال اجرا دارید. لطفاً ابتدا آن را تمام کنید.", alert=True)
        return

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM results WHERE user_id = ? AND exam = ?", (user_id, exam_title)) as cur:
            if await cur.fetchone():
                await event.answer("⛔️ شما قبلاً در این آزمون شرکت کرده‌اید.", alert=True)
                return

    try:
        with open(EXAMS[exam_title], "r", encoding="utf-8") as f:
            questions = json.load(f)
    except FileNotFoundError:
        await event.answer(f"خطا: فایل سوالات آزمون '{exam_title}' یافت نشد!", alert=True)
        return
    except json.JSONDecodeError:
        await event.answer(f"خطا: فایل سوالات آزمون '{exam_title}' معتبر نیست!", alert=True)
        return
    
    # NEW: ایجاد تایمر و ذخیره تسک آن برای قابلیت لغو کردن
    timer_task = asyncio.create_task(exam_timer(user_id, 40 * 60)) # 40 دقیقه

    user_exams_in_progress[user_id] = {
        "exam": exam_title,
        "questions": questions,
        "current": 0,
        "answers": [],
        "chat_id": event.chat_id,
        "timer_task": timer_task # NEW: ذخیره تسک تایمر
    }

    await event.answer(f"آزمون {exam_title} شروع می‌شود...")
    await event.delete()
    await send_question(user_id)

async def handle_answer_submission(event):
    """پردازش پاسخ کاربر به یک سوال."""
    user_id = event.sender_id
    exam_data = user_exams_in_progress.get(user_id)
    if not exam_data:
        await event.answer("خطا: آزمون شما یافت نشد. لطفاً دوباره شروع کنید.", alert=True)
        return

    selected_option_index = int(event.data.decode().split(":")[1])
    current_q_index = exam_data["current"]
    
    if current_q_index >= len(exam_data["questions"]):
        return # آزمون قبلا تمام شده

    correct_answer_index = exam_data["questions"][current_q_index]["answer"]
    exam_data["answers"].append((current_q_index, selected_option_index, correct_answer_index))
    exam_data["current"] += 1
    
    await event.delete()
    await send_question(user_id)

async def send_question(user_id: int):
    """سوال فعلی را برای کاربر ارسال می‌کند."""
    exam_data = user_exams_in_progress.get(user_id)
    if not exam_data:
        return

    if exam_data["current"] >= len(exam_data["questions"]):
        await finish_exam(user_id)
        return

    q = exam_data["questions"][exam_data["current"]]
    text = f"❓ سوال {exam_data['current'] + 1} از {len(exam_data['questions'])}:\n\n**{q['question']}**"
    
    buttons = [Button.inline(opt, f"answer:{i}") for i, opt in enumerate(q['options'])]
    
    await bot.send_message(exam_data["chat_id"], text, buttons=[buttons])

async def finish_exam(user_id: int):
    """آزمون را به پایان رسانده، نتایج را ذخیره و وضعیت کاربر را پاک می‌کند."""
    if user_id not in user_exams_in_progress:
        return # اگر آزمون قبلا تمام شده باشد، کاری انجام نده
        
    exam_data = user_exams_in_progress[user_id]
    
    # NEW: لغو کردن تسک تایمر تا پس از پایان آزمون اجرا نشود
    exam_data["timer_task"].cancel()

    chat_id = exam_data["chat_id"]
    score = sum(1 for _, user_ans, correct_ans in exam_data["answers"] if user_ans == correct_ans)
    total_questions = len(exam_data["questions"])
    percent = int((score / total_questions) * 100) if total_questions > 0 else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO results (user_id, exam, score, date) VALUES (?, ?, ?, ?)",
                         (user_id, exam_data["exam"], percent, now))
        for q_no, u_ans, c_ans in exam_data["answers"]:
            await db.execute("INSERT INTO answers (user_id, exam, q_no, user_answer, correct_answer) VALUES (?, ?, ?, ?, ?)",
                             (user_id, exam_data["exam"], q_no, u_ans, c_ans))
        await db.commit()

    # FIX: پاک کردن وضعیت کاربر از حافظه پس از اتمام تمام کارها
    del user_exams_in_progress[user_id]
    
    await bot.send_message(chat_id, f"✅ آزمون به پایان رسید!\n\n**آزمون:** {exam_data['exam']}\n**🎯 نمره نهایی:** {percent} از ۱۰۰")
    await send_exam_menu(chat_id, "می‌توانید در آزمون دیگری شرکت کنید:")

async def exam_timer(user_id: int, duration: int):
    """تایمر آزمون. اگر زمان تمام شود، آزمون را به صورت خودکار به پایان می‌رساند."""
    try:
        await asyncio.sleep(duration)
        if user_id in user_exams_in_progress:
            chat_id = user_exams_in_progress[user_id]["chat_id"]
            logging.info(f"Exam timer finished for user {user_id}.")
            await bot.send_message(chat_id, "⏰ زمان آزمون شما به پایان رسید!")
            await finish_exam(user_id)
    except asyncio.CancelledError:
        # NEW: وقتی تایمر لغو می‌شود، این استثنا رخ می‌دهد که طبیعی است
        logging.info(f"Exam timer cancelled for user {user_id}.")

async def admin_panel(event):
    """نتایج تمام آزمون‌ها را برای ادمین ارسال می‌کند."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("""
                SELECT u.full_name, r.exam, r.score, r.date 
                FROM results r JOIN users u ON r.user_id = u.user_id
                ORDER BY r.date DESC
            """) as cursor:
                rows = await cursor.fetchall()

                if not rows:
                    await event.reply("هنوز هیچ نتیجه‌ای در سیستم ثبت نشده است.")
                    return
                
                text = "📋 **لیست نتایج شرکت‌کنندگان:**\n\n"
                for full_name, exam, score, date in rows:
                    text += f"👤 **نام:** {full_name}\n📘 **آزمون:** {exam}\n🎯 **نمره:** {score}\n🕰 **تاریخ:** {date}\n---\n"
        
                # ارسال نتایج در چند پیام در صورت طولانی بودن
                for i in range(0, len(text), 4000):
                    await event.reply(text[i:i+4000])

    except Exception as e:
        logging.error(f"Error in /panel: {e}")
        await event.reply("خطا در دریافت اطلاعات از پایگاه داده.")

async def main():
    """تابع اصلی برای راه‌اندازی ربات."""
    await setup_database()
    logging.info("Bot is starting...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Failed to run bot: {e}")
