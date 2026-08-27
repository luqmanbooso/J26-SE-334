import os
import socket
import time
from typing import Optional
from core.adb_client import ADBClient
from core.event_logger import EventLogger

class InterruptionStressor:
    def __init__(self, adb: ADBClient, logger: EventLogger, port: int = 5554):
        self.adb = adb
        self.logger = logger
        self.port = port
        self.auth_token = self._get_auth_token()

    def _get_auth_token(self) -> str:
        token_path = os.path.expanduser("~/.emulator_console_auth_token")
        if os.path.exists(token_path):
            with open(token_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def _send_console_cmd(self, command: str) -> str:
        try:
            sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
            sock.recv(1024)
            if self.auth_token:
                sock.sendall(f"auth {self.auth_token}\n".encode("utf-8"))
                time.sleep(0.1)
                sock.recv(1024)
            sock.sendall(f"{command}\n".encode("utf-8"))
            time.sleep(0.2)
            cmd_resp = sock.recv(1024).decode("utf-8", errors="ignore")
            sock.sendall("quit\n".encode("utf-8"))
            sock.close()
            return cmd_resp.strip()
        except Exception as e:
            return f"SOCKET_ERROR: {str(e)}"

    def trigger_incoming_call(self, phone_number: str = "15555215554") -> None:
        clean_number = "".join(filter(str.isdigit, str(phone_number)))
        resp = self._send_console_cmd(f"gsm call {clean_number}")
        self.logger.record("INTERRUPTION", "INCOMING_CALL_RINGING", {"number": clean_number, "console_resp": resp})

    def accept_call(self) -> None:
        """Programmatically answers the ringing call using Android Keyevent 5 (KEYCODE_CALL)."""
        self.adb.run_shell("input keyevent 5")
        self.logger.record("INTERRUPTION", "CALL_ACCEPTED", {"action": "keyevent_5_call"})

    def dismiss_call(self, phone_number: str = "15555215554") -> None:
        """Cancels the GSM signal and explicitly sends Keyevent 6 (KEYCODE_ENDCALL)."""
        clean_number = "".join(filter(str.isdigit, str(phone_number)))
        resp = self._send_console_cmd(f"gsm cancel {clean_number}")
        self.adb.run_shell("input keyevent 6")
        self.logger.record("INTERRUPTION", "CALL_DISMISSED", {"number": clean_number, "console_resp": resp})

    def send_sms_banner(self, message: str, sender: str = "15555215554", force_fail: bool = False) -> None:
        """Sends an SMS. If force_fail is True, it purposely tests modem error handling."""
        src = "INVALID_SENDER_123" if force_fail else "".join(filter(str.isdigit, str(sender)))
        clean_msg = message.replace('"', '').replace("'", "")
        
        resp = self._send_console_cmd(f"sms send {src} {clean_msg}")
        
        # Log status conditionally based on GSM modem response
        status = "FAILED_AT_MODEM" if "KO:" in resp else "APPLIED"
        self.logger.record("INTERRUPTION", "SMS_NOTIFICATION", {"sender": src, "message": clean_msg, "console_resp": resp}, status=status)

    def trigger_app_standby(self, package_name: str) -> None:
        self.adb.run_shell(f"am set-standby-bucket {package_name} rare")
        self.logger.record("INTERRUPTION", "DOZE_STANDBY_TRIGGER", {"package": package_name, "bucket": "rare"})
