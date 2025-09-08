from globalit_app import create_app
import socket

app = create_app()

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Connect to a remote server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    
    print("🚀 Starting Global IT Education Web Application...")
    print("=" * 60)
    print(f"📍 Local Access:    http://127.0.0.1:5000")
    print(f"🌐 Network Access:  http://{local_ip}:5000")
    print("=" * 60)
    print("📱 To test from other devices:")
    print(f"   • Connect devices to the same WiFi network")
    print(f"   • Open browser and go to: http://{local_ip}:5000")
    print("=" * 60)
    print("⚠️  Security Note: This exposes the app to your local network")
    print("   Only use this for testing purposes!")
    print("=" * 60)
    
    # Run the app on all network interfaces (0.0.0.0)
    # This allows external connections from other devices
    app.run(
        host='0.0.0.0',  # Listen on all network interfaces
        port=5000,       # Port number
        debug=True,      # Enable debug mode for development
        threaded=True    # Enable threading for better performance
    )
