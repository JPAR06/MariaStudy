"""
Starts MariaStudy and exposes it via ngrok.

Modes:
  python share.py            # starts Streamlit locally + ngrok
  python share.py --docker   # Docker already running; only opens ngrok tunnel
  python share.py --token TOKEN  # save ngrok token (only needed once)
"""
import subprocess
import sys
import time
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", help="ngrok authtoken (only needed once)")
    parser.add_argument("--docker", action="store_true", help="skip starting Streamlit (Docker handles it)")
    args = parser.parse_args()

    from pyngrok import ngrok

    if args.token:
        ngrok.set_auth_token(args.token)
        print("Token guardado.")

    proc = None
    if not args.docker:
        print("A iniciar MariaStudy...")
        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py",
             "--server.port", "8502",
             "--server.headless", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(4)
    else:
        print("Modo Docker — a aguardar que o container esteja pronto...")
        time.sleep(2)

    tunnel = ngrok.connect(8502)
    url = tunnel.public_url

    print("\n" + "="*50)
    print("  MariaStudy está online!")
    print(f"  URL: {url}")
    print("="*50)
    print("\nPartilha este link com a Maria.")
    print("Para parar: Ctrl+C\n")

    try:
        if proc:
            proc.wait()
        else:
            while True:
                time.sleep(60)
    except KeyboardInterrupt:
        print("\nA fechar túnel ngrok...")
        ngrok.disconnect(url)
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
