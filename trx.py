import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.types import User
import aiosqlite


API_ID = '18377832'  # از my.telegram.org دریافت کنید
API_HASH = 'ed8556c450c6d0fd68912423325dd09c'  # از my.telegram.org دریافت کنید
BOT_TOKEN = "8186718003:AAGoJsGyE7SajlKv2SDbII5_NUuo-ptk40A"
ADMIN_ID = 1848591768


bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)


user_exams_in_progress = {}

EXAMS = {
‎    "شهروند الکترونیک": "shahrvand.json",
‎    "فتوشاپ": "photoshop.json",
‎    "ایلیستریتور": "illustrator.json",
‎    "کرل": "corel.json"
}
DB_NAME = "exam_bot.db"

‎# --- مدیریت پایگاه داده ---
async def setup_database():
‎    """پایگاه داده و جداول را در صورت عدم وجود ایجاد می‌کند."""
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
    print("Database setup complete.")


async def send_exam_menu(chat_id: int):
‎    """منوی انتخاب آزمون را ارسال می‌کند."""
    print(f"Sending exam menu to chat {chat_id}")
    buttons = []
    for title in EXAMS:
        buttons.append([Button.inline(title, f"exam:{title}")])
    
    await bot.send_message(chat_id, "📝 یکی از آزمون‌های زیر را انتخاب کنید:", buttons=buttons)


@bot.on(events.NewMessage(pattern='/start'))
async def handle_start(event):
‎    """کنترل‌کننده دستور /start."""
    print(f"Start command from user: {event.sender_id}")
    
    user_id = event.sender_id
    
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                user = await cur.fetchone()
                print(f"User found in DB: {user}")
                if user:
                    await send_exam_menu(event.chat_id)
                else:
                    await event.reply("سلام! به ربات آزمون خوش آمدید.\nلطفاً نام و نام خانوادگی خود را برای ثبت‌نام وارد کنید:")
    except Exception as e:
        print(f"Error in start command: {e}")
        await event.reply("خطا در سیستم. لطفاً دوباره تلاش کنید.")

@bot.on(events.NewMessage(pattern='/panel'))
async def handle_panel(event):
‎    """کنترل‌کننده دستور /panel."""
    print(f"Panel command from user: {event.sender_id}")
    
    if event.sender_id == ADMIN_ID:
        await admin_panel(event)
    else:
        await event.reply("⛔️ شما مجوز دسترسی به این بخش را ندارید.")

@bot.on(events.NewMessage)
async def handle_messages(event):
‎    """کنترل‌کننده عمومی برای تمام پیام‌های دریافتی."""

    if event.text and (event.text.startswith('/start') or event.text.startswith('/panel')):
        return
    
    if not event.text:
        return
    
    print(f"Message received: {event.text}")
    print(f"From user: {event.sender_id}")
    print(f"Chat ID: {event.chat_id}")
    
    user_id = event.sender_id
    

    print("Processing regular message")
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                user_exists = await cur.fetchone()
            
            if not user_exists:
‎                # ثبت نام کاربر جدید
                await db.execute("INSERT INTO users (user_id, full_name) VALUES (?, ?)", (user_id, event.text))
                await db.commit()
                await event.reply(f"✅ ثبت نام شما با نام \"{event.text}\" با موفقیت انجام شد.")
                await send_exam_menu(event.chat_id)
            elif user_id not in user_exams_in_progress:
                await event.reply("برای شروع، یکی از آزمون‌ها را از منو انتخاب کنید. /start")
    except Exception as e:
        print(f"Error in message handling: {e}")
        await event.reply("خطا در سیستم. لطفاً دوباره تلاش کنید.")


@bot.on(events.CallbackQuery)
async def handle_callback_queries(event):
‎    """کنترل‌کننده عمومی برای تمام callback queryها."""
    print(f"Callback query received: {event.data.decode()}")
    
    data = event.data.decode()
    
    if data.startswith("exam:"):
        await handle_exam_selection(event)
    elif data.startswith("answer:"):
        await handle_answer_submission(event)

async def handle_exam_selection(event):
‎    """پاسخ به کلیک روی دکمه انتخاب آزمون."""
    exam_title = event.data.decode().split(":")[1]
    user_id = event.sender_id
    print(f"Exam selected: {exam_title} by user {user_id}")

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

    user_exams_in_progress[user_id] = {
        "exam": exam_title,
        "questions": questions,
        "current": 0,
        "answers": [],
        "chat_id": event.chat_id
    }

    await event.answer(f"آزمون {exam_title} شروع می‌شود...")
    await event.delete()
    await send_question(user_id)
    asyncio.create_task(exam_timer(user_id))

async def handle_answer_submission(event):
‎    """پاسخ به کلیک روی گزینه‌های سوال."""
    user_id = event.sender_id
    data = user_exams_in_progress.get(user_id)
    if not data:
        await event.answer("خطا: آزمون شما یافت نشد. لطفاً دوباره شروع کنید.", alert=True)
        return

    selected_option_index = int(event.data.decode().split(":")[1])
    current_q_index = data["current"]
    
    if current_q_index >= len(data["questions"]):
        return

    correct_answer_index = data["questions"][current_q_index]["answer"]
    data["answers"].append((current_q_index, selected_option_index, correct_answer_index))
    data["current"] += 1
    
    await event.delete()
    await send_question(user_id)




async def send_question(user_id: int):
‎    """سوال فعلی را برای کاربر ارسال می‌کند."""
    data = user_exams_in_progress.get(user_id)
    if not data:
        return

    if data["current"] >= len(data["questions"]):
        await finish_exam(user_id)
        return

    q = data["questions"][data["current"]]
    text = f"❓ سوال {data['current'] + 1} از {len(data['questions'])}:\n\n{q['question']}"
    
    buttons = []
    for i, opt in enumerate(q['options']):
        buttons.append([Button.inline(opt, f"answer:{i}")])
    
    await bot.send_message(data["chat_id"], text, buttons=buttons)

async def finish_exam(user_id: int):
‎    """آزمون را به پایان رسانده و نتایج را ذخیره می‌کند."""
    if user_id not in user_exams_in_progress:
        return
        
    data = user_exams_in_progress[user_id]
    chat_id = data["chat_id"]
    score = sum(1 for _, user_ans, correct_ans in data["answers"] if user_ans == correct_ans)
    percent = int((score / len(data["questions"])) * 100) if data["questions"] else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO results (user_id, exam, score, date) VALUES (?, ?, ?, ?)",
                         (user_id, data["exam"], percent, now))
        for q_no, u_ans, c_ans in data["answers"]:
            await db.execute("INSERT INTO answers (user_id, exam, q_no, user_answer, correct_answer) VALUES (?, ?, ?, ?, ?)",
                             (user_id, data["exam"], q_no, u_ans, c_ans))
        await db.commit()

    await bot.send_message(chat_id, f"✅ آزمون به پایان رسید!\n\nآزمون: {data['exam']}\n🎯 نمره نهایی: {percent} از ۱۰۰")
    del user_exams_in_progress[user_id]

async def exam_timer(user_id: int):
‎    """تایمر ۴۰ دقیقه‌ای برای آزمون."""
    await asyncio.sleep(40 * 60)
    if user_id in user_exams_in_progress:
        chat_id = user_exams_in_progress[user_id]["chat_id"]
        await bot.send_message(chat_id, "⏰ زمان آزمون شما به پایان رسید!")
        await finish_exam(user_id)


async def admin_panel(event):
‎    """نمایش نتایج آزمون‌ها برای ادمین."""
    text = "📋 لیست نتایج شرکت‌کنندگان:\n\n"
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT u.full_name, r.exam, r.score, r.date 
            FROM results r JOIN users u ON r.user_id = u.user_id
            ORDER BY r.date DESC
        """) as cursor:
            rows = await cursor.fetchall()
            if not rows:
                return await event.reply("هنوز هیچ نتیجه‌ای در سیستم ثبت نشده است.")
            
            for full_name, exam, score, date in rows:
                text += f"👤 نام: {full_name}\n📘 آزمون: {exam}\n🎯 نمره: {score}\n🕰 تاریخ: {date}\n---\n"
    

    for i in range(0, len(text), 4000):
        await event.reply(text[i:i + 4000])


async def main():
‎    """تابع اصلی اجرای ربات."""
    try:

        await setup_database()
        

        print("Bot is starting...")
        await bot.run_until_disconnected()
        
    except Exception as e:
        print(f"خطا در اجرای ربات: {e}")

if __name__ == "__main__":
    asyncio.run(main())
