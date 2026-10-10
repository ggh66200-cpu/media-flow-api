import os
import subprocess
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI(title="MediaFlow API", version="1.0.0")

# إعداد الربط مع Supabase (سنضع المتغيرات البيئية لاحقاً في Render)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

class MediaTaskRequest(BaseModel):
    user_id: str
    video_url: str
    action: str = "compress" # compress, convert_mp3, etc.

def process_media_background(job_id: str, video_url: str, action: str):
    """
    دالة المعالجة التي تعمل في الخلفية دون تعطيل استجابة الـ API
    """
    try:
        # 1. تحديث حالة الطلب إلى جارٍ المعالجة
        if supabase:
            supabase.table("media_jobs").update({"status": "processing"}).eq("id", job_id).execute()

        # 2. اسم الملف المؤقت
        input_file = f"temp_input_{job_id[:8]}.mp4"
        output_file = f"temp_output_{job_id[:8]}.mp4"

        # 3. تحميل الفيديو (أو استقباله)
        # ملاحظة: سنستخدم أمر wget أو curl خفيف لتحميل الملف
        download_cmd = f"curl -s -L '{video_url}' -o {input_file}"
        subprocess.run(download_cmd, shell=True, check=True)

        # 4. تطبيق أمر FFmpeg حسب الطلب
        if action == "compress":
            # ضغط الفيديو وتقليل الحجم بنفس الجودة
            ffmpeg_cmd = f"ffmpeg -i {input_file} -vcodec libx264 -crf 28 {output_file} -y"
        else:
            ffmpeg_cmd = f"ffmpeg -i {input_file} {output_file} -y"

        subprocess.run(ffmpeg_cmd, shell=True, check=True)

        # 5. هنا يتم رفع الملف الناتج إلى Supabase Storage أو إرجاع رابطه
        # (للتجربة سنضع رابطاً شاملاً لمُخرجات المعالجة)
        processed_url = f"https://your-storage-bucket.com/{output_file}"

        # 6. تحديث حالة الطلب إلى اكتمل
        if supabase:
            supabase.table("media_jobs").update({
                "status": "completed",
                "processed_url": processed_url
            }).eq("id", job_id).execute()

        # تنظيف الملفات المؤقتة من السيرفر
        if os.path.exists(input_file): os.remove(input_file)
        if os.path.exists(output_file): os.remove(output_file)

    except Exception as e:
        if supabase:
            supabase.table("media_jobs").update({"status": f"failed: {str(e)}"}).eq("id", job_id).execute()


@app.get("/")
def home():
    return {"status": "online", "message": "Welcome to MediaFlow API Engine"}


@app.post("/api/v1/process")
async def create_processing_task(payload: MediaTaskRequest, background_tasks: BackgroundTasks):
    """
    نقطة استقبال الطلبات من المطورين
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")

    # إنشاء سجل جديد في جدول media_jobs
    job_data = {
        "user_id": payload.user_id,
        "original_url": payload.video_url,
        "status": "pending"
    }
    
    response = supabase.table("media_jobs").insert(job_data).execute()
    job_id = response.data[0]["id"]

    # تشغيل عملية المعالجة في الخلفية كي يرجع الـ API رد فوري للمطور
    background_tasks.add_task(process_media_background, job_id, payload.video_url, payload.action)

    return {
        "success": True,
        "job_id": job_id,
        "status": "pending",
        "message": "Task received and is processing in background."
    }
