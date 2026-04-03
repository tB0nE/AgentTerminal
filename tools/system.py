import subprocess
import shutil

def send_notification(message: str) -> str:
    """Sends a persistent system desktop notification using notify-send."""
    if not shutil.which("notify-send"):
        return "Error: notify-send not found on this system."
    
    try:
        # --hint=int:transient:0 ensures the notification stays in history on KDE/GNOME
        # --urgency=normal or critical can also be used
        subprocess.run(
            ["notify-send", "am_agents", message, "--hint=int:transient:0"],
            check=True,
            capture_output=True,
            text=True
        )
        return f"Notification sent: {message}"
    except Exception as e:
        return f"Error sending notification: {str(e)}"

# Export for dynamic discovery
TOOL_DISPATCH = {
    "send_notification": send_notification
}
