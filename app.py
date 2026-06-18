from flask import Flask, render_template, request, send_from_directory, jsonify
from pytubefix import YouTube
import os
import threading
import time
import subprocess
import imageio_ffmpeg
import re

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

app.config["DOWNLOAD_FOLDER"] = DOWNLOAD_FOLDER

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


def safe_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)


def delete_file_async(path):
    time.sleep(10)

    try:
        if os.path.exists(path):
            os.remove(path)
            print("Deleted:", path)
    except Exception as e:
        print("Delete Error:", e)


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        url = request.form.get("url")
        file_type = request.form.get("file_type")
        resolution = request.form.get("resolution", "highest")

        if not url:
            return "Please enter a YouTube URL"

        try:

            yt = YouTube(url)

            title = safe_filename(yt.title)

            if file_type == "mp3":

                audio = (
                    yt.streams
                    .filter(only_audio=True)
                    .order_by("abr")
                    .desc()
                    .first()
                )

                if not audio:
                    return "Audio stream not found"

                downloaded = audio.download(
                    output_path=DOWNLOAD_FOLDER
                )

                mp3_file = os.path.join(
                    DOWNLOAD_FOLDER,
                    f"{title}.mp3"
                )

                if os.path.exists(mp3_file):
                    os.remove(mp3_file)

                os.rename(downloaded, mp3_file)

                response = send_from_directory(
                    DOWNLOAD_FOLDER,
                    os.path.basename(mp3_file),
                    as_attachment=True
                )

                threading.Thread(
                    target=delete_file_async,
                    args=(mp3_file,),
                    daemon=True
                ).start()

                return response

            elif file_type == "mp4":

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

                    response = send_from_directory(
                        DOWNLOAD_FOLDER,
                        os.path.basename(file_path),
                        as_attachment=True
                    )

                    threading.Thread(
                        target=delete_file_async,
                        args=(file_path,),
                        daemon=True
                    ).start()

                    return response

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
                        .order_by("resolution")
                        .desc()
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
                    return "Requested resolution unavailable"

                if not audio_stream:
                    return "Audio stream unavailable"

                video_path = video_stream.download(
                    output_path=DOWNLOAD_FOLDER,
                    filename_prefix="video_"
                )

                audio_path = audio_stream.download(
                    output_path=DOWNLOAD_FOLDER,
                    filename_prefix="audio_"
                )

                final_file = os.path.join(
                    DOWNLOAD_FOLDER,
                    f"{title}.mp4"
                )

                command = [
                    FFMPEG_PATH,
                    "-i", video_path,
                    "-i", audio_path,
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
                    return f"Merge Error: {result.stderr}"

                if os.path.exists(video_path):
                    os.remove(video_path)

                if os.path.exists(audio_path):
                    os.remove(audio_path)

                response = send_from_directory(
                    DOWNLOAD_FOLDER,
                    os.path.basename(final_file),
                    as_attachment=True
                )

                threading.Thread(
                    target=delete_file_async,
                    args=(final_file,),
                    daemon=True
                ).start()

                return response

            else:
                return "Invalid file type"

        except Exception as e:
            return f"Error: {str(e)}"

    return render_template("index.html")


@app.route("/get_resolutions", methods=["POST"])
def get_resolutions():

    url = request.form.get("url")

    if not url:
        return jsonify({
            "error": "No URL supplied"
        })

    try:

        yt = YouTube(url)

        resolutions = set()

        progressive = yt.streams.filter(
            progressive=True,
            file_extension="mp4"
        )

        for stream in progressive:
            if stream.resolution:
                resolutions.add(stream.resolution)

        adaptive = yt.streams.filter(
            only_video=True,
            file_extension="mp4"
        )

        for stream in adaptive:
            if stream.resolution:
                resolutions.add(stream.resolution)

        resolution_list = sorted(
            list(resolutions),
            key=lambda x: int(x.replace("p", "")),
            reverse=True
        )

        resolution_list.insert(0, "highest")

        return jsonify({
            "resolutions": resolution_list
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        })


@app.route("/downloads/<path:filename>")
def download_file(filename):
    return send_from_directory(
        DOWNLOAD_FOLDER,
        filename,
        as_attachment=True
    )

@app.route("/video_info", methods=["POST"])
def video_info():

    url = request.form.get("url")

    yt = YouTube(url)

    return jsonify({
        "title": yt.title,
        "author": yt.author,
        "length": yt.length,
        "thumbnail": yt.thumbnail_url
    })

# if __name__ == "__main__":
#     app.run(
#         host="0.0.0.0",
#         port=5000,
#         debug=True
#     )