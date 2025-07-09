import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.types import User
import aiosqlite
import logging

# Configure logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


API_ID = '18377832'  # Get from my.telegram.org
API_HASH = 'ed8556c450c6d0fd68912423325dd09c'  # Get from my.telegram.org
BOT_TOKEN = "8186718003:AAGoJsGyE7SajlKv2SDbII5_NUuo-ptk40B" # Ensure this is correct
ADMIN_ID = 1848591768


# Initialize the bot client globally, but don't start it here.
# The .start() call needs to happen within an asyncio event loop.
bot = TelegramClient('bot', API_ID, API_HASH)


user_exams_in_progress = {}

EXAMS = {
    "شهروند الکترونیک": "shahrvand.json",
    "فتوشاپ": "photoshop.json",
    "ایلیستریتور": "illustrator.json",
    "کرل": "corel.json"
}
DB_NAME = "exam_bot.db"

# --- Database Management ---
async def setup_database():
    """Creates the database and tables if they don't exist."""
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
    logger.info("Database setup complete.")


async def send_exam_menu(chat_id: int):
    """Sends the exam selection menu."""
    logger.info(f"Sending exam menu to chat {chat_id}")
    buttons = []
    for title in EXAMS:
        buttons.append([Button.inline(title, f"exam:{title}")])
    
    await bot.send_message(chat_id, "📝 یکی از آزمون‌های زیر را انتخاب کنید:", buttons=buttons)


@bot.on(events.NewMessage(pattern='/start'))
async def handle_start(event):
    """Handles the /start command."""
    logger.info(f"Start command from user: {event.sender_id}")
    
    user_id = event.sender_id
    
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                user = await cur.fetchone()
                logger.info(f"User found in DB: {user}")
                if user:
                    await send_exam_menu(event.chat_id)
                else:
                    await event.reply("سلام! به ربات آزمون خوش آمدید.\nلطفاً نام و نام خانوادگی خود را برای ثبت‌نام وارد کنید:")
    except Exception as e:
        logger.exception(f"Error in start command for user {user_id}")
        await event.reply("خطا در سیستم. لطفاً دوباره تلاش کنید.")

@bot.on(events.NewMessage(pattern='/panel'))
async def handle_panel(event):
    """Handles the /panel command."""
    logger.info(f"Panel command from user: {event.sender_id}")
    
    if event.sender_id == ADMIN_ID:
        await admin_panel(event)
    else:
        await event.reply("⛔️ شما مجوز دسترسی به این بخش را ندارید.")

@bot.on(events.NewMessage)
async def handle_messages(event):
    """General handler for all incoming messages."""

    # Ignore commands to prevent reprocessing
    if event.text and (event.text.startswith('/start') or event.text.startswith('/panel')):
        return
    
    # Ignore messages without text content
    if not event.text:
        return
    
    logger.info(f"Message received: '{event.text}' from user: {event.sender_id} in chat: {event.chat_id}")
    
    user_id = event.sender_id
    
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                user_exists = await cur.fetchone()
            
            if not user_exists:
                # Register new user
                await db.execute("INSERT INTO users (user_id, full_name) VALUES (?, ?)", (user_id, event.text))
                await db.commit()
                await event.reply(f"✅ ثبت نام شما با نام \"{event.text}\" با موفقیت انجام شد.")
                await send_exam_menu(event.chat_id)
            elif user_id not in user_exams_in_progress:
                # If user exists and is not in an exam, prompt them to start one
                await event.reply("برای شروع، یکی از آزمون‌ها را از منو انتخاب کنید. /start")
    except Exception as e:
        logger.exception(f"Error in general message handling for user {user_id}")
        await event.reply("خطا در سیستم. لطفاً دوباره تلاش کنید.")


@bot.on(events.CallbackQuery)
async def handle_callback_queries(event):
    """General handler for all callback queries."""
    data = event.data.decode()
    logger.info(f"Callback query received: {data} from user: {event.sender_id}")
    
    if data.startswith("exam:"):
        await handle_exam_selection(event)
    elif data.startswith("answer:"):
        await handle_answer_submission(event)

async def handle_exam_selection(event):
    """Responds to an exam selection button click."""
    exam_title = event.data.decode().split(":")[1]
    user_id = event.sender_id
    logger.info(f"Exam selected: {exam_title} by user {user_id}")

    try:
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
            logger.error(f"Exam file not found: {EXAMS[exam_title]}")
            return

        user_exams_in_progress[user_id] = {
            "exam": exam_title,
            "questions": questions,
            "current": 0,
            "answers": [],
            "chat_id": event.chat_id,
            "timer_task": None # To store the timer task
        }

        await event.answer(f"آزمون {exam_title} شروع می‌شود...")
        await event.delete() # Delete the message with exam selection buttons
        
        # Start the exam timer and store its task
        user_exams_in_progress[user_id]["timer_task"] = asyncio.create_task(exam_timer(user_id))
        await send_question(user_id)
    except Exception as e:
        logger.exception(f"Error in exam selection for user {user_id} and exam {exam_title}")
        await event.answer("خطا در شروع آزمون. لطفاً دوباره تلاش کنید.", alert=True)


