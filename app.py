import streamlit as st
import os
import requests
import re
import time
from gtts import gTTS
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, ColorClip

# --- 1. CLOUD CONFIGURATION ---
if "PEXELS_API_KEY" in st.secrets:
    PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
else:
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

OUTPUT_DIR = "output_assets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 2. CORE LOGIC ---
def get_keyword(text):
    stop_words = {'this', 'that', 'with', 'from', 'here', 'there', 'what', 'about', 'just', 'then', 'when', 'some'}
    words = [w for w in re.findall(r'\w+', text.lower()) if len(w) > 3 and w not in stop_words]
    return max(words, key=len) if words else "abstract"

def generate_audio(text, output_path):
    if os.path.exists(output_path):
        try: os.remove(output_path)
        except: pass
    tts = gTTS(text=text, lang='en', slow=False)
    tts.save(output_path)
    audio = AudioFileClip(output_path)
    return audio.duration

def fetch_stock_video(keyword, duration, output_path, target_size):
    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    orientation = "portrait" if target_size[0] < target_size[1] else "landscape"
    search_url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation={orientation}"
    
    # Pre-delete
    if os.path.exists(output_path):
        try: os.remove(output_path)
        except: pass

    try:
        # Search for video
        resp = requests.get(search_url, headers=headers, timeout=15)
        resp.raise_for_status()
        video_data = resp.json()
        
        # Get direct link
        video_url = video_data['videos'][0]['video_files'][0]['link']
        
        # Download video
        with requests.get(video_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
        
        # Validate file size
        if os.path.getsize(output_path) > 50000:
            time.sleep(1)
            return VideoFileClip(output_path).subclipped(0, duration).resized(target_size)
        else:
            raise ValueError("File corrupted or empty")

    except Exception as e:
        st.warning(f"⚠️ Video failed for '{keyword}'. Using solid background.")
        # ABSOLUTE FALLBACK: Create a solid blue/black background so it never crashes
        return ColorClip(size=target_size, color=(20, 20, 20), duration=duration)

def create_scene(text, index, target_size):
    audio_path = os.path.join(OUTPUT_DIR, f"a_{index}.mp3")
    video_path = os.path.join(OUTPUT_DIR, f"v_{index}.mp4")
    
    dur = generate_audio(text, audio_path)
    v_clip = fetch_stock_video(get_keyword(text), dur, video_path, target_size)
    v_clip = v_clip.with_audio(AudioFileClip(audio_path))
    
    try:
        f_size = int(target_size[1] * 0.05) 
        txt = TextClip(
            text=text, font_size=f_size, color='white', font='Arial',
            bg_color='black', method='caption', size=(target_size[0] - 80, None)
        ).with_duration(dur).with_position(('center', 'bottom'))
        return CompositeVideoClip([v_clip, txt])
    except:
        return v_clip

# --- 3. UI ---
st.set_page_config(page_title="AI Video Engine", layout="wide")

st.sidebar.title("🛠️ Settings")
ratio_choice = st.sidebar.selectbox("Aspect Ratio", ["16:9 - YouTube", "9:16 - Shorts", "1:1 - Square"])

if "16:9" in ratio_choice: target_size = (1280, 720)
elif "9:16" in ratio_choice: target_size = (720, 1280)
else: target_size = (1080, 1080)

st.title("🎬 AI Video Generator")
script = st.text_area("Enter Script:", height=200)

if st.button("🚀 Generate"):
    if not PEXELS_API_KEY:
        st.error("Missing Pexels API Key in Secrets!")
    elif not script:
        st.warning("Script is empty.")
    else:
        sentences = [s.strip() for s in re.split(r'[.!?]', script) if len(s.strip()) > 5]
        
        with st.status("Processing...") as status:
            clips = []
            for i, sent in enumerate(sentences):
                status.write(f"Scene {i+1}...")
                clips.append(create_scene(sent, i, target_size))
            
            status.write("Rendering...")
            final_path = "out.mp4"
            final = concatenate_videoclips(clips, method="compose")
            final.write_videofile(final_path, fps=24, codec="libx264", audio_codec="aac")
            
            st.video(final_path)
            with open(final_path, "rb") as f:
                st.download_button("Download Video", f, "video.mp4", "video/mp4")
