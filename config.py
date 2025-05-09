import os
from dotenv import load_dotenv

# load environment variables from a .env file (if present)
load_dotenv()

class Config:
    # point at your local MySQL server
    DB_HOST     = os.getenv("DB_HOST", "localhost")
    DB_PORT     = int(os.getenv("DB_PORT", "3306"))
    DB_USER     = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "12345")
    DB_NAME     = os.getenv("DB_NAME", "champions_league")

    # Flask session secret
    SECRET_KEY  = os.getenv("SECRET_KEY", "supersecretkey")