async def handle_answer_submission(event):
    """Responds to a question option button click."""
    user_id = event.sender_id
    data = user_exams_in_progress.get(user_id)
    if not data:
        await event.answer("خطا: آزمون شما یافت نشد. لطفاً دوباره شروع کنید.", alert=True)
        logger.warning(f"Answer submission for non-existent exam for user {user_id}")
        return

    try:
        selected_option_index = int(event.data.decode().split(":")[1])
        current_q_index = data["current"]
        
        # Prevent out-of-bounds access if multiple answers for the same question are sent
        if current_q_index >= len(data["questions"]):
            logger.warning(f"Received answer for question beyond exam length for user {user_id}")
            await event.answer("این سوال قبلاً پاسخ داده شده یا آزمون به پایان رسیده است.", alert=True)
            return

        correct_answer_index = data["questions"][current_q_index]["answer"]
        data["answers"].append((current_q_index, selected_option_index, correct_answer_index))
        data["current"] += 1
        
        await event.delete() # Delete the previous question message
        await send_question(user_id)
    except Exception as e:
        logger.exception(f"Error in answer submission for user {user_id}")
        await event.answer("خطا در ثبت پاسخ. لطفاً دوباره تلاش کنید.", alert=True)


async def send_question(user_id: int):
    """Sends the current question to the user."""
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
    
    try:
        await bot.send_message(data["chat_id"], text, buttons=buttons)
    except Exception as e:
        logger.exception(f"Error sending question to user {user_id}")
        # Optionally, try to finish the exam if sending question fails
        await bot.send_message(data["chat_id"], "خطا در ارسال سوال. آزمون به پایان رسید.")
        await finish_exam(user_id)

async def finish_exam(user_id: int):
    """Finishes the exam and saves the results."""
    if user_id not in user_exams_in_progress:
        return
        
    data = user_exams_in_progress[user_id]
    chat_id = data["chat_id"]
    
    # Cancel the associated timer task if it's still running
    if data["timer_task"] and not data["timer_task"].done():
        data["timer_task"].cancel()
        try:
            await data["timer_task"] # Await to ensure it's cancelled and handles any cleanup
        except asyncio.CancelledError:
            pass # Expected
    
    score = sum(1 for _, user_ans, correct_ans in data["answers"] if user_ans == correct_ans)
    percent = int((score / len(data["questions"])) * 100) if data["questions"] else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT INTO results (user_id, exam, score, date) VALUES (?, ?, ?, ?)",
                            (user_id, data["exam"], percent, now))
            for q_no, u_ans, c_ans in data["answers"]:
                await db.execute("INSERT INTO answers (user_id, exam, q_no, user_answer, correct_answer) VALUES (?, ?, ?, ?, ?)",
                                (user_id, data["exam"], q_no, u_ans, c_ans))
            await db.commit()

        await bot.send_message(chat_id, f"✅ آزمون به پایان رسید!\n\nآزمون: {data['exam']}\n🎯 نمره نهایی: {percent} از ۱۰۰")
    except Exception as e:
        logger.exception(f"Error finishing exam or saving results for user {user_id}")
        await bot.send_message(chat_id, "خطا در ثبت نتایج آزمون شما.")
    finally:
        del user_exams_in_progress[user_id]
        logger.info(f"Exam for user {user_id} finished and data cleared.")


async def exam_timer(user_id: int):
    """40-minute timer for the exam."""
    try:
        await asyncio.sleep(40 * 60) # 40 minutes in seconds
        if user_id in user_exams_in_progress:
            chat_id = user_exams_in_progress[user_id]["chat_id"]
            await bot.send_message(chat_id, "⏰ زمان آزمون شما به پایان رسید!")
            await finish_exam(user_id)
            logger.info(f"Exam timer for user {user_id} expired.")
    except asyncio.CancelledError:
        logger.info(f"Exam timer for user {user_id} was cancelled.")
        pass # Timer was cancelled, which is expected if exam finishes normally
    except Exception as e:
        logger.exception(f"Error in exam timer for user {user_id}")


async def admin_panel(event):
    """Displays exam results for the admin."""
    text = "📋 لیست نتایج شرکت‌کنندگان:\n\n"
    try:
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
        
        # Telegram message limit is 4096 characters for text messages.
        # Splitting if the text is too long.
        for i in range(0, len(text), 4000): # Use 4000 to be safe
            await event.reply(text[i:i + 4000])
    except Exception as e:
        logger.exception(f"Error in admin panel for admin {event.sender_id}")
        await event.reply("خطا در نمایش پنل ادمین.")


async def main():
    """Main function to run the bot."""
    await setup_database()
    
    logger.info("Bot is starting...")
    # This is the crucial change:
    # Use 'async with bot:' for proper connection management within an event loop.
    # It ensures the client is properly started and disconnected.
    async with bot:
        logger.info("Bot client connected. Running until disconnected...")
        await bot.run_until_disconnected()
    logger.info("Bot has disconnected.")

if __name__ == "__main__":
    # Ensure there's only one asyncio.run() call for the entire application lifecycle.
    # asyncio.run() creates a new event loop and closes it at the end.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
    except Exception as e:
        logger.exception("An unhandled error occurred in the main execution.")

