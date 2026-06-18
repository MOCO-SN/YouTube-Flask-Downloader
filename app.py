from flask import Flask, request, jsonify, send_from_directory
from pytubefix import YouTube
import os
import re
import time
import threading
import subprocess
import imageio_ffmpeg

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


def safe_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)


def delete_file_later(path, delay=300):
    time.sleep(delay)

    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"Deleted: {path}")
    except Exception as e:
        print("Delete Error:", e)


def schedule_delete(path):
    threading.Thread(
        target=delete_file_later,
        args=(path,),
        daemon=True
    ).start()


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "message": "YT Downloader API Running"
    })


@app.route("/api/status")
def status():
    return jsonify({
        "success": True,
        "message": "Server Online"
    })


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
            "length": yt.length,
            "thumbnail": yt.thumbnail_url
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/api/resolutions", methods=["GET", "POST"])
def resolutions():

    try:

        url = request.form.get("url")

        yt = YouTube(url)

        resolutions = []

        for stream in yt.streams.filter(
                file_extension="mp4"):

            if stream.resolution:
                resolutions.append(
                    stream.resolution
                )

        resolutions = sorted(
            list(set(resolutions)),
            key=lambda x: int(x[:-1]),
            reverse=True
        )

        resolutions.insert(0, "highest")

        return jsonify({
            "success": True,
            "resolutions": resolutions
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })

@app.route("/api/download", methods=["POST"])
def download():

    try:

        url = request.form.get("url")
        file_type = request.form.get("file_type", "mp4")
        resolution = request.form.get("resolution", "highest")

        if not url:
            return jsonify({
                "success": False,
                "error": "URL Required"
            })

        yt = YouTube(url)

        title = safe_filename(yt.title)

        # MP3
        if file_type.lower() == "mp3":

            audio_stream = (
                yt.streams
                .filter(only_audio=True)
                .order_by("abr")
                .desc()
                .first()
            )

            if not audio_stream:
                return jsonify({
                    "success": False,
                    "error": "Audio stream unavailable"
                })

            temp_file = audio_stream.download(
                output_path=DOWNLOAD_FOLDER
            )

            final_file = os.path.join(
                DOWNLOAD_FOLDER,
                f"{title}.mp3"
            )

            if os.path.exists(final_file):
                os.remove(final_file)

            os.rename(temp_file, final_file)

            schedule_delete(final_file)

            return jsonify({
                "success": True,
                "filename": os.path.basename(final_file),
                "download_url":
                    request.host_url +
                    "downloads/" +
                    os.path.basename(final_file)
            })

        # MP4

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

            schedule_delete(file_path)

            return jsonify({
                "success": True,
                "filename": os.path.basename(file_path),
                "download_url":
                    request.host_url +
                    "downloads/" +
                    os.path.basename(file_path)
            })

        if resolution == "highest":

            video_stream = (
                yt.streams
                .filter(
                    only_video=True,
                    file_extension="mp4"
                )
                .order_by("resolution")
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

        audio_stream = (
            yt.streams
            .filter(only_audio=True)
            .order_by("abr")
            .desc()
            .first()
        )

        if not video_stream:
            return jsonify({
                "success": False,
                "error": "Video stream unavailable"
            })

        if not audio_stream:
            return jsonify({
                "success": False,
                "error": "Audio stream unavailable"
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
            f"{title}.mp4"
        )

        cmd = [
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
            cmd,
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

        schedule_delete(final_file)

        return jsonify({
            "success": True,
            "filename": os.path.basename(final_file),
            "download_url":
                request.host_url +
                "downloads/" +
                os.path.basename(final_file)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/downloads/<path:filename>")
def download_file(filename):

    return send_from_directory(
        DOWNLOAD_FOLDER,
        filename,
        as_attachment=True
    )


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )