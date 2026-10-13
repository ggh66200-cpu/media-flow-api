import os
import telebot
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

# قراءة التوكن من إعدادات البيئة في Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

app = FastAPI(title="Media Flow API & Telegram Bot")

# نموذج البيانات القادم للـ API
class ProcessRequest(BaseModel):
    user_id: str
    video_url: str
    action: str = "compress"

# دالة المعالجة الخلفية (Background Task)
def background_media_processing(job_id: str, video_url: str, user_id: str):
    print(f"[*] Starting background task {job_id} for user {user_id}...")
    # هنا يتم تطبيق كود معالجة الفيديو لاحقاً (مثل استخدام FFmpeg)
    # حالياً نقوم بمحاكاة عملية المعالجة
    import time
    time.sleep(3)
    print(f"[+] Task {job_id} completed successfully!")
    
    # إذا كان الطلب قادماً من بوت تيليجرام، يمكننا إرسال رسالة للمستخدم هنا
    if bot and user_id.isdigit():
        try:
            bot.send_message(chat_id=int(user_id), text="✅ تم معالجة الفيديو الخاص بك بنجاح!")
        except Exception as e:
            print(f"[-] Failed to send Telegram notification: {e}")

@app.get("/")
def home():
    return {"status": "online", "message": "Media Flow API is running successfully!"}

@app.post("/api/v1/process")
def process_media(request: ProcessRequest, background_tasks: BackgroundTasks):
    import uuid
    job_id = str(uuid.uuid4())
    
    # إشعار البداية في الخلفية
    background_tasks.add_task(background_media_processing, job_id, request.video_url, request.user_id)
    
    return {
        "success": True,
        "job_id": job_id,
        "status": "pending",
        "message": "Task received and is processing in background."
    }

# إعداد تفاعل بوت تيليجرام لاستقبال الفيديوهات
if bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "أهلاً بك في بوت معالجة الميديا! أرسل لي أي فيديو وسأقوم بمعالجته لك.")

    @bot.message_handler(content_types=['video', 'document'])
    def handle_video(message):
        bot.reply_to(message, "⏳ جاري استلام الفيديو وبدء المعالجة على السيرفر...")
        try:
            # استخراج رابط الملف من تيليجرام
            file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            
            user_id = str(message.chat.id)
            
            # استدعاء دالة المعالجة مباشرة
            import uuid
            job_id = str(uuid.uuid4())
            background_media_processing(job_id, file_url, user_id)
            
        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ أثناء استقبال الملف: {str(e)}")

    # تشغيل البوت في الخلفية ليبقى مستምعاً للرسائل
    import threading
    def run_telegram_bot():
        print("[*] Telegram Bot polling started...")
        bot.infinity_polling()
        
    threading.Thread(target=run_telegram_bot, daemon=True).start()
