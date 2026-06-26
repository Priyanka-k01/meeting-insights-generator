from fastapi import FastAPI, UploadFile, File, Form
import whisper
import mysql.connector
import json
import os
import uuid
import re
from datetime import datetime

# ---------------- ENV + GROQ ----------------
from dotenv import load_dotenv
from groq import Groq

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ---------------- APP ----------------
app = FastAPI()

# ---------------- DATABASE ----------------
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="P@ss00p",
    database="meeting_db"
)
cursor = conn.cursor()
print("✅ Connected to MySQL")

# ---------------- WHISPER ----------------
whisper_model = whisper.load_model("tiny")

# ---------------- JSON EXTRACT ----------------
def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None

# ---------------- LLM FUNCTION ----------------
def generate_insights(text):

    prompt = f"""
You are an AI meeting assistant.

Analyze the transcript and return ONLY JSON:

{{
  "summary": "short clear summary (max 5 lines)",
  "key_points": ["point 1", "point 2", "point 3"],
  "action_items": ["task 1", "task 2"]
}}

Do NOT repeat the transcript.

Transcript:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        output = response.choices[0].message.content
        data = extract_json(output)

        if data:
            summary = data.get("summary", "")
            key_points = data.get("key_points", [])
            action_items = data.get("action_items", [])
        else:
            summary = "⚠️ Failed to parse summary"
            key_points = []
            action_items = []

    except Exception as e:
        print("❌ LLM ERROR:", e)
        summary = "⚠️ LLM failed"
        key_points = []
        action_items = []

    return summary, key_points, action_items


# ---------------- HOME ----------------
@app.get("/")
def home():
    return {"message": "🚀 Server running successfully"}


# ---------------- PROCESS AUDIO ----------------
@app.post("/process-audio/")
async def process_audio(
    file: UploadFile = File(...),
    title: str = Form(...)
):

    file_path = f"temp_{uuid.uuid4().hex}_{file.filename}"

    try:
        # Save file
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # 🎤 Transcription
        result = whisper_model.transcribe(file_path)
        text = result["text"]

        # 🧠 AI Insights
        summary, key_points, action_items = generate_insights(text)

        # 💾 Save meeting
        cursor.execute("""
        INSERT INTO meetings (title, date, transcript, summary, key_points, actions, decisions)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            title,
            str(datetime.now()),
            text,
            summary,
            json.dumps(key_points),
            json.dumps(action_items),
            json.dumps([])
        ))

        conn.commit()

        # ✅ GET meeting_id
        meeting_id = cursor.lastrowid

        # ✅ SAVE ACTION ITEMS (NEW)
        for action in action_items:
            cursor.execute("""
                INSERT INTO action_items (meeting_id, action_text)
                VALUES (%s, %s)
            """, (meeting_id, action))

        conn.commit()

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return {
        "transcript": text,
        "summary": summary,
        "key_points": key_points,
        "action_items": action_items
    }


# ---------------- GET MEETINGS ----------------
@app.get("/meetings")
def get_meetings():
    cursor.execute("SELECT * FROM meetings ORDER BY id DESC")
    rows = cursor.fetchall()

    data = []

    for row in rows:
        data.append({
            "id": row[0],
            "title": row[1],
            "date": str(row[2]),
            "transcript": row[3],
            "summary": row[4],
            "key_points": json.loads(row[5]),
            "actions": json.loads(row[6]),
            "decisions": json.loads(row[7]),
        })

    return data


# ---------------- DELETE ----------------
@app.delete("/delete-meeting/{meeting_id}")
def delete_meeting(meeting_id: int):
    cursor.execute("DELETE FROM meetings WHERE id = %s", (meeting_id,))
    conn.commit()
    return {"message": "🗑️ Deleted successfully"}


# ---------------- GLOBAL SEARCH ----------------
@app.get("/search_all")
def search_all(query: str):

    conn_local = mysql.connector.connect(
        host="localhost",
        user="root",
        password="P@ss00p",
        database="meeting_db"
    )
    cursor_local = conn_local.cursor(dictionary=True)

    cursor_local.execute("SELECT id, title, transcript FROM meetings")
    meetings = cursor_local.fetchall()

    results = []

    for meeting in meetings:
        lines = meeting["transcript"].split(".")

        for line in lines:
            if query.lower() in line.lower():
                results.append({
                    "meeting_id": meeting["id"],
                    "meeting_title": meeting["title"],
                    "match": line.strip()
                })

    cursor_local.close()
    conn_local.close()

    return {"results": results}


# ---------------- DB HELPER ----------------
def get_conn():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="P@ss00p",
        database="meeting_db"
    )


# ---------------- GET ACTIONS ----------------
@app.get("/actions/{meeting_id}")
def get_actions(meeting_id: int):

    conn = get_conn()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, action_text, is_done
        FROM action_items
        WHERE meeting_id=%s
    """, (meeting_id,))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return data


# ---------------- UPDATE ACTION ----------------

from fastapi import Query

@app.put("/update-action/{action_id}")
@app.put("/update-action/{action_id}")
def update_action(action_id: int, is_done: str):

    is_done_bool = is_done.lower() == "true"

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE action_items
        SET is_done=%s
        WHERE id=%s
    """, (is_done_bool, action_id))

    conn.commit()
    cursor.close()
    conn.close()

    return {"status": "updated"}