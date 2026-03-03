import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_change_me")
    DB_PATH = os.environ.get("DB_PATH", "swim_tracker.db")