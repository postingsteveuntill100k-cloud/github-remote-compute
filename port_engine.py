import socket

def find_available_port():
    """Finds an available ephemeral port assigned by the OS, preventing race conditions."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
