import streamlit as st
import os
import requests
import re
import time
from gtts import gTTS
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips

# --- SECRETS HANDLING ---
# Streamlit Cloud uses st.secrets, Local uses .env or manual keys.
# This check handles both automatically.
if "PEXELS_API_KEY" in st.secrets:
    PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
else:
    # Fallback for local testing if you don't have secrets.toml
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "YOUR_KEY_HERE")

OUTPUT_DIR = "output_assets"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_keyword(text):
    stop_words = {'this', 'that', 'with', 'from', 'here', 'there', 'what', 'about', 'just', 'then', 'into', 'when'}
    words = [w for w in re.findall(r'\w+', text.lower()) if len(w) > 3 and w not in stop_words]
    return max(words, key=len) if words else "abstract"

def generate_audio(text, output_path):
    if os.path.exists(output_path):
        try: os.remove(output_path)
        except: pass
    tts = gTTS(text=text, lang='en', slow=False)
    tts.save(output_path)
    return AudioFileClip(output_path).duration

def fetch_stock_video(keyword, duration, output_path, target_size):
    headers = {"Authorization": PEXELS_API_KEY}
    orientation = "portrait" if target_size[0] < target_size[1] else "landscape"
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation={orientation}"
    
    # NEW RELIABLE FALLBACK (Direct link to a sample MP4)
    fallback_url = "https://www.w3schools.com/html/mov_bbb.mp4"

    def download(target_url, path):
        # We don't use raise_for_status() inside the fallback attempt to avoid crashing
        r = requests.get(target_url, stream=True, timeout=20)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk: f.write(chunk)
            return True
        return False

    if os.path.exists(output_path):
        try: os.remove(output_path)
        except: pass

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        video_url = data['videos'][0]['video_files'][0]['link']
        
        if download(video_url, output_path):
            time.sleep(1)
            return VideoFileClip(output_path).subclipped(0, duration).resized(target_size)
        else:
            raise Exception("Download failed")
            
    except Exception as e:
        st.warning(f"⚠️ Search failed for '{keyword}', using fallback.")
        download(fallback_url, output_path)
        time.sleep(1)
        return VideoFileClip(output_path).subclipped(0, duration).resized(target_size)

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
            bg_color='black', method='caption', size=(target_size[0] - 60, None)
        ).with_duration(dur).with_position(('center', 'bottom'))
        return CompositeVideoClip([v_clip, txt])
    except Exception:
        return v_clip

# --- UI ---
st.set_page_config(page_title="AI Video Engine", layout="wide")

st.sidebar.title("🛠️ Settings")
ratio_choice = st.sidebar.selectbox(
    "Aspect Ratio",
    ["16:9 - YouTube", "9:16 - Shorts", "1:1 - Square"]
)

if "16:9" in ratio_choice: target_size = (1280, 720)
elif "9:16" in ratio_choice: target_size = (720, 1280)
else: target_size = (1080, 1080)

st.title("🎬 DIY Pictory")
script = st.text_area("Paste script:", height=200)

if st.button("🚀 Generate Video", use_container_width=True):
    if not PEXELS_API_KEY or PEXELS_API_KEY == "YOUR_KEY_HERE":
        st.error("Missing API Key! Add it to Streamlit Secrets.")
    elif not script:
        st.error("Script is empty!")
    else:
        sentences = [s.strip() for s in re.split(r'[.!?]', script) if len(s.strip()) > 5]
        
        with st.status("Building...", expanded=True) as status:
            clips = []
            for i, sent in enumerate(sentences):
                status.write(f"Scene {i+1}...")
                clips.append(create_scene(sent, i, target_size))
            
            status.write("Rendering...")
            final_path = "generated_video.mp4"
            final = concatenate_videoclips(clips, method="compose")
            final.write_videofile(final_path, fps=24, codec="libx264", audio_codec="aac")
            
            st.success("Video Ready!")
            st.video(final_path)
            
            with open(final_path, "rb") as f:
                st.download_button("📥 Download Video", f, "video.mp4", "video/mp4")
