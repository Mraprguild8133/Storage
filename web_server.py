from flask import Flask, render_template, request, jsonify
import boto3
from botocore.exceptions import ClientError
from config import config
import os

app = Flask(__name__)

# Wasabi configuration
WASABI_ACCESS_KEY = config.WASABI_ACCESS_KEY
WASABI_SECRET_KEY = config.WASABI_SECRET_KEY
WASABI_BUCKET = config.WASABI_BUCKET
WASABI_REGION = config.WASABI_REGION

# Initialize S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',
    aws_access_key_id=WASABI_ACCESS_KEY,
    aws_secret_access_key=WASABI_SECRET_KEY,
    region_name=WASABI_REGION
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/player')
def player():
    file_key = request.args.get('file')
    if not file_key:
        return "File parameter is required", 400
    
    # Generate presigned URL for the video
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': WASABI_BUCKET, 'Key': file_key},
            ExpiresIn=3600  # 1 hour
        )
    except ClientError as e:
        return f"Error accessing file: {e}", 404
    
    return render_template('player.html', 
                         video_url=presigned_url, 
                         filename=file_key)

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
