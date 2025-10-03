FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY . .

# Create non-root user
RUN useradd -m -r bot && \
    chown -R bot:bot /app
USER bot

# Start the bot
CMD ["python", "bot.py"]
