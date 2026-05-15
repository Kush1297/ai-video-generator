import streamlit as st
import os
import requests
import re
import time
from gtts import gTTS
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips

# --- 1. CLOUD CONFIGURATION ---
# Check if we are on Streamlit Cloud or Local
if "PEXELS_API_KEY" in st.secrets:
    PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
else:
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "YOUR_LOCAL_KEY_HERE")

OUTPUT_DIR = "output_assets"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# --- 2. CORE LOGIC ---
def get_keyword(text):
    """Extracts the most descriptive word for stock footage search."""
    stop_words = {'this', 'that', 'with', 'from', 'here', 'there', 'what', 'about', 'just', 'then', 'when', 'some'}
    words = [w for w in re.findall(r'\w+', text.lower()) if len(w) > 3 and w not in stop_words]
    return max(words, key=len) if words else "abstract"

def generate_audio(text, output_path):
    """Generates TTS audio and returns duration."""
    if os.path.exists(output_path):
        try: os.remove(output_path)
        except: pass
    tts = gTTS(text=text, lang='en', slow=False)
    tts.save(output_path)
    audio = AudioFileClip(output_path)
    return audio.duration

def fetch_stock_video(keyword, duration, output_path, target_size):
    """Downloads video from Pexels with orientation matching."""
    headers = {"Authorization": PEXELS_API_KEY}
    orientation = "portrait" if target_size[0] < target_size[1] else "landscape"
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation={orientation}"
    
    # Reliable web-stable fallback
    fallback_url = "https://www.w3schools.com/html/mov_bbb.mp4"

    def download_file(url, path):
        try:
            with requests.get(url, stream=True, timeout=20) as r:
                if r.status_code == 200:
                    with open(path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024*1024):
                            f.write(chunk)
                    return True
        except: pass
        return False

    # Attempt Pexels Download
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        video_url = data['videos'][0]['video_files'][0]['link']
        if download_file(video_url, output_path):
            time.sleep(1) # Wait for file lock to release
            clip = VideoFileClip(output_path).subclipped(0, duration)
            return clip.resized(target_size)
    except:
        pass # Fall through to fallback

    # Fallback if Pexels fails
    download_file(fallback_url, output_path)
    time.sleep(1)
    return VideoFileClip(output_path).subclipped(0, duration).resized(target_size)

def create_scene(text, index, target_size):
    """Combines Video + Audio + Subtitles."""
    audio_path = os.path.join(OUTPUT_DIR, f"a_{index}.mp3")
    video_path = os.path.join(OUTPUT_DIR, f"v_{index}.mp4")
    
    dur = generate_audio(text, audio_path)
    v_clip = fetch_stock_video(get_keyword(text), dur, video_path, target_size)
    v_clip = v_clip.with_audio(AudioFileClip(audio_path))
    
    # Text overlay with error safety for ImageMagick
    try:
        f_size = int(target_size[1] * 0.05) 
        txt = TextClip(
            text=text, font_size=f_size, color='white', font='Arial',
            bg_color='black', method='caption', size=(target_size[0] - 80, None)
        ).with_duration(dur).with_position(('center', 'bottom'))
        return CompositeVideoClip([v_clip, txt])
    except:
        # If subtitles fail (missing ImageMagick), return raw video
        return v_clip

# --- 3. STREAMLIT UI ---
st.set_page_config(page_title="AI Video Engine", layout="wide", page_icon="🎬")

st.sidebar.title("🛠️ Project Settings")
ratio_choice = st.sidebar.selectbox(
    "Aspect Ratio",
    ["16:9 - YouTube", "9:16 - TikTok/Shorts", "1:1 - Instagram"]
)

# Resolution setup
if "16:9" in ratio_choice: target_size = (1280, 720)
elif "9:16" in ratio_choice: target_size = (720, 1280)
else: target_size = (1080, 1080)

st.title("🎬 AI Script-to-Video Generator")
st.info("Paste your script. Every sentence will become a new scene with stock footage.")

script = st.text_area("Your Script:", height=250, placeholder="Type your story here...")

if st.button("🚀 Build Video", use_container_width=True):
    if not PEXELS_API_KEY or PEXELS_API_KEY == "YOUR_LOCAL_KEY_HERE":
        st.error("Missing Pexels API Key! Add it to Streamlit Secrets.")
    elif not script:
        st.warning("Please enter a script first.")
    else:
        # Split by sentence endings
        sentences = [s.strip() for s in re.split(r'[.!?]', script) if len(s.strip()) > 5]
        
        with st.status("Building your video...", expanded=True) as status:
            clips = []
            for i, sent in enumerate(sentences):
                status.write(f"Generating Scene {i+1}...")
                clips.append(create_scene(sent, i, target_size))
            
            status.write("🧵 Final Rendering...")
            final_path = "final_output.mp4"
            final_video = concatenate_videoclips(clips, method="compose")
            final_video.write_videofile(final_path, fps=24, codec="libx264", audio_codec="aac")
            
            st.success("🎉 Video Complete!")
            st.video(final_path)
            
            with open(final_path, "rb") as f:
                st.download_button("📥 Download MP4", f, "ai_video.mp4", "video/mp4", use_container_width=True)
