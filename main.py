import flet as ft
import threading
import uvicorn
import socket
from server import app as fastapi_app

# Function to get local IP address
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Function to run the FastAPI server
def run_fastapi():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000, log_level="error")

def main(page: ft.Page):
    page.title = "CinePix Background Server"
    page.theme_mode = ft.ThemeMode.DARK
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.window_width = 400
    page.window_height = 600
    page.bgcolor = "#0f172a"
    page.padding = 30

    # Start FastAPI server in a background thread
    server_thread = threading.Thread(target=run_fastapi, daemon=True)
    server_thread.start()
    
    local_ip = get_local_ip()

    # UI Elements
    title = ft.Text("CinePix Server", size=32, weight=ft.FontWeight.BOLD, color="#38bdf8")
    status_icon = ft.Icon(name=ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN_500, size=60)
    status_text = ft.Text("Server is Running", size=20, color=ft.colors.GREEN_400)
    
    ip_info = ft.Container(
        content=ft.Column([
            ft.Text("App can now access local API at:", color="#94a3b8", size=14),
            ft.Text(f"http://127.0.0.1:8000", size=18, weight=ft.FontWeight.BOLD, color="#f8fafc", selectable=True),
            ft.Text(f"Network IP: http://{local_ip}:8000", size=14, color="#64748b", selectable=True),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=20,
        bgcolor="#1e293b",
        border_radius=10,
        margin=ft.margin.only(top=20, bottom=20)
    )

    instructions = ft.Text(
        "You can now minimize this app. The scraping server will continue running in the background. Open your main CinePix app to start streaming movies.",
        text_align=ft.TextAlign.CENTER,
        color="#94a3b8",
        size=14
    )
    
    monitor_btn = ft.ElevatedButton(
        text="Open Monitor Dashboard",
        icon=ft.icons.MONITOR_HEART,
        color=ft.colors.WHITE,
        bgcolor="#0284c7",
        on_click=lambda _: page.launch_url(f"http://127.0.0.1:8000/monitor")
    )

    # Add elements to page
    page.add(
        ft.Column(
            [
                title,
                ft.Container(height=20),
                status_icon,
                status_text,
                ip_info,
                monitor_btn,
                ft.Container(height=20),
                instructions
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER
        )
    )

ft.app(target=main)
