import tkinter
from tkinter import ttk, filedialog
from pytubefix import YouTube, Playlist
import requests
import re
import os
import subprocess
import threading
from PIL import Image, ImageTk
from io import BytesIO
import datetime
import functools
import time
import sys


# ==================== Helper Functions ====================
def add_log_path(message, path):
    log_text.config(state=tkinter.NORMAL)

    start = log_text.index(tkinter.END)

    log_text.insert(
        tkinter.END,
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message} "
    )

    link_start = log_text.index(tkinter.END)
    log_text.insert(tkinter.END, path)
    link_end = log_text.index(tkinter.END)

    tag_name = f"path:{path}"
    log_text.tag_add(tag_name, link_start, link_end)
    log_text.tag_add("link", link_start, link_end)

    log_text.insert(tkinter.END, "\n")

    log_text.see(tkinter.END)
    log_text.config(state=tkinter.DISABLED)

def open_folder(path):
    if not os.path.exists(path):
        add_log(f"Folder not found: {path}")
        return

    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def is_valid_youtube_url(url):
    """Validate YouTube URL"""
    pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    return re.match(pattern, url) is not None


def merge_audio_video(video_path, audio_path, output_path):
    """Merge audio and video using ffmpeg"""
    command = [
        "ffmpeg",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-y",
        output_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_video_info(url):
    """Get video information from YouTube"""
    try:
        yt = YouTube(url)
        video_info = {
            "title": yt.title,
            "author": yt.author,
            "length": yt.length,
            "views": yt.views,
            "publish_date": str(yt.publish_date),
            "thumbnail_url": yt.thumbnail_url
        }
        return video_info, None
    except Exception as e:
        add_log(f"Error getting video info: {str(e)}")
        return None, str(e)


def get_available_streams(url):
    """Get available streams (MP4 resolutions and MP3 audio)"""
    try:
        yt = YouTube(url)
        
        # Get available MP4 resolutions
        mp4_streams = {}
        for stream in yt.streams.filter(progressive=True, file_extension="mp4"):
            if stream.resolution:
                mp4_streams[stream.resolution] = stream
        
        # Also get high-quality separate streams
        for stream in yt.streams.filter(file_extension="mp4", only_video=True):
            if stream.resolution and stream.resolution not in mp4_streams:
                mp4_streams[stream.resolution] = stream
        
        # MP3 is always available (audio extraction)
        mp3_available = True
        
        return mp4_streams, mp3_available, None
    except Exception as e:
        return {}, False, str(e)


def sanitize_filename(filename, video_id=None):
    """Sanitize filename to be safe for filesystem"""
    if not filename:
        filename = ""

    # remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')

    # remove control characters
    filename = "".join(c for c in filename if c.isprintable())

    # trim spaces
    filename = filename.strip()

    # ถ้าชื่อหายหมด → fallback
    if not filename:
        now = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
        if video_id:
            return f"video_{video_id}_{now}"
        else:
            return f"video_{now}"

    return filename

def sanitize_foldername(foldername, video_id=None):
    """Sanitize folder name (no timestamp fallback)"""
    if not foldername:
        foldername = ""

    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        foldername = foldername.replace(char, '')

    foldername = "".join(c for c in foldername if c.isprintable())
    foldername = foldername.strip()

    # fallback (ไม่มี timestamp)
    if not foldername:
        if video_id:
            return f"video_{video_id}"
        else:
            return "video"

    return foldername

def select_all():
    for row in row_widgets:
        row["selected"].set(True)

def is_playlist_url(url):
    """Check if URL is a YouTube playlist or mix"""
    return "list=" in url

def deselect_all():
    for row in row_widgets:
        row["selected"].set(False)
def queue_has_items():
    return len(video_queue) > 0

def get_playlist_videos(url):
    """Get all video URLs from playlist / mix / radio"""
    try:
        add_log("Initializing playlist...")
        video_urls = []

        # ---------- Try normal playlist ----------
        try:
            playlist = Playlist(url)

            add_log("Loading playlist videos...")
            for i, video in enumerate(playlist.videos):
                add_log(f"Reading playlist video {i+1}...")
                video_urls.append(video.watch_url)

        except Exception as e:
            add_log(f"Playlist load failed: {str(e)}")

        # ---------- Fallback: Mix / RD / Related ----------
        if not video_urls:
            add_log("Playlist empty, trying related videos fallback...")
            try:
                yt = YouTube(url)

                for i, video in enumerate(yt.related_videos):
                    add_log(f"Reading related video {i+1}...")
                    video_urls.append(video.watch_url)

            except Exception as e:
                add_log(f"Related fallback failed: {str(e)}")

        # ---------- Fallback: Single video ----------
        if not video_urls:
            add_log("No playlist found, using single video fallback")
            video_urls.append(url)

        add_log(f"Playlist loaded: {len(video_urls)} videos")
        return video_urls, None

    except Exception as e:
        add_log(f"Playlist error: {str(e)}")
        return [], str(e)
def remove_selected():
    global video_queue

    new_rows = []

    for row in row_widgets:
        if row["selected"].get():
            row["frame"].destroy()
            video_queue.remove(row["data"])
        else:
            new_rows.append(row)

    row_widgets.clear()
    row_widgets.extend(new_rows)

    add_log("Removed selected videos")
    update_queue_buttons()

# Global queue to store video information
video_queue = []


THUMBNAIL_SIZE_LABELS = [
    ("HD Image (1280x720)", "maxresdefault"),
    ("SD Image (640x480)", "sddefault"),
    ("Normal Image (480x360)", "hqdefault"),
    ("Normal Image (320x180)", "mqdefault"),
    ("Normal Image (120x90)", "default"),
]
THUMBNAIL_SIZE_MAP = {label: key for label, key in THUMBNAIL_SIZE_LABELS}


def download_thumbnail_custom(url, size_option, custom_path=None):
    """Download the video thumbnail with optional resizing and custom path."""
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return False, "Invalid YouTube URL"

        thumb_name = size_option or "maxresdefault"
        if thumb_name not in ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"]:
            thumb_name = "maxresdefault"

        image_url = f"https://img.youtube.com/vi/{video_id}/{thumb_name}.jpg"
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200 or len(response.content) < 1000:
            fallback_order = ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"]
            next_index = fallback_order.index(thumb_name) + 1 if thumb_name in fallback_order else 0
            found = False
            for fallback in fallback_order[next_index:]:
                image_url = f"https://img.youtube.com/vi/{video_id}/{fallback}.jpg"
                response = requests.get(image_url, timeout=15)
                if response.status_code == 200 and len(response.content) > 1000:
                    thumb_name = fallback
                    found = True
                    break
            if not found:
                return False, "Thumbnail not found"

        img = Image.open(BytesIO(response.content))
        img = img.convert("RGB")

        if custom_path:
            output_path = custom_path
            if not os.path.splitext(output_path)[1].lower() in [".jpg", ".jpeg", ".png"]:
                output_path = output_path + ".jpg"
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        else:
            yt = YouTube(url)
            video_id = extract_video_id(url)
            folder_name = sanitize_foldername(yt.title, video_id)
            output_dir = f"./downloads/{folder_name}"
            os.makedirs(output_dir, exist_ok=True)
            filename_base = sanitize_filename("thumbnail", video_id)
            output_path = os.path.join(output_dir, f"{filename_base}.jpg")

        extension = os.path.splitext(output_path)[1].lower()
        if extension == ".png":
            img.save(output_path, format="PNG")
        else:
            img.save(output_path, format="JPEG")
        return True, None
    except Exception as e:
        return False, str(e)


def download_video_custom(url, resolution, output_format="mp4", custom_path=None):
    """Download video in specified format and resolution with custom path"""
    try:
        yt = YouTube(url)
        
        # Determine output directory and filename
        if custom_path:
            output_dir = os.path.dirname(custom_path)
            filename_base = os.path.splitext(os.path.basename(custom_path))[0]
            extension = ".mp3" if output_format.lower() == "mp3" else ".mp4"
            final_filename = filename_base + extension
        else:
            video_id = extract_video_id(url)
            folder_name = sanitize_foldername(yt.title, video_id)
            output_dir = f"./downloads/{folder_name}"
            filename_base = sanitize_filename(yt.title, video_id)
            extension = ".mp3" if output_format.lower() == "mp3" else ".mp4"
            final_filename = filename_base + extension
        
        os.makedirs(output_dir, exist_ok=True)
        
        add_log(f"Downloading: {yt.title}")
        add_log(f"Format: {output_format.upper()}, Resolution: {resolution}")
        
        if output_format.lower() == "mp3":
            # Download only audio
            audio_stream = yt.streams.filter(only_audio=True).first()
            if audio_stream:
                add_log("Downloading audio...")
                temp_audio_file = os.path.join(output_dir, "temp_audio.mp4")
                audio_stream.download(output_path=output_dir, filename="temp_audio.mp4")
                
                # Convert to MP3 using ffmpeg
                final_path = os.path.join(output_dir, final_filename)
                command = [
                    "ffmpeg",
                    "-i", temp_audio_file,
                    "-vn",  # No video
                    "-ab", "128k",  # Audio bitrate
                    "-ar", "44100",  # Audio sample rate
                    "-y",  # Overwrite
                    final_path
                ]
                
                try:
                    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    os.remove(temp_audio_file)  # Remove temp file
                    add_log_path("Download completed → ", output_dir)
                    return True, None
                except subprocess.CalledProcessError as e:
                    # If ffmpeg fails, just rename the file
                    if custom_path:
                        os.rename(temp_audio_file, final_path)
                    add_log("Download completed (without conversion)!")
                    return True, None
            else:
                return False, "Audio stream not found"
        else:
            # Download video
            stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution=resolution).first()
            
            if stream:
                add_log("Downloading video...")
                final_path = os.path.join(output_dir, final_filename)
                stream.download(output_path=output_dir, filename=final_filename)
                add_log_path("Download completed → ", output_dir)
                return True, None
            else:
                # Try separate video and audio
                video_stream = yt.streams.filter(file_extension='mp4', resolution=resolution, only_video=True).first()
                audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
                
                if not video_stream or not audio_stream:
                    return False, "Video/audio stream not found"
                
                add_log("Downloading video...")
                video_file = video_stream.download(output_path=output_dir, filename="video.mp4")
                
                add_log("Downloading audio...")
                audio_file = audio_stream.download(output_path=output_dir, filename="audio.mp4")
                
                final_path = os.path.join(output_dir, final_filename)
                
                add_log("Merging with ffmpeg...")
                merge_audio_video(video_file, audio_file, final_path)
                
                os.remove(video_file)
                os.remove(audio_file)
                
                add_log_path("Download completed → ", output_dir)
                return True, None
    except Exception as e:
        return False, str(e)

def get_selected_videos():
    selected = []

    for row in row_widgets:
        if row["selected"].get():
            selected.append(row["data"])

    return selected
# ==================== GUI Setup ====================

app = tkinter.Tk()
app.title("Youtube Downloader")
app.geometry("1280x800")
app.resizable(False, False)

# Main frame
main_frame = tkinter.Frame(app)
main_frame.pack(fill=tkinter.BOTH, expand=True)

# ==================== Header ====================
header_frame = tkinter.Frame(main_frame, bg="#2c3e50")
header_frame.pack(fill=tkinter.X, pady=(0, 20))

# ==================== URL Input Section ====================
url_frame = tkinter.Frame(main_frame)
url_frame.pack(pady=10)

entryLabel = tkinter.Label(url_frame, text="Enter the URL of the video you want to download", font=("Arial", 12))
entryLabel.pack(pady=5)

entryURL = tkinter.Entry(url_frame, width=60, font=("Arial", 11))
entryURL.pack(pady=5)

ControlFrame = tkinter.Frame(main_frame)
ControlFrame.pack(pady=10)

clearURLBtn = tkinter.Button(ControlFrame, text="Clear URL", font=("Arial", 11), width=15)
clearURLBtn.pack(side=tkinter.LEFT, padx=5)

pasteURLBtn = tkinter.Button(ControlFrame, text="Paste URL", font=("Arial", 11), width=15)
pasteURLBtn.pack(side=tkinter.LEFT, padx=5)

