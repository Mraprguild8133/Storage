import os
import base64
import threading
import logging
from flask import Flask, render_template, jsonify

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for player.html
flask_app = Flask(__name__, template_folder="templates")

@flask_app.route("/")
def index():
    return render_template("index.html")

@flask_app.route("/player/<media_type>/<encoded_url>")
def player(media_type, encoded_url):
    # Decode the URL
    try:
        # Add padding if needed
        padding = 4 - (len(encoded_url) % 4)
        if padding != 4:
            encoded_url += '=' * padding
        media_url = base64.urlsafe_b64decode(encoded_url).decode()
        return render_template("player.html", media_type=media_type, media_url=media_url)
    except Exception as e:
        return f"Error decoding URL: {str(e)}", 400

@flask_app.route("/health")
def health():
    return jsonify({"status": "ok"})

def run_flask():
    """Run the Flask web server"""
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)
    
    # Check if template files exist, create them if not
    create_template_files()
    
    logger.info("Starting Flask web server on port 8000...")
    flask_app.run(host="0.0.0.0", port=8000, debug=False)

def create_template_files():
    """Create default template files if they don't exist"""
    
    # Create index.html if it doesn't exist
    index_html = """<!DOCTYPE html>
<html>
<head>
    <title>Media Player Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .status { padding: 20px; background: #f0f0f0; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Media Player Server</h1>
        <div class="status">
            <p>Server is running successfully!</p>
            <p>Use the Telegram bot to upload files and get player links.</p>
        </div>
    </div>
</body>
</html>"""
    
    # Create player.html if it doesn't exist
    player_html = """<!DOCTYPE html>
<html>
<head>
    <title>Media Player - {{ media_type.title() }}</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: #1a1a1a; 
            color: white; 
            text-align: center;
        }
        .container { 
            max-width: 1000px; 
            margin: 0 auto; 
        }
        .player-container {
            background: #2d2d2d;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        video, audio {
            width: 100%;
            max-width: 800px;
            border-radius: 5px;
        }
        .download-btn {
            display: inline-block;
            padding: 10px 20px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Media Player</h1>
        <div class="player-container">
            {% if media_type == 'video' %}
                <video controls autoplay>
                    <source src="{{ media_url }}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            {% elif media_type == 'audio' %}
                <audio controls autoplay>
                    <source src="{{ media_url }}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            {% else %}
                <p>This file type cannot be played in the browser.</p>
            {% endif %}
        </div>
        
        <a href="{{ media_url }}" class="download-btn" download>
            📥 Download File
        </a>
        
        <p><small>Link expires in 7 days</small></p>
    </div>
</body>
</html>"""
    
    # Write files if they don't exist
    if not os.path.exists("templates/index.html"):
        with open("templates/index.html", "w") as f:
            f.write(index_html)
        logger.info("Created templates/index.html")
    
    if not os.path.exists("templates/player.html"):
        with open("templates/player.html", "w") as f:
            f.write(player_html)
        logger.info("Created templates/player.html")

if __name__ == "__main__":
    run_flask()
