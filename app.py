import os
import json
import base64
from datetime import datetime
import requests
from flask import Flask, request, jsonify, send_from_directory
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Настройки
CREDENTIALS_PATH = os.getenv('CREDENTIALS_PATH', 'credentials.json')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')

def get_creds():
    # Сначала пробуем загрузить из файла
    if os.path.exists(CREDENTIALS_PATH):
        try:
            creds = service_account.Credentials.from_service_account_file(
                CREDENTIALS_PATH,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            print(f"✅ Авторизация по файлу {CREDENTIALS_PATH}")
            return creds
        except Exception as e:
            print(f"❌ Ошибка загрузки файла: {e}")
    
    # Если файла нет, пробуем переменную окружения
    creds_json_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    if creds_json_env:
        try:
            creds_info = json.loads(creds_json_env)
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            print("✅ Авторизация по GOOGLE_APPLICATION_CREDENTIALS_JSON")
            return creds
        except Exception as e:
            print(f"❌ Ошибка парсинга переменной: {e}")
    
    return None

# ... остальной код без изменений, но везде используем get_creds()
