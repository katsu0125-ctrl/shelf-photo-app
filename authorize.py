"""
最初に1回だけ実行する認証スクリプト。
ブラウザが開くので、写真の保存先にしたいGoogleアカウントでログインして許可する。
成功すると token.json が作られ、以降アプリはログイン不要で動く。
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.file']
CLIENT_SECRET = 'client_secret.json'
TOKEN_FILE = 'token.json'


def main():
    if not os.path.exists(CLIENT_SECRET):
        print(f'エラー: {CLIENT_SECRET} が見つかりません。')
        print('Google Cloud で OAuth クライアント ID（デスクトップアプリ）を作成し、')
        print('ダウンロードした JSON を client_secret.json として保存してください。')
        return

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
    creds = flow.run_local_server(port=0, prompt='consent')

    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    print(f'認証成功！ {TOKEN_FILE} を作成しました。')
    print('これで app.py を起動すればアップロードできます。')


if __name__ == '__main__':
    main()
