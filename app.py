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

# Настройки из переменных окружения
CREDENTIALS_PATH = os.getenv('CREDENTIALS_PATH', 'credentials.json')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')

print("=== Настройка авторизации ===")
print(f"SPREADSHEET_ID: {SPREADSHEET_ID}")
print(f"CREDENTIALS_PATH: {CREDENTIALS_PATH}")

def get_creds():
    """Возвращает объект credentials для Google API."""
    # 1. Попытка загрузить из файла
    if os.path.exists(CREDENTIALS_PATH):
        try:
            creds = service_account.Credentials.from_service_account_file(
                CREDENTIALS_PATH,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            print(f"✅ Успешно загружен credentials из файла: {CREDENTIALS_PATH}")
            return creds
        except Exception as e:
            print(f"❌ Ошибка загрузки из файла: {e}")
    else:
        print(f"⚠️ Файл {CREDENTIALS_PATH} не найден.")

    # 2. Попытка загрузить из переменной окружения
    creds_json_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    if creds_json_env:
        try:
            creds_info = json.loads(creds_json_env)
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            print("✅ Успешно загружен credentials из переменной окружения")
            return creds
        except Exception as e:
            print(f"❌ Ошибка парсинга переменной: {e}")
    else:
        print("⚠️ Переменная GOOGLE_APPLICATION_CREDENTIALS_JSON не задана.")

    # Если ничего не получилось
    print("❌ Нет доступных credentials для авторизации.")
    return None

# Проверим credentials при запуске
creds = get_creds()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    creds = get_creds()
    if not creds:
        return jsonify({'success': False, 'error': 'Нет доступа к Google Sheets'})
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range='Справочник!A2:C').execute()
    rows = result.get('values', [])
    vehicles = []
    for row in rows:
        if len(row) >= 2:
            try:
                coeff = float(row[2].replace(',', '.')) if len(row) > 2 and row[2] else 0
            except:
                coeff = 0
            vehicles.append({
                'name': row[0],
                'plate': row[1],
                'coefficient': coeff
            })
    return jsonify({'success': True, 'vehicles': vehicles})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    login = data.get('login')
    password = data.get('password')
    if not login or not password:
        return jsonify({'success': False, 'error': 'Введите логин и пароль'})
    creds = get_creds()
    if not creds:
        return jsonify({'success': False, 'error': 'Нет доступа к Google Sheets'})
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range='Пользователи!A2:E').execute()
    rows = result.get('values', [])
    for row in rows:
        if len(row) >= 4 and row[1] == login and str(row[2]) == password:
            return jsonify({
                'success': True,
                'user': {
                    'fullName': row[0],
                    'login': row[1],
                    'email': row[3]
                }
            })
    return jsonify({'success': False, 'error': 'Неверный логин или пароль'})

@app.route('/api/submit', methods=['POST'])
def submit_waybill():
    data = request.json
    driver_name = data.get('driverName')
    vehicle = data.get('vehicle')
    mileage_before = data.get('mileageBefore')
    mileage_after = data.get('mileageAfter')
    fuel_start = data.get('fuelStart', 0)
    refuel = data.get('refuel', 0)
    hours = data.get('hoursWorked', 0)
    waybill_date = data.get('waybillDate', '')
    fuel_type = data.get('fuelType', '')
    photo_base64 = data.get('photoBase64', '')
    photo_name = data.get('photoName', 'photo.jpg')
    photo_type = data.get('photoType', 'image/jpeg')

    if not driver_name or not vehicle or mileage_before is None or mileage_after is None:
        return jsonify({'success': False, 'error': 'Заполните все обязательные поля'})

    creds = get_creds()
    if not creds:
        return jsonify({'success': False, 'error': 'Нет доступа к Google Sheets'})
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    # Коэффициент
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range='Справочник!A2:C').execute()
    rows = result.get('values', [])
    coefficient = 0
    for row in rows:
        if len(row) >= 2 and row[0] + ' ' + row[1] == vehicle:
            try:
                coefficient = float(row[2].replace(',', '.')) if len(row) > 2 and row[2] else 0
            except:
                coefficient = 0
            break

    total_mileage = max(0, float(mileage_after) - float(mileage_before))
    fuel_consumed = total_mileage / 100 * coefficient
    fuel_end = float(fuel_start) - fuel_consumed + float(refuel)

    # Фото на ImgBB
    photo_url = ''
    if photo_base64:
        try:
            payload = {
                'key': IMGBB_API_KEY,
                'image': photo_base64,
                'name': photo_name,
                'expiration': 86400
            }
            resp = requests.post('https://api.imgbb.com/1/upload', data=payload)
            if resp.status_code == 200:
                photo_url = resp.json()['data']['url']
            else:
                photo_url = f'Ошибка ImgBB: {resp.text}'
        except Exception as e:
            photo_url = f'Ошибка: {str(e)}'

    row_data = [
        str(datetime.now().isoformat()),
        waybill_date,
        driver_name,
        vehicle,
        mileage_before,
        mileage_after,
        total_mileage,
        fuel_start,
        fuel_consumed,
        refuel,
        fuel_end,
        hours,
        photo_url,
        fuel_type
    ]
    row_data = [str(x) for x in row_data]

    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range='Путевые_листы!A:N',
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body={'values': [row_data]}
    ).execute()

    return jsonify({
        'success': True,
        'message': 'Путевой лист отправлен! Фото сохранено.',
        'photoUrl': photo_url
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
