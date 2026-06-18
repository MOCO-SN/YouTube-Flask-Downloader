from flask import Flask, request, jsonify
import yt_dlp
import os
import uuid

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "message": "YT Downloader API Running"
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

        ydl_opts = {
            "quiet": True,
            "extract_flat": False
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        return jsonify({
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "author": info.get("uploader"),
            "length": info.get("duration")
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

        if not url:
            return jsonify({
                "success": False,
                "error": "URL Required"
            })

        unique_id = str(uuid.uuid4())

        if file_type == "mp3":

            filename = f"{unique_id}.mp3"

            ydl_opts = {
                "format": "bestaudio",
                "outtmpl": os.path.join(
                    DOWNLOAD_FOLDER,
                    filename
                )
            }

        else:

            filename = f"{unique_id}.mp4"

            ydl_opts = {
                "format": "best[ext=mp4]",
                "outtmpl": os.path.join(
                    DOWNLOAD_FOLDER,
                    filename
                )
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return jsonify({
            "success": True,
            "filename": filename,
            "download_url":
                request.host_url +
                "downloads/" +
                filename
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/downloads/<filename>")
def file_download(filename):

    from flask import send_from_directory

    return send_from_directory(
        DOWNLOAD_FOLDER,
        filename,
        as_attachment=True
    )


@app.route("/api/status")
def status():

    return jsonify({
        "success": True,
        "message": "Server Online"
    })


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )