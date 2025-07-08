import asyncio
import json
from datetime import datetime

from balethon import Client, types, InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite

API_KEY = "717675061:1p9xzK4wzYVqml3dVInIV4I3HgnW15ewFAWi8aIZ"
ADMIN_ID = 2143480267  # عدد آی‌دی شما

bot = Client(API_KEY)

# حافظه موقتی برای آزمون در حال اجرا
user_answers = {}

EXAMS = {
    "شهروند الکترونیک": "shahrvand.json",
    "فتوشاپ": "photoshop.json",
    "ایلیستریتور": "illustrator.json",
    "کرل": "corel.json"
}

# شروع ربات
@bot.on_message(commands=["start"])
async def start(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("exam_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            user = await cur.fetchone()
            if not user:
                await message.reply("سلام! لطفاً نام و نام خانوادگی خود را وارد کنید:")
                return
    await send_exam_menu(message.chat.id)

# دریافت نام
@bot.on_message()
async def get_name(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("exam_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            exists = await cur.fetchone()
        if exists:
            return
        await db.execute("INSERT INTO users (user_id, full_name) VALUES (?, ?)", (user_id, message.text))
        await db.commit()
    await message.reply("✅ ثبت شد.")
    await send_exam_menu(message.chat.id)

# منوی انتخاب آزمون
async def send_exam_menu(chat_id):
    buttons = [[InlineKeyboardButton(text=title, callback_data=f"exam:{title}")] for title in EXAMS]
    markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(chat_id, "📝 یکی از آزمون‌های زیر را انتخاب کنید:", reply_markup=markup)

# کلیک روی آزمون
@bot.on_callback_query()
async def handle_exam_callback(query: types.CallbackQuery):
    if not query.data.startswith("exam:"):
        return

    exam_title = query.data.split(":")[1]
    user_id = query.from_user.id

    # بررسی اینکه قبلاً آزمون داده یا نه
    async with aiosqlite.connect("exam_bot.db") as db:
        async with db.execute("SELECT * FROM results WHERE user_id = ? AND exam = ?", (user_id, exam_title)) as cur:
            done = await cur.fetchone()
            if done:
                return await query.message.reply("⛔️ شما قبلاً این آزمون را داده‌اید.")

    with open(EXAMS[exam_title], "r", encoding="utf-8") as f:
        questions = json.load(f)

    user_answers[user_id] = {
        "exam": exam_title,
        "questions": questions,
        "current": 0,
        "answers": []
    }

    await bot.answer_callback_query(query.id)
    await send_question(user_id, query.message.chat.id)

    # شروع تایمر آزمون
    asyncio.create_task(exam_timer(user_id, query.message.chat.id))

# ارسال سوال
async def send_question(user_id, chat_id):
    data = user_answers.get(user_id)
    if not data:
        return

    if data["current"] >= len(data["questions"]):
        return await finish_exam(user_id, chat_id)

    q = data["questions"][data["current"]]
    text = f"❓ سوال {data['current'] + 1}:\n{q['question']}"
    options = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(q['options'])]
    markup = InlineKeyboardMarkup(options)
    await bot.send_message(chat_id, text, reply_markup=markup)

# دریافت پاسخ سوال
@bot.on_callback_query()
async def handle_answer_callback(query: types.CallbackQuery):
    if not query.data.startswith("answer:"):
        return

    user_id = query.from_user.id
    selected = int(query.data.split(":")[1])
    data = user_answers.get(user_id)

    if not data:
        return

    current_q = data["questions"][data["current"]]
    correct = current_q["answer"]
    data["answers"].append((data["current"], selected, correct))

    data["current"] += 1
    await bot.answer_callback_query(query.id)
    await send_question(user_id, query.message.chat.id)

# پایان آزمون
async def finish_exam(user_id, chat_id):
    data = user_answers[user_id]
    score = sum(1 for _, u, c in data["answers"] if u == c)
    percent = int((score / len(data["questions"])) * 100)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    async with aiosqlite.connect("exam_bot.db") as db:
        await db.execute("INSERT INTO results (user_id, exam, score, date) VALUES (?, ?, ?, ?)",
                         (user_id, data["exam"], percent, now))
        for q_no, u, c in data["answers"]:
            await db.execute("INSERT INTO answers (user_id, exam, q_no, user_answer, correct_answer) VALUES (?, ?, ?, ?, ?)",
                             (user_id, data["exam"], q_no, u, c))
        await db.commit()

    await bot.send_message(chat_id, f"✅ آزمون به پایان رسید!\n🎯 نمره نهایی: {percent} از ۱۰۰")
    del user_answers[user_id]

# تایمر آزمون
async def exam_timer(user_id, chat_id):
    await asyncio.sleep(40 * 60)
    if user_id in user_answers:
        await bot.send_message(chat_id, "⏰ زمان آزمون به پایان رسید!")
        await finish_exam(user_id, chat_id)

# پنل ادمین
@bot.on_message(commands=["panel"])
async def panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("⛔️ فقط ادمین می‌تونه این بخش رو ببینه.")
    text = "📋 لیست شرکت‌کنندگان:\n\n"
    async with aiosqlite.connect("exam_bot.db") as db:
        async with db.execute("""
            SELECT u.full_name, r.exam, r.score, r.date 
            FROM results r JOIN users u ON r.user_id = u.user_id
            ORDER BY r.date DESC
        """) as cursor:
            rows = await cursor.fetchall()
            for full_name, exam, score, date in rows:
                text += f"👤 {full_name}\n📘 {exam}\n🎯 نمره: {score}\n🕰 {date}\n---\n"
    await message.reply(text or "هیچ نتیجه‌ای ثبت نشده.")

# اجرای ربات
bot.run()
