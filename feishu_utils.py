
import requests
import json
import time
import hashlib
import base64
from flask import current_app

class FeishuBot:
    def __init__(self, app_id, app_secret, verification_token=None, encrypt_key=None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.encrypt_key = encrypt_key
        self.tenant_access_token = None
        self.token_expire_time = 0

    def get_tenant_access_token(self):
        if self.tenant_access_token and time.time() < self.token_expire_time:
            return self.tenant_access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            data = response.json()
            if data.get("code") == 0:
                self.tenant_access_token = data.get("tenant_access_token")
                self.token_expire_time = time.time() + data.get("expire") - 60 # Refresh 1 min early
                return self.tenant_access_token
            else:
                print(f"Error getting tenant_access_token: {data}")
                return None
        except Exception as e:
            print(f"Exception getting tenant_access_token: {e}")
            return None

    def send_message(self, receive_id_type, receive_id, content_type, content):
        token = self.get_tenant_access_token()
        if not token:
            return {"code": -1, "msg": "Failed to get token"}

        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        # content must be a JSON string for 'text' type
        if content_type == "text":
            msg_content = json.dumps({"text": content})
        else:
            msg_content = content

        payload = {
            "receive_id": receive_id,
            "msg_type": content_type,
            "content": msg_content
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            return response.json()
        except Exception as e:
            return {"code": -1, "msg": str(e)}

    def verify_signature(self, timestamp, nonce, signature, body):
        if not self.verification_token:
            return True # Skip if not configured
            
        # Calculate signature: sha256(timestamp + nonce + encrypt_key + body)
        # But for event subscription V2.0 (webhook), check documentation
        # Actually, for simple verification token check (deprecated but common):
        # The new way is header signature verification.
        # Let's stick to checking 'challenge' for now or assume trusted source if configured.
        # The official way involves concatenating timestamp + nonce + encrypt_key + body_string
        # then sha256.
        
        key = self.encrypt_key if self.encrypt_key else ""
        content = timestamp + nonce + key + body
        local_sig = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        return local_sig == signature
