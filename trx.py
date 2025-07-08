import asyncio
import json
from datetime import datetime
from balethon import Client

# [اصلاح شد] حذف filters از import و استفاده از روش‌های جایگزین

from balethon.objects import Message, CallbackQuery, InlineKeyboard, InlineKeyboardButton, Update
import aiosqlite

# — تنظیمات اولیه —

API_KEY = “717675061:1p9xzK4wzYVqml3dVInIV4I3HgnW15ewFAWi8aIZ”  # توکن شما
ADMIN_ID = 2143480267  # آیدی عددی ادمین

bot = Client(API_KEY)

# حافظه موقت برای آزمون‌های در حال اجرا

user_exams_in_progress = {}

EXAMS = {
“شهروند الکترونیک”: “shahrvand.json”,
“فتوشاپ”: “photoshop.json”,
“ایلیستریتور”: “illustrator.json”,
“کرل”: “corel.json”
}
DB_NAME = “exam_bot.db”

# — مدیریت پایگاه داده —

async def setup_database():
“”“پایگاه داده و جداول را در صورت عدم وجود ایجاد می‌کند.”””
async with aiosqlite.connect(DB_NAME) as db:
await db.execute(”””
CREATE TABLE IF NOT EXISTS users (
user_id INTEGER PRIMARY KEY,
full_name TEXT NOT NULL
)”””)
await db.execute(”””
CREATE TABLE IF NOT EXISTS results (
result_id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
exam TEXT NOT NULL,
score INTEGER NOT NULL,
date TEXT NOT NULL,
FOREIGN KEY (user_id) REFERENCES users(user_id)
)”””)
await db.execute(”””
CREATE TABLE IF NOT EXISTS answers (
answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
exam TEXT NOT NULL,
q_no INTEGER NOT NULL,
user_answer INTEGER NOT NULL,
correct_answer INTEGER NOT NULL,
FOREIGN KEY (user_id) REFERENCES users(user_id)
)”””)
await db.commit()
print(“Database setup complete.”)

# — توابع اصلی ربات —

async def send_exam_menu(chat_id: int):
“”“منوی انتخاب آزمون را ارسال می‌کند.”””
buttons = [[InlineKeyboardButton(text=title, callback_data=f”exam:{title}”)] for title in EXAMS]
markup = InlineKeyboard(buttons)
await bot.send_message(chat_id, “📝 یکی از آزمون‌های زیر را انتخاب کنید:”, reply_markup=markup)

# — کنترل‌کننده‌های پیام —

@bot.on_message()
async def handle_messages(message: Message):
“”“کنترل‌کننده عمومی برای تمام پیام‌های دریافتی.”””
if not message.text:
return

```
user_id = message.from_user.id

# بررسی دستور /start
if message.text.startswith("/start"):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            user = await cur.fetchone()
            if user:
                await send_exam_menu(message.chat.id)
            else:
                await message.reply("سلام! به ربات آزمون خوش آمدید.\nلطفاً نام و نام خانوادگی خود را برای ثبت‌نام وارد کنید:")
    return

# بررسی دستور /panel
if message.text.startswith("/panel"):
    if user_id == ADMIN_ID:
        await admin_panel(message)
    else:
        await message.reply("⛔️ شما مجوز دسترسی به این بخش را ندارید.")
    return

# پردازش پیام‌های عادی
async with aiosqlite.connect(DB_NAME) as db:
    async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
        user_exists = await cur.fetchone()
    
    if not user_exists:
        # ثبت نام کاربر جدید
        await db.execute("INSERT INTO users (user_id, full_name) VALUES (?, ?)", (user_id, message.text))
        await db.commit()
        await message.reply(f"✅ ثبت نام شما با نام \"{message.text}\" با موفقیت انجام شد.")
        await send_exam_menu(message.chat.id)
    elif user_id not in user_exams_in_progress:
        await message.reply("برای شروع، یکی از آزمون‌ها را از منو انتخاب کنید. /start")
```

# — کنترل‌کننده‌های کلیک —

@bot.on_callback_query()
async def handle_callback_queries(query: CallbackQuery):
“”“کنترل‌کننده عمومی برای تمام callback queryها.”””
if query.data.startswith(“exam:”):
await handle_exam_selection(query)
elif query.data.startswith(“answer:”):
await handle_answer_submission(query)

async def handle_exam_selection(query: CallbackQuery):
“”“پاسخ به کلیک روی دکمه انتخاب آزمون.”””
exam_title = query.data.split(”:”)[1]
user_id = query.from_user.id

