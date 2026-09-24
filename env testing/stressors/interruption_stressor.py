import os
import socket
import time
from typing import Optional, Dict, Any
from core.base import BaseStressor
from core.adb_client import ADBClient
from core.event_logger import EventLogger

class InterruptionStressor(BaseStressor):
    """Injects real-world interruptions: incoming calls, SMS banners, app backgrounding, and Doze/App-Standby transitions."""

    def __init__(self, adb: ADBClient, logger: EventLogger, port: int = 5554):
        super().__init__(adb, logger, category="INTERRUPTION")
        self.port = port
        self.auth_token = self._get_auth_token()
        self.active_call_number: Optional[str] = None

    def apply(self, **kwargs) -> bool:
        """Applies configured interruption."""
        itype = kwargs.get("type", "call")
        if itype == "call":
            self.trigger_incoming_call(kwargs.get("number", "15555215554"))
        elif itype == "sms":
            self.send_sms_banner(kwargs.get("message", "One-Time Passcode: 882910"), kwargs.get("sender", "15555215554"))
        elif itype == "background":
            self.background_app(kwargs.get("duration_sec", 3.0), kwargs.get("package_name"))
        elif itype == "doze":
            self.trigger_doze_mode(True)
        return True

    def _get_auth_token(self) -> str:
        token_path = os.path.expanduser("~/.emulator_console_auth_token")
        if os.path.exists(token_path):
            try:
                with open(token_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return ""

    def _send_console_cmd(self, command: str) -> str:
        if self.adb.is_simulated:
            return f"SIMULATED_OK: {command}"

        try:
            sock = socket.create_connection(("127.0.0.1", self.port), timeout=4)
            sock.recv(1024)
            if self.auth_token:
                sock.sendall(f"auth {self.auth_token}\n".encode("utf-8"))
                time.sleep(0.1)
                sock.recv(1024)
            sock.sendall(f"{command}\n".encode("utf-8"))
            time.sleep(0.15)
            cmd_resp = sock.recv(1024).decode("utf-8", errors="ignore")
            sock.sendall("quit\n".encode("utf-8"))
            sock.close()
            return cmd_resp.strip()
        except Exception as e:
            return f"SOCKET_FALLBACK: {self.adb.run_emulator_cmd(command)}"

    def trigger_incoming_call(self, phone_number: str = "15555215554") -> None:
        """Triggers incoming GSM call on emulator."""
        clean_number = "".join(filter(str.isdigit, str(phone_number))) or "15555215554"
        self.active_call_number = clean_number
        resp = self._send_console_cmd(f"gsm call {clean_number}")
        self.is_active = True
        self.logger.record("INTERRUPTION_CALL", "INCOMING_CALL_RINGING", {
            "number": clean_number,
            "response": resp
        })

    def accept_call(self) -> None:
        """Answers the active ringing call using Android KEYCODE_CALL (Keyevent 5)."""
        self.adb.run_shell("input keyevent 5")
        self.logger.record("INTERRUPTION_CALL", "CALL_ACCEPTED", {"action": "KEYCODE_CALL"})

    def dismiss_call(self, phone_number: Optional[str] = None) -> None:
        """Declines or terminates call using GSM cancel and KEYCODE_ENDCALL (Keyevent 6)."""
        target = phone_number or self.active_call_number or "15555215554"
        clean_number = "".join(filter(str.isdigit, str(target)))
        resp = self._send_console_cmd(f"gsm cancel {clean_number}")
        self.adb.run_shell("input keyevent 6")
        self.active_call_number = None
        self.logger.record("INTERRUPTION_CALL", "CALL_TERMINATED", {
            "number": clean_number,
            "response": resp
        })

    def send_sms_banner(self, message: str, sender: str = "15555215554", force_fail: bool = False) -> None:
        """Sends an SMS message notification banner."""
        src = "INVALID_SENDER" if force_fail else "".join(filter(str.isdigit, str(sender))) or "15555215554"
        clean_msg = message.replace('"', '').replace("'", "")
        resp = self._send_console_cmd(f"sms send {src} {clean_msg}")
        status = "FAILED_AT_MODEM" if "KO:" in resp else "APPLIED"
        self.logger.record("INTERRUPTION_SMS", "SMS_NOTIFICATION_BANNER", {
            "sender": src,
            "message": clean_msg,
            "response": resp
        }, status=status)

    def background_app(self, duration_sec: float = 3.0, package_name: Optional[str] = None) -> None:
        """Sends active app to background via Home button, pauses, then reopens app."""
        self.logger.record("INTERRUPTION_LIFECYCLE", "APP_BACKGROUNDED", {"duration_sec": duration_sec})
        self.adb.run_shell("input keyevent 3")  # KEYCODE_HOME

        if duration_sec > 0:
            time.sleep(duration_sec)

        if package_name:
            self.resume_app(package_name)

    def resume_app(self, package_name: str) -> None:
        """Resumes target package to foreground via monkey launcher intent."""
        self.adb.run_shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
        self.logger.record("INTERRUPTION_LIFECYCLE", "APP_RESUMED", {"package": package_name})

    def trigger_doze_mode(self, enabled: bool = True) -> None:
        """Forces system into deep Android Doze mode."""
        if enabled:
            self.adb.run_shell("dumpsys deviceidle force-idle")
        else:
            self.adb.run_shell("dumpsys deviceidle unforce")
        self.logger.record("INTERRUPTION_DOZE", "SYSTEM_DOZE_TRANSITION", {"force_idle": enabled})

    def trigger_app_standby(self, package_name: str, bucket: str = "rare") -> None:
        """Sets app standby bucket: 'active', 'working_set', 'frequent', 'rare'."""
        self.adb.run_shell(f"am set-standby-bucket {package_name} {bucket}")
        self.logger.record("INTERRUPTION_STANDBY", "APP_STANDBY_BUCKET_SET", {
            "package": package_name,
            "bucket": bucket
        })

    def revert(self) -> bool:
        """Restores interruption state (dismisses active calls, restores Doze)."""
        if self.active_call_number:
            self.dismiss_call()
        self.trigger_doze_mode(False)
        self.is_active = False
        self.current_state.clear()
        self.logger.record("INTERRUPTION", "INTERRUPTIONS_CLEARED", {})
        return True
