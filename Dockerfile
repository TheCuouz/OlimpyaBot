FROM python:3.11-slim
# Emoji font and FriBiDi (Pillow's complex text layout) for the Tiamat welcome card
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-color-emoji libfribidi0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
