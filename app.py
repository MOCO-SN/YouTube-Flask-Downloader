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

@app.route("/api/resolutions", methods=["POST"])
def resolutions():

    try:

        print("FORM DATA =", request.form)

        url = request.form.get("url")

        print("URL =", url)

        if not url:
            return jsonify({
                "success": False,
                "error": "URL not received"
            })

        yt = YouTube(url)

        resolutions = []

        for stream in yt.streams:

            if stream.resolution:
                resolutions.append(stream.resolution)

        resolutions = list(set(resolutions))

        resolutions.sort(
            key=lambda x: int(x.replace("p", "")),
            reverse=True
        )

        resolutions.insert(0, "highest")

        return jsonify({
            "success": True,
            "resolutions": resolutions
        })

    except Exception as e:

        print("ERROR =", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        })
@app.route("/api/download", methods=["POST"])
def download():

    try:

        url = request.form.get("url")
        file_type = request.form.get("file_type")

        if not url:
            return jsonify({
                "success": False,
                "error": "URL Required"
            })

        yt = YouTube(url)

        if file_type == "mp3":

            stream = (
                yt.streams
                .filter(only_audio=True)
                .first()
            )

            filename = stream.download(
                output_path=DOWNLOAD_FOLDER
            )

        else:

            stream = (
                yt.streams
                .filter(
                    progressive=True,
                    file_extension="mp4"
                )
                .order_by("resolution")
                .desc()
                .first()
            )

            filename = stream.download(
                output_path=DOWNLOAD_FOLDER
            )

        return jsonify({
            "success": True,
            "filename": os.path.basename(filename),
            "download_url":
                request.host_url +
                "downloads/" +
                os.path.basename(filename)
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