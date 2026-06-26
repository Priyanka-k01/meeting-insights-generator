import streamlit as st
import requests
import re
from streamlit_mic_recorder import mic_recorder
from datetime import datetime

# ✅ STEP 1
import io
import time

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# =====================================================
# ✅ STEP 2 - FIXED PDF FUNCTION
# =====================================================
def generate_pdf(meeting):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph(f"<b>{meeting.get('title')}</b>", styles["Title"]))
    content.append(Spacer(1, 10))

    raw_date = meeting.get("date", "")
    try:
        dt = datetime.fromisoformat(raw_date)
        date = dt.strftime("%d %b %Y")
        time_str = dt.strftime("%H:%M:%S")
    except:
        date = raw_date
        time_str = ""

    content.append(Paragraph(f"<b>Date:</b> {date}", styles["Normal"]))
    content.append(Paragraph(f"<b>Time:</b> {time_str}", styles["Normal"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("<b>Summary</b>", styles["Heading2"]))
    content.append(Paragraph(meeting.get("summary", ""), styles["Normal"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("<b>Key Points</b>", styles["Heading2"]))
    for kp in meeting.get("key_points", []):
        content.append(Paragraph(f"• {kp}", styles["Normal"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("<b>Action Items</b>", styles["Heading2"]))
    for act in meeting.get("actions", []):
        content.append(Paragraph(f"• {act}", styles["Normal"]))

    doc.build(content)
    buffer.seek(0)
    return buffer


# ---------------- CONFIG ----------------
st.set_page_config(page_title="Meeting Insights", layout="wide")

def safe_rerun():
    st.rerun()

# ---------------- STYLING ----------------
st.markdown("""
<style>
.main {background: linear-gradient(135deg, #0f172a, #1e293b); color: white;}
.stButton>button {border-radius: 10px; background: #6366f1; color: white;}
.card {background: #1e293b; padding: 15px; border-radius: 12px; margin-bottom: 10px;}
.scroll-box {height:350px; overflow-y:auto; background:#0f172a; padding:15px; border-radius:10px; border:1px solid #334155;}
.match-box {background: linear-gradient(135deg, #1e293b, #334155); padding: 12px; border-radius: 10px; margin-bottom: 8px; border-left: 4px solid #6366f1;}
</style>
""", unsafe_allow_html=True)

# ---------------- SESSION ----------------
if "page" not in st.session_state:
    st.session_state.page = "upload"
if "selected_meeting" not in st.session_state:
    st.session_state.selected_meeting = None
if "show_full" not in st.session_state:
    st.session_state.show_full = True

# =====================================================
# ✅ STEP 3 - CACHING
# =====================================================
@st.cache_data(ttl=10)
def get_meetings():
    try:
        res = requests.get("http://127.0.0.1:8000/meetings", timeout=2)
        if res.status_code == 200:
            return res.json()
    except:
        return []
    return []

meetings = get_meetings()

# =====================================================
# 🔥 NEW: GLOBAL SEARCH FUNCTION
# =====================================================
def search_all_meetings(query):
    try:
        res = requests.get("http://127.0.0.1:8000/search_all", params={"query": query}, timeout=5)
        if res.status_code == 200:
            return res.json().get("results", [])
    except:
        return []
    return []

# ---------------- SIDEBAR ----------------
st.sidebar.markdown("## ⚙️ Controls")

if st.sidebar.button("📤 Upload"):
    st.session_state.page = "upload"
    safe_rerun()

st.sidebar.markdown("---")

# =====================================================
# 🔥 NEW: MART SEARCH (GLOBAL)
# =====================================================
st.sidebar.markdown("## 🔍 SMART SEARCH")

global_query = st.sidebar.text_input("Search ALL meetings")

if global_query:
    results = search_all_meetings(global_query)

    if results:
        for i, r in enumerate(results[:10]):
            st.sidebar.markdown(f"**📌 {r['meeting_title']}**")
            st.sidebar.markdown(f"➡️ {r['match']}")

            if st.sidebar.button(f"Open", key=f"global_{i}"):
                for m in meetings:
                    if m.get("id") == r["meeting_id"]:
                        st.session_state.selected_meeting = m
                        st.session_state.page = "details"
                        safe_rerun()
    else:
        st.sidebar.info("No matches found")

st.sidebar.markdown("---")
st.sidebar.title("📊 Recent Meetings")

for i, m in enumerate(meetings[:10]):
    title = m.get("title", "Untitled Meeting")
    raw_date = m.get("date", "")

    try:
        dt = datetime.fromisoformat(raw_date)
        date = dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        date = raw_date

    meeting_id = m.get("id")

    col1, col2 = st.sidebar.columns([4,1])

    with col1:
        if st.button(f"📌 {title}\n🗓 {date}", key=f"sb_{i}"):
            st.session_state.selected_meeting = m
            st.session_state.page = "details"
            safe_rerun()

    with col2:
        if st.button("🗑", key=f"del_sb_{i}"):
            try:
                requests.delete(f"http://127.0.0.1:8000/delete-meeting/{meeting_id}", timeout=2)
                get_meetings.clear()
            except:
                pass
            safe_rerun()

# =====================================================
# (बाकी आपका पूरा code SAME है — unchanged)
# =====================================================

# =====================================================
# PAGE 1 - UPLOAD
# =====================================================
if st.session_state.page == "upload":

    st.title("🎤 Smart Meeting Analyzer")

    uploaded_file = st.file_uploader("Upload audio", type=["mp3", "wav"])
    meeting_title = st.text_input("Meeting Title")

    if uploaded_file:
        audio_bytes = uploaded_file.read()
        st.session_state.audio_bytes = audio_bytes
        st.audio(audio_bytes)
        uploaded_file.seek(0)

    audio = mic_recorder(start_prompt="▶ Start recording", stop_prompt="⏹ Stop")

    if audio:
        st.session_state.audio_bytes = audio["bytes"]
        st.audio(audio["bytes"])

    if st.button("🚀 Generate Insights"):

        if (uploaded_file or audio) and meeting_title:

            if uploaded_file:
                uploaded_file.seek(0)
                files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
            else:
                files = {"file": ("recorded.wav", io.BytesIO(audio["bytes"]), "audio/wav")}

            # ✅ STEP 5 (spinner + progress)
            progress = st.progress(0, text="Starting...")

            with st.spinner("⏳ Processing audio..."):

                progress.progress(20, text="Uploading audio...")
                time.sleep(0.3)

                try:
                    response = requests.post(
                        "http://127.0.0.1:8000/process-audio/",
                        files=files,
                        data={"title": meeting_title},
                        timeout=500
                    )

                    progress.progress(60, text="Transcribing...")
                    time.sleep(0.3)

                    if response.status_code == 200:
                        data = response.json()

                        progress.progress(90, text="Generating insights...")
                        time.sleep(0.3)

                        st.session_state.transcript = data.get("transcript", "")
                        st.session_state.summary = data.get("summary", "")
                        st.session_state.key_points = data.get("key_points", [])
                        st.session_state.action_items = data.get("action_items", [])

                        progress.progress(100, text="Done!")
                        st.success("✅ Insights generated!")

                        st.session_state.page = "results"
                        safe_rerun()

                    else:
                        st.warning("Something went wrong.")

                except:
                    pass

        else:
            st.warning("Upload/record audio + title")

# =====================================================
# PAGE 2 - RESULTS (FULLY RESTORED)
# =====================================================
# =====================================================
# PAGE 2 - RESULTS (FULL + RECENT MEETINGS RESTORED)
# =====================================================

if st.session_state.page == "results":

    st.title("📊 Results & Insights")

    if "summary" not in st.session_state:
        st.info("No data yet")

    else:
        # -------- SUMMARY --------
        st.markdown(f"<div class='card'><b>📝 Summary</b><br>{st.session_state.summary}</div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        # -------- TRANSCRIPT + SEARCH --------
        with col1:
            st.subheader("📄 Transcript")

            transcript = st.session_state.transcript
            search = st.text_input("🔍 Search")

            display_text = transcript

            if search:
                pattern = re.compile(re.escape(search), re.IGNORECASE)
                match = pattern.search(transcript)

                if match:
                    start_pos = match.start()
                    display_text = transcript[start_pos:]

                display_text = re.sub(
                    pattern,
                    lambda m: f"<mark style='background:yellow;color:black'>{m.group(0)}</mark>",
                    display_text
                )

            st.markdown(f"<div class='scroll-box'>{display_text}</div>", unsafe_allow_html=True)

            # -------- MATCHING SENTENCES --------
            if search:
                st.markdown("### 🔎 Matching Sentences")

                sentences = re.split(r'(?<=[.!?]) +', transcript)

                found = False
                for s in sentences:
                    if search.lower() in s.lower():
                        found = True
                        st.markdown(f"<div class='match-box'>{s}</div>", unsafe_allow_html=True)

                if not found:
                    st.info("No matching sentences found")

        # -------- RIGHT PANEL --------
        with col2:
            st.subheader("📌 Key Highlights")
            for k in st.session_state.key_points:
                st.markdown(f"<div class='match-box'>✨ {k}</div>", unsafe_allow_html=True)

            st.subheader("✅ Action Items")

            for a in st.session_state.action_items:
                st.markdown(f"<div class='match-box'>🚀 {a}</div>", unsafe_allow_html=True)

        st.download_button("⬇ Download Summary", st.session_state.summary)

    # =====================================================
    # ✅ RECENT MEETINGS (RESTORED + STRUCTURED)
    # =====================================================
    st.markdown("## 📂 Recent Meetings")

    if not meetings:
        st.info("No meetings available yet")

    for i, m in enumerate(meetings[:5]):

        with st.expander(f"📌 {m.get('title')}"):

            # -------- DATE + TIME --------
            raw_date = m.get("date", "")
            try:
                dt = datetime.fromisoformat(raw_date)
                date = dt.strftime("%d %b %Y")
                time = dt.strftime("%H:%M:%S")
            except:
                date = raw_date
                time = ""

            st.markdown(f"""
            <div class='card'>
                <b>📅 {date}</b><br>
                <b>⏰ {time}</b>
            </div>
            """, unsafe_allow_html=True)

            # -------- SUMMARY --------
            st.markdown(f"""
            <div class='card'>
                <b>🧠 Summary</b><br>
                {m.get("summary")}
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            # -------- KEY POINTS --------
            with col1:
                st.markdown("### 📌 Key Highlights")
                key_points = m.get("key_points", [])

                if isinstance(key_points, list):
                    for k in key_points:
                        st.markdown(f"<div class='match-box'>✨ {k}</div>", unsafe_allow_html=True)
                else:
                    st.write(key_points)

            # -------- ACTIONS --------
        with col2:
            st.markdown("### ✅ Action Items")
            try:
                actions = requests.get(
                   f"http://127.0.0.1:8000/actions/{m.get('id')}",
                   timeout=3
                ).json()
            except:
                actions = []

            for act in actions:

                c1, c2 = st.columns([1, 10])

                with c1:
                    new_val = st.checkbox(
                        "done",
                        value=act["is_done"],
                        key=f"recent_{act['id']}",
                        label_visibility="collapsed"
                    )

                with c2:
                    st.markdown(
                        f"""
                        <span style="
                        text-decoration: {'line-through' if new_val else 'none'};
                         opacity: {'0.5' if new_val else '1'};
                         font-size:16px;
                        ">
                         {act["action_text"]}
                         </span>
                         """,
                        unsafe_allow_html=True
                    )

    # 🔥 SYNC WITH DB
                if new_val != act["is_done"]:
                    try:
                        requests.put(
                    f"http://127.0.0.1:8000/update-action/{act['id']}",
                    params={"is_done": str(new_val).lower()},
                    timeout=3
                )
                        st.rerun()
                    except:
                        pass

            # -------- BUTTONS --------
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
                if st.button("🔍 Open", key=f"open_{i}"):
                    st.session_state.selected_meeting = m
                    st.session_state.page = "details"
                    safe_rerun()

        with col2:
                if st.button("🗑 Delete", key=f"del_main_{i}"):
                    try:
                        requests.delete(f"http://127.0.0.1:8000/delete-meeting/{m.get('id')}", timeout=2)
                        get_meetings.clear()  # refresh cache
                    except:
                        pass
                    safe_rerun()
# =====================================================
# PAGE 3 - DETAILS (WITH PDF FIX)
# =====================================================
if st.session_state.page == "details":

    m = st.session_state.selected_meeting

    if m:
        st.title("📌 Meeting Insights Dashboard")

        raw_date = m.get("date", "")

        try:
            dt = datetime.fromisoformat(raw_date)
            formatted_date = dt.strftime("%d %b %Y")
            formatted_time = dt.strftime("%H:%M:%S")
        except:
            formatted_date = raw_date
            formatted_time = ""

        st.markdown(f"""
        <div class='card'>
            <h2>📂 {m.get("title")}</h2>
            <p>📅 <b>Date:</b> {formatted_date}</p>
            <p>⏰ <b>Time:</b> {formatted_time}</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"<div class='card'><h3>🧠 Executive Summary</h3>{m.get('summary')}</div>", unsafe_allow_html=True)
            st.markdown("<h3>📄 Full Transcript</h3>", unsafe_allow_html=True)
            st.markdown(f"<div class='scroll-box'>{m.get('transcript')}</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("<h3>📌 Key Highlights</h3>", unsafe_allow_html=True)
            for k in m.get("key_points", []):
                st.markdown(f"<div class='match-box'>✨ {k}</div>", unsafe_allow_html=True)

            st.markdown("<h3>✅ Action Items</h3>", unsafe_allow_html=True)

            try:
                actions = requests.get(
                    f"http://127.0.0.1:8000/actions/{m.get('id')}",
                 timeout=3
                ).json()
            except:
                actions = []

            for act in actions:

                checked = act["is_done"]

                new_val = st.checkbox(
                    act["action_text"],
                    value=checked,
                    key=f"detail_{act['id']}"
                 )

                if new_val != checked:
                    try:
                        
                        requests.put(
                            f"http://127.0.0.1:8000/update-action/{act['id']}",
                            params={"is_done": str(new_val).lower()},
                             timeout=3
                        )

                        st.success("Updated ✅")

                        st.rerun()

                    except Exception as e:
                        st.error(f"Update failed: {e}")

        if st.button("⬅ Back to Results"):
            st.session_state.page = "results"
            safe_rerun()

        # ✅ STEP 6 (PDF FIX)
        pdf_buffer = generate_pdf(m)

        st.download_button(
            label="📄 Download Full Report",
            data=pdf_buffer,
            file_name="meeting_report.pdf",
            mime="application/pdf"
        )