```
async with aiosqlite.connect(DB_NAME) as db:
    async with db.execute("SELECT * FROM results WHERE user_id = ? AND exam = ?", (user_id, exam_title)) as cur:
        if await cur.fetchone():
            await query.answer("⛔️ شما قبلاً در این آزمون شرکت کرده‌اید.", show_alert=True)
            return

try:
    with open(EXAMS[exam_title], "r", encoding="utf-8") as f:
        questions = json.load(f)
except FileNotFoundError:
    await query.answer(f"خطا: فایل سوالات آزمون '{exam_title}' یافت نشد!", show_alert=True)
    return

user_exams_in_progress[user_id] = {
    "exam": exam_title,
    "questions": questions,
    "current": 0,
    "answers": [],
    "chat_id": query.message.chat.id
}

await query.answer(f"آزمون {exam_title} شروع می‌شود...")
await query.message.delete()
await send_question(user_id)
asyncio.create_task(exam_timer(user_id))
```

async def handle_answer_submission(query: CallbackQuery):
“”“پاسخ به کلیک روی گزینه‌های سوال.”””
user_id = query.from_user.id
data = user_exams_in_progress.get(user_id)
if not data:
await query.answer(“خطا: آزمون شما یافت نشد. لطفاً دوباره شروع کنید.”, show_alert=True)
return

```
selected_option_index = int(query.data.split(":")[1])
current_q_index = data["current"]

if current_q_index >= len(data["questions"]):
    return

correct_answer_index = data["questions"][current_q_index]["answer"]
data["answers"].append((current_q_index, selected_option_index, correct_answer_index))
data["current"] += 1

await query.message.delete()
await send_question(user_id)
```

# — منطق آزمون —

async def send_question(user_id: int):
“”“سوال فعلی را برای کاربر ارسال می‌کند.”””
data = user_exams_in_progress.get(user_id)
if not data:
return

```
if data["current"] >= len(data["questions"]):
    await finish_exam(user_id)
    return

q = data["questions"][data["current"]]
text = f"❓ سوال {data['current'] + 1} از {len(data['questions'])}:\n\n**{q['question']}**"
options = [[InlineKeyboardButton(opt, callback_data=f"answer:{i}")] for i, opt in enumerate(q['options'])]
markup = InlineKeyboard(options)
await bot.send_message(data["chat_id"], text, reply_markup=markup)
```

async def finish_exam(user_id: int):
“”“آزمون را به پایان رسانده و نتایج را ذخیره می‌کند.”””
if user_id not in user_exams_in_progress:
return

```
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

await bot.send_message(chat_id, f"✅ آزمون به پایان رسید!\n\n**آزمون**: {data['exam']}\n**🎯 نمره نهایی**: {percent} از ۱۰۰")
del user_exams_in_progress[user_id]
```

async def exam_timer(user_id: int):
“”“تایمر ۴۰ دقیقه‌ای برای آزمون.”””
await asyncio.sleep(40 * 60)
if user_id in user_exams_in_progress:
chat_id = user_exams_in_progress[user_id][“chat_id”]
await bot.send_message(chat_id, “⏰ زمان آزمون شما به پایان رسید!”)
await finish_exam(user_id)

# — پنل ادمین —

async def admin_panel(message: Message):
“”“نمایش نتایج آزمون‌ها برای ادمین.”””
text = “📋 **لیست نتایج شرکت‌کنندگان:**\n\n”
async with aiosqlite.connect(DB_NAME) as db:
async with db.execute(”””
SELECT u.full_name, r.exam, r.score, r.date
FROM results r JOIN users u ON r.user_id = u.user_id
ORDER BY r.date DESC
“””) as cursor:
rows = await cursor.fetchall()
if not rows:
return await message.reply(“هنوز هیچ نتیجه‌ای در سیستم ثبت نشده است.”)

```
        for full_name, exam, score, date in rows:
            text += f"👤 **نام:** {full_name}\n📘 **آزمون:** {exam}\n🎯 **نمره:** {score}\n🕰 **تاریخ:** {date}\n---\n"

# برای پیام‌های طولانی، بهتر است آن را در چند بخش ارسال کرد
for i in range(0, len(text), 4000):
    await message.reply(text[i:i + 4000])
```

# — اجرای ربات —

async def main():
await setup_database()
print(“Bot is starting…”)
await bot.run()

if **name** == “**main**”:
asyncio.run(main())
