import requests
import json
import hmac
import hashlib

class QQBot:
    """
    A simple OneBot V11 (formerly CQHTTP) client for QQ Bots.
    Compatible with NapCatQQ, go-cqhttp, Lagrange.Core, etc.
    """
    def __init__(self, http_api_url, access_token=None, secret=None):
        self.http_api_url = http_api_url.rstrip('/')
        self.access_token = access_token
        self.secret = secret

    def verify_signature(self, signature, body):
        """
        Verify the X-Signature header from the bot server (HMAC SHA1).
        """
        if not self.secret:
            return True
        
        if not signature:
            return False
            
        # signature format: "sha1=..."
        sig_hash = hmac.new(self.secret.encode('utf-8'), body, hashlib.sha1).hexdigest()
        return signature == f"sha1={sig_hash}"

    def send_message(self, message_type, user_id, group_id, message):
        """
        Send a message via HTTP API.
        """
        url = f"{self.http_api_url}/send_msg"
        
        headers = {
            "Content-Type": "application/json"
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        payload = {
            "message_type": message_type,
            "user_id": user_id,
            "group_id": group_id,
            "message": message,
            "auto_escape": False
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"QQ Bot Send Error: {e}")
            return {"status": "failed", "retcode": -1, "msg": str(e)}

    def send_private_msg(self, user_id, message):
        return self.send_message("private", user_id, None, message)

    def send_group_msg(self, group_id, message):
        return self.send_message("group", None, group_id, message)
