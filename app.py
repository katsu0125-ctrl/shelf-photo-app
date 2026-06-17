import os
import io
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB上限

SCOPES = ['https://www.googleapis.com/auth/drive.file']
ROOT_FOLDER_NAME = '棚写真'
TOKEN_FILE = os.environ.get('TOKEN_FILE', 'token.json')


def _load_credentials():
    # 1) 環境変数 GOOGLE_TOKEN_JSON があればそれを優先（Render などのクラウド向け）
    token_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if token_json:
        return Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    # 2) なければローカルの token.json を使う
    if os.path.exists(TOKEN_FILE):
        return Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    raise RuntimeError('認証情報がありません。ローカルでは authorize.py を実行し、'
                       'クラウドでは環境変数 GOOGLE_TOKEN_JSON を設定してください')


def get_drive_service():
    creds = _load_credentials()
    # アクセストークンが期限切れなら自動更新
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # ローカルファイル運用時のみ書き戻す
        if not os.environ.get('GOOGLE_TOKEN_JSON') and os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)


def get_or_create_folder(service, name, parent_id=None):
    """指定した名前のフォルダを取得。なければ作成。"""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, fields='files(id, name)').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    meta = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
    }
    if parent_id:
        meta['parents'] = [parent_id]
    folder = service.files().create(body=meta, fields='id').execute()
    return folder['id']


def get_root_folder_id(service):
    root_id_env = os.environ.get('GOOGLE_DRIVE_ROOT_FOLDER_ID')
    if root_id_env:
        return root_id_env
    return get_or_create_folder(service, ROOT_FOLDER_NAME)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    store_name = request.form.get('store_name', '').strip()
    taken_at_str = request.form.get('taken_at', '').strip()
    photo = request.files.get('photo')

    if not store_name:
        return jsonify({'ok': False, 'error': '店舗名を入力してください'}), 400
    if not photo or photo.filename == '':
        return jsonify({'ok': False, 'error': '写真を選択してください'}), 400

    # 日時パース（フォームの datetime-local 形式: "2026-06-17T14:30"）
    try:
        taken_at = datetime.fromisoformat(taken_at_str) if taken_at_str else datetime.now()
    except ValueError:
        taken_at = datetime.now()

    ym_folder = taken_at.strftime('%Y-%m')
    timestamp = taken_at.strftime('%Y%m%d_%H%M')
    ext = os.path.splitext(photo.filename)[1] or '.jpg'
    filename = f"{timestamp}_{store_name}{ext}"

    try:
        service = get_drive_service()
        root_id = get_root_folder_id(service)
        store_id = get_or_create_folder(service, store_name, root_id)
        ym_id = get_or_create_folder(service, ym_folder, store_id)

        file_data = photo.read()
        media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype=photo.content_type or 'image/jpeg')
        file_meta = {'name': filename, 'parents': [ym_id]}
        uploaded = service.files().create(body=file_meta, media_body=media, fields='id,name,webViewLink').execute()

        return jsonify({
            'ok': True,
            'message': f'アップロード完了: {filename}',
            'link': uploaded.get('webViewLink', ''),
        })
    except Exception as e:
        app.logger.error(e)
        return jsonify({'ok': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5051))
    app.run(host='0.0.0.0', port=port, debug=False)