processURLBtn = tkinter.Button(ControlFrame, text="Process URL", font=("Arial", 11), width=15, bg="#27ae60", fg="white")
processURLBtn.pack(side=tkinter.LEFT, padx=5)

def clear_queue():
    global video_queue

    video_queue.clear()
    row_widgets.clear()
    
    for w in scrollable_frame.winfo_children():
        w.destroy()

    add_log("Queue cleared")
    
# ==================== Queue Display Area ====================
queue_frame = tkinter.LabelFrame(main_frame, text="Download Queue", font=("Arial", 12, "bold"), padx=10, pady=10)
queue_frame.pack(pady=20, padx=20, fill=tkinter.BOTH, expand=True)

queue_container = tkinter.Frame(queue_frame)
queue_container.pack(fill="both", expand=True)

queue_left = tkinter.Frame(queue_container)
queue_left.pack(side="left", fill="both", expand=True)
queue_left.grid_rowconfigure(0, weight=1)
queue_left.grid_columnconfigure(0, weight=1)
queue_running = False

queue_right = tkinter.LabelFrame(
    queue_container,
    text="Queue Management",
    font=("Arial", 10, "bold"),
    padx=10,
    pady=10,
    width=260
)

queue_right.pack(side="right", fill="y", padx=10, pady=5)

queue_mp4 = tkinter.BooleanVar(value=True)
queue_mp3 = tkinter.BooleanVar(value=False)
queue_thumb = tkinter.BooleanVar(value=False)

tkinter.Label(queue_right, text="Format").pack(anchor="w")

mp4_check = tkinter.Checkbutton(
    queue_right, text="MP4", variable=queue_mp4
)
mp4_check.pack(anchor="w")

queue_mp4_quality = ttk.Combobox(queue_right, state="disabled")
queue_mp4_quality.pack(fill="x", pady=2)
queue_mp4_quality["values"] = [
    "MP4 - 1080p",
    "MP4 - 720p",
    "MP4 - 480p",
    "MP4 - 360p"
]
queue_mp4_quality.current(1)


mp3_check = tkinter.Checkbutton(
    queue_right, text="MP3", variable=queue_mp3
)
mp3_check.pack(anchor="w")

queue_mp3_quality = ttk.Combobox(queue_right, state="disabled")
queue_mp3_quality.pack(fill="x", pady=2)
queue_mp3_quality["values"] = ["MP3 - 128K"]
queue_mp3_quality.current(0)


thumb_check = tkinter.Checkbutton(
    queue_right, text="Thumbnail", variable=queue_thumb
)
thumb_check.pack(anchor="w")

queue_thumb_quality = ttk.Combobox(queue_right, state="disabled")
queue_thumb_quality.pack(fill="x", pady=2)
queue_thumb_quality["values"] = [
    label for label, _ in THUMBNAIL_SIZE_LABELS
]
queue_thumb_quality.current(0)



# Create scrollable canvas for queue with both scrollbars
canvas = tkinter.Canvas(queue_left, bg="#f0f0f0")
v_scrollbar = tkinter.Scrollbar(queue_left, orient="vertical", command=canvas.yview)
h_scrollbar = tkinter.Scrollbar(queue_left, orient="horizontal", command=canvas.xview)
scrollable_frame = tkinter.Frame(canvas, bg="#f0f0f0")

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

# Pack canvas and scrollbars using grid for proper layout
canvas.grid(row=0, column=0, sticky="nsew")
v_scrollbar.grid(row=0, column=1, sticky="ns")
h_scrollbar.grid(row=1, column=0, sticky="ew")

queue_frame.grid_rowconfigure(0, weight=1)
queue_frame.grid_columnconfigure(0, weight=1)

def update_queue_checkbox():

    queue_mp4_quality.config(
        state="readonly" if queue_mp4.get() else "disabled"
    )

    queue_mp3_quality.config(
        state="readonly" if queue_mp3.get() else "disabled"
    )

    queue_thumb_quality.config(
        state="readonly" if queue_thumb.get() else "disabled"
    )

queue_mp4.trace("w", lambda *a: update_queue_checkbox())
queue_mp3.trace("w", lambda *a: update_queue_checkbox())
queue_thumb.trace("w", lambda *a: update_queue_checkbox())

update_queue_checkbox()


def queue_quick_download_selected():
    global queue_running

    if queue_running:
        add_log("Queue already running")
        return

    selected_videos = get_selected_videos()

    if not selected_videos:
        add_log("No videos selected")
        return

    def worker():
        global queue_running
        queue_running = True

        add_log(f"Queue started ({len(selected_videos)} selected)")

        for i, video in enumerate(selected_videos):

            add_log(f"[{i+1}/{len(selected_videos)}] {video['title']}")

            vid = extract_video_id(video["url"])
            name = sanitize_filename(video["title"], vid)

            folder = os.path.join("downloads", name)
            os.makedirs(folder, exist_ok=True)

            # ---------- MP4 ----------
            if queue_mp4.get():

                quality = queue_mp4_quality.get()
                if " - " in quality:
                    quality = quality.split(" - ")[1]
                else:
                    quality = "720p"

                path = os.path.join(folder, name + ".mp4")

                download_video_custom(
                    video["url"],
                    quality,
                    "mp4",
                    path
                )

            # ---------- MP3 ----------
            if queue_mp3.get():

                quality = queue_mp3_quality.get().split(" - ")[1]

                path = os.path.join(folder, name + ".mp3")

                download_video_custom(
                    video["url"],
                    quality,
                    "mp3",
                    path
                )

            # ---------- Thumbnail ----------
            if queue_thumb.get():

                quality = THUMBNAIL_SIZE_MAP[
                    queue_thumb_quality.get()
                ]

                path = os.path.join(folder, name + ".png")

                download_thumbnail_custom(
                    video["url"],
                    quality,
                    path
                )

        add_log("Selected queue finished")
        queue_running = False

    threading.Thread(target=worker, daemon=True).start()
    
def queue_download_selected_as():

    global queue_running

    if queue_running:
        add_log("Queue already running")
        return

    selected_videos = get_selected_videos()

    if not selected_videos:
        add_log("No videos selected")
        return

    base_folder = filedialog.askdirectory()

    if not base_folder:
        return

    def worker():

        global queue_running
        queue_running = True

        add_log(f"Queue started ({len(selected_videos)} selected)")

        for i, video in enumerate(selected_videos):

            add_log(f"[{i+1}/{len(selected_videos)}] {video['title']}")

            vid = extract_video_id(video["url"])
            name = sanitize_filename(video["title"], vid)

            folder = os.path.join(base_folder, name)
            os.makedirs(folder, exist_ok=True)

            # ---------- MP4 ----------
            if queue_mp4.get():

                quality = queue_mp4_quality.get()
                if " - " in quality:
                    quality = quality.split(" - ")[1]
                else:
                    quality = "720p"

                path = os.path.join(folder, name + ".mp4")

                download_video_custom(
                    video["url"],
                    quality,
                    "mp4",
                    path
                )

            # ---------- MP3 ----------
            if queue_mp3.get():

                quality = queue_mp3_quality.get().split(" - ")[1]

                path = os.path.join(folder, name + ".mp3")

                download_video_custom(
                    video["url"],
                    quality,
                    "mp3",
                    path
                )

            # ---------- Thumbnail ----------
            if queue_thumb.get():

                quality = THUMBNAIL_SIZE_MAP[
                    queue_thumb_quality.get()
                ]

                path = os.path.join(folder, name + ".png")

                download_thumbnail_custom(
                    video["url"],
                    quality,
                    path
                )

        add_log("Selected queue finished")
        queue_running = False

    threading.Thread(target=worker, daemon=True).start()   
    
def queue_quick_download():
    global queue_running
    if queue_running:
        add_log("Queue already running")
        return
    

    if not video_queue:
        add_log("Queue empty")
        return

    def worker():
        global queue_running
        queue_running = True
        
        add_log("Queue started")

        for i, video in enumerate(video_queue):

            add_log(f"[{i+1}/{len(video_queue)}] {video['title']}")

            vid = extract_video_id(video["url"])
            name = sanitize_filename(video["title"], vid)

            folder = os.path.join("downloads", name)
            os.makedirs(folder, exist_ok=True)

            # MP4
            if queue_mp4.get():

                quality = queue_mp4_quality.get()
                if " - " in quality:
                    quality = quality.split(" - ")[1]
                else:
                    quality = "720p"
                
                path = os.path.join(folder, name + ".mp4")

                add_log("Downloading MP4...")
                download_video_custom(
                    video["url"],
                    quality,
                    "mp4",
                    path
                )

            # MP3
            if queue_mp3.get():

                quality = queue_mp3_quality.get().split(" - ")[1]

                path = os.path.join(folder, name + ".mp3")

                add_log("Downloading MP3...")
                download_video_custom(
                    video["url"],
                    quality,
                    "mp3",
                    path
                )

            # Thumbnail
            if queue_thumb.get():

                quality = THUMBNAIL_SIZE_MAP[
                    queue_thumb_quality.get()
                ]

                path = os.path.join(folder, name + ".png")

                add_log("Downloading Thumbnail...")
                download_thumbnail_custom(
                    video["url"],
                    quality,
                    path
                )

        add_log("Queue finished")
        queue_running = False

    threading.Thread(target=worker, daemon=True).start()

def queue_download_as():

    global queue_running

    if queue_running:
        add_log("Queue already running")
        return

    base_folder = filedialog.askdirectory()

    if not base_folder:
        return

    def worker():

        global queue_running
        queue_running = True

        add_log("Queue started")

        for i, video in enumerate(video_queue):

            add_log(f"[{i+1}/{len(video_queue)}] {video['title']}")

            vid = extract_video_id(video["url"])
            name = sanitize_filename(video["title"], vid)

            folder = os.path.join(base_folder, name)
            os.makedirs(folder, exist_ok=True)

            # ---------- MP4 ----------
            if queue_mp4.get():

                quality = queue_mp4_quality.get()
                if " - " in quality:
                    quality = quality.split(" - ")[1]
                else:
                    quality = "720p"
                                    
                path = os.path.join(folder, name + ".mp4")

                add_log("Downloading MP4...")
                download_video_custom(
                    video["url"],
                    quality,
                    "mp4",
                    path
                )

            # ---------- MP3 ----------
            if queue_mp3.get():

                quality = queue_mp3_quality.get().split(" - ")[1]
                path = os.path.join(folder, name + ".mp3")

                add_log("Downloading MP3...")
                download_video_custom(
                    video["url"],
                    quality,
                    "mp3",
                    path
                )

            # ---------- Thumbnail ----------
            if queue_thumb.get():

                quality = THUMBNAIL_SIZE_MAP[
                    queue_thumb_quality.get()
                ]

                path = os.path.join(folder, name + ".png")

                add_log("Downloading Thumbnail...")
                download_thumbnail_custom(
                    video["url"],
                    quality,
                    path
                )

        add_log("Queue finished")
        queue_running = False

    threading.Thread(target=worker, daemon=True).start()

quick_btn = tkinter.Button(
    queue_right,
    text="Quick Download All",
    bg="#3498db",
    fg="white",
    command=queue_quick_download
)
quick_btn.pack(fill="x", pady=(15,3))


download_as_btn = tkinter.Button(
    queue_right,
    text="Download All As",
    bg="#f39c12",
    fg="white",
    command=queue_download_as
)
download_as_btn.pack(fill="x", pady=3)

selected_quick_btn = tkinter.Button(
    queue_right,
    text="Quick Download Selected",
    bg="#2ecc71",
    fg="white",
    command=queue_quick_download_selected
)
selected_quick_btn.pack(fill="x", pady=3)


selected_download_btn = tkinter.Button(
    queue_right,
    text="Download Selected As",
    bg="#9b59b6",
    fg="white",
    command=queue_download_selected_as
)
selected_download_btn.pack(fill="x", pady=3)


tkinter.Button(
    queue_right,
    text="Clear Queue",
    bg="#e74c3c",
    fg="white",
    command=clear_queue
).pack(fill="x", pady=(15,3))

tkinter.Button(
    queue_right,
    text="Select All",
    command=select_all
).pack(fill="x")

tkinter.Button(
    queue_right,
    text="De-select All",
    command=deselect_all
).pack(fill="x")

# Bind mousewheel to canvas
def _on_mousewheel(event):
    canvas.yview_scroll(int(-1*(event.delta/120)), "units")

canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

# ==================== Queue Management ====================

def create_row_callback(video_info, row_index):
    """Callback function to create video row in main thread"""
    create_video_row(video_info, row_index)


def add_video_to_queue(video_info):
    """Add a video to the download queue and create UI row"""
    global video_queue
    
    new_id = extract_video_id(video_info.get("url"))
    
    # prevent duplicates
    for existing_video in video_queue:
        existing_id = extract_video_id(existing_video.get("url"))
        if existing_id == new_id:
            add_log(f"Video already in queue: {video_info['title']}")
            return
    
    video_queue.append(video_info)
    
    app.after(
        0,
        functools.partial(
            create_row_callback,
            video_info,
            len(video_queue) - 1
        )
    )
    update_queue_buttons()
row_widgets = []


def update_queue_buttons():
    state = "normal" if video_queue else "disabled"

    quick_btn.config(state=state)
    download_as_btn.config(state=state)

def create_video_row(video_info, row_index):
    """Create a row in the queue for a video"""
    def load_mp4_quality():
        def worker():
            mp4_streams, _, _ = get_available_streams(video_info["url"])

            if mp4_streams:
                # sort resolution สูง -> ต่ำ
                resolutions = sorted(
                    mp4_streams.keys(),
                    key=lambda x: int(x.replace("p", "")),
                    reverse=True
                )

                options = [f"MP4 - {r}" for r in resolutions]
            else:
                options = ["MP4 - 720p"]

            def apply():
                mp4_quality["values"] = options
                if options:
                    mp4_quality.current(0)

            app.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()
        
    """Create a row in the queue for a video"""
    row_frame = tkinter.Frame(scrollable_frame, relief="ridge", bd=1)
    row_frame.pack(fill="x", pady=2, padx=5)
    
    row_frame.grid_columnconfigure(1, weight=1)
    row_frame.grid_columnconfigure(2, weight=1)
    row_frame.grid_columnconfigure(3, weight=0)
    row_frame.grid_columnconfigure(4, weight=0)
    
    select_var = tkinter.BooleanVar(value=False)
    select_check = tkinter.Checkbutton(row_frame,variable=select_var)
    select_check.grid(row=0, column=0, sticky="nw")
    
    
    # Column 1: Thumbnail (120x90)
    thumb_frame = tkinter.Frame(row_frame, width=120, height=90)
    thumb_frame.grid(row=0, column=1, padx=5, pady=5)
    thumb_frame.grid_propagate(False)
    
    thumb_label = tkinter.Label(thumb_frame, bg="gray")
    thumb_label.pack(fill=tkinter.BOTH, expand=True)
    
    def load_thumbnail():
        try:
            video_id = extract_video_id(video_info["url"])

            fallback_order = [
                "maxresdefault",
                "sddefault",
                "hqdefault",
                "mqdefault",
                "default"
            ]

            for size in fallback_order:
                url = f"https://img.youtube.com/vi/{video_id}/{size}.jpg"
                r = requests.get(url, timeout=10)

                if r.status_code == 200 and len(r.content) > 1000:
                    img = Image.open(BytesIO(r.content))
                    img = img.resize((120, 90), Image.Resampling.LANCZOS)

                    photo = ImageTk.PhotoImage(img)

                    def apply():
                        thumb_label.config(image=photo)
                        thumb_label.image = photo

                    app.after(0, apply)
                    return

        except Exception as e:
            add_log(f"Thumbnail load error: {e}")

    threading.Thread(target=load_thumbnail, daemon=True).start()
    
    # Column 2: Clip Name
    title_label = tkinter.Label(
        row_frame,
        text=video_info["title"],
        font=("Arial", 10, "bold"),
        wraplength=300,
        justify=tkinter.LEFT,
        anchor="w"
    )
    title_label.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
    
    # Column 3: Details
    details_text = (
        f"Author: {video_info['author']}\n"
        f"Length: {video_info['length'] // 60} min\n"
        f"Views: {video_info['views']:,}\n"
        f"Date: {video_info['publish_date']}"
    )
    
    details_label = tkinter.Label(
        row_frame,
        text=details_text,
        font=("Arial", 9),
        justify=tkinter.LEFT,
        anchor="center"
    )
    details_label.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
    row_frame.grid_rowconfigure(0, weight=1)
    
    # Column 4: Options
    options_frame = tkinter.Frame(row_frame)
    options_frame.grid(row=0, column=4, padx=5, pady=5, sticky="nsew")
    
    row_mp4 = tkinter.BooleanVar(value=False)
    row_mp3 = tkinter.BooleanVar(value=False)
    row_thumb = tkinter.BooleanVar(value=False)
    
    tkinter.Checkbutton(options_frame, text="MP4", variable=row_mp4).pack(anchor="w")
    mp4_quality = ttk.Combobox(options_frame, state="disabled", width=18)
    mp4_quality.pack()
    
    load_mp4_quality()
    
    tkinter.Checkbutton(options_frame, text="MP3", variable=row_mp3).pack(anchor="w")
    mp3_quality = ttk.Combobox(options_frame, state="disabled", width=18)
    mp3_quality.pack()
    mp3_quality["values"] = ["MP3 - 128K"]
    mp3_quality.current(0)
    
    tkinter.Checkbutton(options_frame, text="Thumbnail", variable=row_thumb).pack(anchor="w")
    thumb_quality = ttk.Combobox(options_frame, state="disabled", width=18)
    thumb_quality.pack()
    thumb_quality["values"] = [label for label,_ in THUMBNAIL_SIZE_LABELS]
    thumb_quality.current(0)
    
    def update_row():

        mp4_quality.config(
            state="readonly" if row_mp4.get() else "disabled"
        )

        mp3_quality.config(
            state="readonly" if row_mp3.get() else "disabled"
        )

        thumb_quality.config(
            state="readonly" if row_thumb.get() else "disabled"
        )

    row_mp4.trace("w", lambda *a: update_row())
    row_mp3.trace("w", lambda *a: update_row())
    row_thumb.trace("w", lambda *a: update_row())

    update_row()
    
    # Column 5: Buttons
    row_frame.grid_columnconfigure(5, weight=0)
    buttons_frame = tkinter.Frame(row_frame)
    buttons_frame.grid(row=0, column=5, padx=5, pady=5, sticky="ns")
    
    def quick_download():

        def worker():

            vid = extract_video_id(video_info["url"])
            name = sanitize_filename(video_info["title"], vid)

            folder = os.path.join("downloads", name)
            os.makedirs(folder, exist_ok=True)

            if row_mp4.get():

                quality = mp4_quality.get()
                if not quality:
                    quality = "MP4 - 720p"
                if " - " in quality:
                    quality = quality.split(" - ")[1]
                else:
                    quality = "720p"
                    
                path = os.path.join(folder, name + ".mp4")

                download_video_custom(
                    video_info["url"],
                    quality,
                    "mp4",
                    path
                )

            if row_mp3.get():

                quality = mp3_quality.get().split(" - ")[1]
                path = os.path.join(folder, name + ".mp3")

                download_video_custom(
                    video_info["url"],
                    quality,
                    "mp3",
                    path
                )

            if row_thumb.get():

                quality = THUMBNAIL_SIZE_MAP[
                    thumb_quality.get()
                ]

                path = os.path.join(folder, name + ".png")

                download_thumbnail_custom(
                    video_info["url"],
                    quality,
                    path
                )

        threading.Thread(target=worker, daemon=True).start()
    
    def download_as():

        folder = filedialog.askdirectory()
        if not folder:
            return

        def worker():

            vid = extract_video_id(video_info["url"])
            name = sanitize_filename(video_info["title"], vid)

            folder_path = os.path.join(folder, name)
            os.makedirs(folder_path, exist_ok=True)

            # MP4
            if row_mp4.get():

                quality = mp4_quality.get()
                if not quality:
                    quality = "MP4 - 720p"
                if " - " in quality:
                    quality = quality.split(" - ")[1]
                else:
                    quality = "720p"
                
                path = os.path.join(folder_path, name + ".mp4")

                download_video_custom(
                    video_info["url"],
                    quality,
                    "mp4",
                    path
                )

            # MP3
            if row_mp3.get():

                quality = mp3_quality.get().split(" - ")[1]

                path = os.path.join(folder_path, name + ".mp3")

                download_video_custom(
                    video_info["url"],
                    quality,
                    "mp3",
                    path
                )

            # Thumbnail
            if row_thumb.get():

                quality = THUMBNAIL_SIZE_MAP[
                    thumb_quality.get()
                ]

                path = os.path.join(folder_path, name + ".png")

                download_thumbnail_custom(
                    video_info["url"],
                    quality,
                    path
                )

        threading.Thread(target=worker, daemon=True).start()
        
    def delete_this_row():
        row_frame.destroy()
        video_queue.remove(video_info)

        for r in row_widgets[:]:
            if r["frame"] == row_frame:
                row_widgets.remove(r)

        update_queue_buttons()

    tkinter.Button(
        buttons_frame,
        text="🗑",
        fg="red",
        command=delete_this_row
    ).pack()
    
    row_quick_btn = tkinter.Button(
        buttons_frame,
        text="Quick Download",
        bg="#3498db",
        fg="white",
        command=quick_download
    )
    row_quick_btn.pack(pady=2)

    row_download_btn = tkinter.Button(
        buttons_frame,
        text="Download As",
        bg="#e74c3c",
        fg="white",
        command=download_as
    )
    row_download_btn.pack(pady=2)
    
    row_widgets.append({
    "frame": row_frame,
    "selected": select_var,
    "data": video_info})
    
    update_row()

# ==================== LOG Section ====================
log_frame = tkinter.Frame(main_frame)
log_frame.pack(padx=20, pady=10, fill=tkinter.BOTH, expand=True)

log_label = tkinter.Label(log_frame, text="Log Output:", font=("Arial", 11, "bold"))
log_label.pack(anchor="w")

# แบ่งซ้าย / ขวา
log_container = tkinter.Frame(log_frame)
log_container.pack(fill=tkinter.BOTH, expand=True)

# ---------------- LEFT : LOG TEXT ----------------
log_left = tkinter.Frame(log_container)
log_left.pack(side="left", fill=tkinter.BOTH, expand=True)

log_text_frame = tkinter.Frame(log_left)
log_text_frame.pack(fill=tkinter.BOTH, expand=True)


log_text = tkinter.Text(
    log_text_frame,
    font=("Consolas", 9),
    bg="black",
    fg="yellow",
    wrap=tkinter.NONE,
    state=tkinter.DISABLED
)
log_text.tag_config("link", foreground="cyan", underline=True)
def on_log_click(event):
    index = log_text.index(f"@{event.x},{event.y}")
    tags = log_text.tag_names(index)

    for tag in tags:
        if tag.startswith("path:"):
            path = tag.replace("path:", "")
            open_folder(path)
            break

log_text.bind("<Button-1>", on_log_click)
log_text.tag_bind("link", "<Enter>", lambda e: log_text.config(cursor="hand2"))
log_text.tag_bind("link", "<Leave>", lambda e: log_text.config(cursor=""))

# scrollbars
log_v_scroll = tkinter.Scrollbar(
    log_text_frame,
    orient=tkinter.VERTICAL,
    command=log_text.yview
)

log_h_scroll = tkinter.Scrollbar(
    log_text_frame,
    orient=tkinter.HORIZONTAL,
    command=log_text.xview
)

log_text.configure(
    yscrollcommand=log_v_scroll.set,
    xscrollcommand=log_h_scroll.set
)

log_text.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)
log_v_scroll.pack(side=tkinter.RIGHT, fill=tkinter.Y)

# ---------------- RIGHT : BUTTON PANEL ----------------
log_right = tkinter.LabelFrame(
    log_container,
    text="Log Controls",
    font=("Arial", 10, "bold"),
    width=300
)

log_right.pack(side="right", fill="y", padx=(10,0))
log_right.pack_propagate(False)

clear_log_btn = tkinter.Button(
    log_right,
    text="Clear Log",
    width=18
)
clear_log_btn.pack(side=tkinter.LEFT, padx=5, pady=5)

copy_log_btn = tkinter.Button(
    log_right,
    text="Copy Log",
    width=18
)
copy_log_btn.pack(side=tkinter.LEFT, padx=5, pady=5)


# ==================== Callback Functions ====================

def add_log(message):
    """Add message to log"""
    log_text.config(state=tkinter.NORMAL)
    log_text.insert(tkinter.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}\n")
    log_text.see(tkinter.END)  # Auto scroll to bottom
    log_text.config(state=tkinter.DISABLED)


def clear_log():
    """Clear all log messages"""
    log_text.config(state=tkinter.NORMAL)
    log_text.delete(1.0, tkinter.END)
    log_text.config(state=tkinter.DISABLED)
    add_log("Log cleared")


def copy_log():
    """Copy log content to clipboard"""
    log_content = log_text.get(1.0, tkinter.END).strip()
    if log_content:
        app.clipboard_clear()
        app.clipboard_append(log_content)
        add_log("Log copied to clipboard")
    else:
        add_log("No log content to copy")


def clear_url():
    """Clear URL entry"""
    entryURL.delete(0, tkinter.END)
    add_log("URL cleared")


def paste_url():
    """Paste URL from clipboard"""
    try:
        url = app.clipboard_get()
        entryURL.delete(0, tkinter.END)
        entryURL.insert(0, url)
        add_log("URL pasted")
    except Exception as e:
        add_log(f"Error pasting URL: {str(e)}")


def process_url():
    """Process URL and add to queue"""
    url = entryURL.get().strip()
    
    if not url:
        add_log("Error: Please enter a URL")
        return
    
    if not is_valid_youtube_url(url):
        add_log("Error: Invalid YouTube URL")
        return
    
    add_log("Processing URL...")
    
    # Check if it's a playlist
    if is_playlist_url(url):
        add_log("Detected playlist, fetching all videos...")
        
        def fetch_playlist():
            video_urls, error = get_playlist_videos(url)
            
            if error:
                add_log(f"Error fetching playlist: {error}")
                return
            
            add_log(f"Found {len(video_urls)} videos in playlist")
            
            for i, video_url in enumerate(video_urls):
                time.sleep(0.1)
                add_log(f"Processing video {i+1}/{len(video_urls)}...")
                
                info, error = get_video_info(video_url)
                if error:
                    add_log(f"Error getting info for video {i+1}: {error}")
                    continue
                
                # Add URL to info
                info["url"] = video_url
                add_video_to_queue(info)
            
            add_log("Playlist processing completed")
        
        thread = threading.Thread(target=fetch_playlist, daemon=True)
        thread.start()
    else:
        # Single video
        def fetch_single():
            info, error = get_video_info(url)
            
            if error:
                add_log(f"Error: {error}")
                return
            
            # Add URL to info
            info["url"] = url
            add_log(f"Adding to queue: {info['title']}")
            add_video_to_queue(info)
        
        thread = threading.Thread(target=fetch_single, daemon=True)
        thread.start()


# ==================== Bind Buttons ====================
clearURLBtn.config(command=clear_url)
pasteURLBtn.config(command=paste_url)
processURLBtn.config(command=process_url)
clear_log_btn.config(command=clear_log)
copy_log_btn.config(command=copy_log)


app.mainloop()