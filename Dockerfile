# Gunakan image resmi dari Microsoft yang sudah terinstall Chrome/Playwright
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Pindah ke folder /app di dalam server
WORKDIR /app

# Copy requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file bot kamu
COPY . .

# Jalankan botnya
CMD ["python", "bot_telegram.py"]
