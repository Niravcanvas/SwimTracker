FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Don't copy local venv into the image
# (add venv/ to .dockerignore)

# Expose port
EXPOSE 4000

# Run with gunicorn (production-safe)
CMD ["gunicorn", "--bind", "0.0.0.0:4000", "--workers", "2", "--timeout", "120", "app:app"]