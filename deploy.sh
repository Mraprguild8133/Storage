#!/bin/bash

echo "🚀 Deploying Telegram File Bot with Wasabi Storage"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create one from .env.example"
    exit 1
fi

# Create virtual environment
echo "📦 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Test Wasabi connection
echo "🔗 Testing Wasabi connection..."
python3 -c "
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

try:
    s3 = boto3.client(
        's3',
        endpoint_url=f'https://s3.{os.getenv(\"WASABI_REGION\")}.wasabisys.com',
        aws_access_key_id=os.getenv('WASABI_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('WASABI_SECRET_KEY'),
        region_name=os.getenv('WASABI_REGION')
    )
    s3.list_buckets()
    print('✅ Wasabi connection successful!')
except Exception as e:
    print(f'❌ Wasabi connection failed: {e}')
"

# Start the bot
echo "🤖 Starting Telegram File Bot..."
python3 bot.py
