import streamlit as st
import os
import requests
import re
import time
from gtts import gTTS
from dotenv import load_dotenv
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips

# --- LOAD SECRETS ---
load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
OUTPUT_DIR = "output_assets"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# --- CORE LOGIC ---
def get_keyword(text):
    stop_words = {'this', 'that', 'with', 'from', 'here', 'there', 'what', 'about', 'just', 'then'}
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
    
    # High-reliability fallback
    fallback_url = "https://player.vimeo.com/external/371433846.sd.mp4?s=236da2f3c0ee273d1ae87f1d80ac3dbec9b9ef96&profile_id=165&oauth2_token_id=57447761"

    def download(url, path):
        with requests.get(url, stream=True, timeout=20) as r:
            r.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk: f.write(chunk)
        time.sleep(1)

    try:
        r = requests.get(url, headers=headers, timeout=10).json()
        video_url = r['videos'][0]['video_files'][0]['link']
        download(video_url, output_path)
        return VideoFileClip(output_path).subclipped(0, duration).resized(target_size)
    except Exception:
        download(fallback_url, output_path)
        return VideoFileClip(output_path).subclipped(0, duration).resized(target_size)

def create_scene(text, index, target_size):
    audio_path = os.path.join(OUTPUT_DIR, f"a_{index}.mp3")
    video_path = os.path.join(OUTPUT_DIR, f"v_{index}.mp4")
    
    dur = generate_audio(text, audio_path)
    v_clip = fetch_stock_video(get_keyword(text), dur, video_path, target_size)
    v_clip = v_clip.with_audio(AudioFileClip(audio_path))
    
    try:
        # Dynamic font sizing based on video height
        f_size = int(target_size[1] * 0.05) 
        txt = TextClip(
            text=text, font_size=f_size, color='white', font='Arial',
            bg_color='black', method='caption', size=(target_size[0] - 60, None)
        ).with_duration(dur).with_position(('center', 'bottom'))
        return CompositeVideoClip([v_clip, txt])
    except:
        return v_clip

# --- STREAMLIT UI ---
st.set_page_config(page_title="AI Video Engine", layout="wide")

st.sidebar.title("🛠️ Project Settings")
if not PEXELS_API_KEY:
    st.sidebar.error("❌ API Key not found in .env file!")
else:
    st.sidebar.success("✅ API Key Loaded")

ratio_choice = st.sidebar.selectbox(
    "Aspect Ratio",
    ["16:9 - YouTube/Desktop", "9:16 - TikTok/Shorts", "1:1 - Instagram/Square"]
)

# Resolution Mapping
if "16:9" in ratio_choice:
    target_size = (1280, 720)
elif "9:16" in ratio_choice:
    target_size = (720, 1280)
else:
    target_size = (1080, 1080)

st.title("🎬 DIY Pictory: Script to Video")
script = st.text_area("Paste your full script here:", height=250, placeholder="Once upon a time...")

if st.button("🚀 Start Generating", use_container_width=True):
    if not PEXELS_API_KEY:
        st.error("Please add your Pexels Key to the .env file first.")
    elif not script:
        st.error("The script is empty!")
    else:
        sentences = [s.strip() for s in re.split(r'[.!?]', script) if len(s.strip()) > 5]
        
        with st.status("🎬 Processing...", expanded=True) as status:
            clips = []
            for i, sent in enumerate(sentences):
                status.write(f"Building Scene {i+1}...")
                clips.append(create_scene(sent, i, target_size))
            
            status.write("🧵 Rendering Final Video...")
            final = concatenate_videoclips(clips, method="compose")
            final_path = "generated_video.mp4"
            final.write_videofile(final_path, fps=24, codec="libx264", audio_codec="aac")
            
            st.success("✨ Your video is ready!")
            st.video(final_path)

with open(final_path, "rb") as file:
                st.download_button(
                    label="📥 Download Video",
                    data=file,
                    file_name="my_ai_video.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )
