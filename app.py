from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory
)

from pytubefix import YouTube

import os
import re
import time
import threading
import subprocess
import imageio_ffmpeg

# ==========================================
# CONFIG
# ==========================================

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(
    os.getcwd(),
    "downloads"
)

os.makedirs(
    DOWNLOAD_FOLDER,
    exist_ok=True
)

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# ==========================================
# HELPERS
# ==========================================

def safe_filename(filename):

    return re.sub(
        r'[\\/*?:"<>|]',
        "",
        filename
    )


def delete_after_delay(path, delay=300):

    time.sleep(delay)

    try:

        if os.path.exists(path):
            os.remove(path)

    except Exception as e:

        print("Delete Error:", e)


def schedule_delete(path):

    threading.Thread(
        target=delete_after_delay,
        args=(path,),
        daemon=True
    ).start()


def get_best_audio_stream(yt):

    return (
        yt.streams
        .filter(only_audio=True)
        .order_by("abr")
        .desc()
        .first()
    )

# ==========================================
# STATUS
# ==========================================

@app.route("/api/status")
def status():

    return jsonify({
        "success": True,
        "message": "Server Online"
    })

# ==========================================
# VIDEO INFO
# ==========================================

@app.route("/api/video_info", methods=["POST"])
def video_info():

    try:

        url = request.form.get("url")

        if not url:

            return jsonify({
                "success": False,
                "error": "URL Required"
            })

        yt = YouTube(url)

        return jsonify({

            "success": True,

            "title": yt.title,

            "author": yt.author,

            "thumbnail": yt.thumbnail_url,

            "length": yt.length

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })

# ==========================================
# RESOLUTIONS
# ==========================================

@app.route("/api/resolutions", methods=["POST"])
def resolutions():

    try:

        url = request.form.get("url")

        if not url:

            return jsonify({
                "success": False,
                "error": "URL Required"
            })

        yt = YouTube(url)

        resolutions = set()

        for stream in yt.streams.filter(
                progressive=True,
                file_extension="mp4"):

            if stream.resolution:
                resolutions.add(
                    stream.resolution
                )

        for stream in yt.streams.filter(
                only_video=True,
                file_extension="mp4"):

            if stream.resolution:
                resolutions.add(
                    stream.resolution
                )

        resolution_list = sorted(
            list(resolutions),
            key=lambda x:
            int(x.replace("p", "")),
            reverse=True
        )

        resolution_list.insert(
            0,
            "highest"
        )

        return jsonify({

            "success": True,

            "resolutions":
                resolution_list

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })

# ==========================================
# DOWNLOAD
# ==========================================

@app.route("/api/download", methods=["POST"])
def download():

    try:

        url = request.form.get("url")

        file_type = request.form.get(
            "file_type",
            "mp4"
        )

        resolution = request.form.get(
            "resolution",
            "highest"
        )

        if not url:

            return jsonify({
                "success": False,
                "error": "URL Required"
            })

        yt = YouTube(url)

        title = safe_filename(
            yt.title
        )

        # ==================================
        # MP3
        # ==================================

        if file_type.lower() == "mp3":

            audio_stream = get_best_audio_stream(
                yt
            )

            if not audio_stream:

                return jsonify({
                    "success": False,
                    "error": "Audio not found"
                })

            temp_file = audio_stream.download(
                output_path=DOWNLOAD_FOLDER
            )

            final_file = os.path.join(
                DOWNLOAD_FOLDER,
                title + ".mp3"
            )

            if os.path.exists(final_file):
                os.remove(final_file)

            os.rename(
                temp_file,
                final_file
            )

            schedule_delete(
                final_file
            )

            return jsonify({

                "success": True,

                "filename":
                    os.path.basename(
                        final_file
                    ),

                "download_url":
                    request.host_url +
                    "downloads/" +
                    os.path.basename(
                        final_file
                    )
            })

        # ==================================
        # MP4
        # ==================================

        progressive_stream = None

        if resolution != "highest":

            progressive_stream = (

                yt.streams

                .filter(
                    progressive=True,
                    file_extension="mp4",
                    res=resolution
                )

                .first()
            )

        if progressive_stream:

            file_path = progressive_stream.download(
                output_path=DOWNLOAD_FOLDER,
                filename=f"{title}.mp4"
            )

            schedule_delete(
                file_path
            )

            return jsonify({

                "success": True,

                "filename":
                    os.path.basename(
                        file_path
                    ),

                "download_url":
                    request.host_url +
                    "downloads/" +
                    os.path.basename(
                        file_path
                    )
            })

        if resolution == "highest":

            video_stream = (

                yt.streams

                .filter(
                    only_video=True,
                    file_extension="mp4"
                )

                .order_by(
                    "resolution"
                )

                .desc()

                .first()
            )

        else:

            video_stream = (

                yt.streams

                .filter(
                    only_video=True,
                    file_extension="mp4",
                    res=resolution
                )

                .first()
            )

        audio_stream = get_best_audio_stream(
            yt
        )

        if not video_stream:

            return jsonify({
                "success": False,
                "error": "Video not found"
            })

        if not audio_stream:

            return jsonify({
                "success": False,
                "error": "Audio not found"
            })

        video_file = video_stream.download(
            output_path=DOWNLOAD_FOLDER,
            filename_prefix="video_"
        )

        audio_file = audio_stream.download(
            output_path=DOWNLOAD_FOLDER,
            filename_prefix="audio_"
        )

        final_file = os.path.join(
            DOWNLOAD_FOLDER,
            title + ".mp4"
        )

        command = [

            FFMPEG_PATH,

            "-i", video_file,

            "-i", audio_file,

            "-c:v", "copy",

            "-c:a", "aac",

            "-shortest",

            final_file,

            "-y"
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:

            return jsonify({
                "success": False,
                "error": result.stderr
            })

        if os.path.exists(video_file):
            os.remove(video_file)

        if os.path.exists(audio_file):
            os.remove(audio_file)

        schedule_delete(
            final_file
        )

        return jsonify({

            "success": True,

            "filename":
                os.path.basename(
                    final_file
                ),

            "download_url":
                request.host_url +
                "downloads/" +
                os.path.basename(
                    final_file
                )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })

# ==========================================
# FILE DOWNLOAD
# ==========================================

@app.route("/downloads/<path:filename>")
def file_download(filename):

    return send_from_directory(
        DOWNLOAD_FOLDER,
        filename,
        as_attachment=True
    )

# ==========================================
# START SERVER
# ==========================================

# if __name__ == "__main__":

#     app.run(
#         host="0.0.0.0",
#         port=5000,
#         debug=True
#     )