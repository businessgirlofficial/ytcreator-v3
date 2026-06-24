"""
YouTube OAuth2 Setup — correr UNA VEZ por PC
================================================

Abre el navegador para que autorices tu cuenta de Google/YouTube,
obtiene un refresh_token y te lo imprime para que lo pegues en .env.

Prerequisitos:
  1. Crear proyecto en https://console.cloud.google.com
  2. Habilitar "YouTube Data API v3"
  3. Crear credenciales OAuth2 (tipo "Desktop app")
  4. Descargar el JSON o copiar Client ID y Client Secret

Uso:
  python scripts/youtube_auth.py --client-id TU_CLIENT_ID --client-secret TU_CLIENT_SECRET

  O si descargaste el JSON de Google Cloud:
  python scripts/youtube_auth.py --credentials-file client_secret_XXXX.json
"""

import argparse
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    parser = argparse.ArgumentParser(description="Obtener refresh token de YouTube")
    parser.add_argument("--client-id", help="OAuth2 Client ID")
    parser.add_argument("--client-secret", help="OAuth2 Client Secret")
    parser.add_argument("--credentials-file", help="Ruta al JSON descargado de Google Cloud Console")
    args = parser.parse_args()

    if args.credentials_file:
        flow = InstalledAppFlow.from_client_secrets_file(args.credentials_file, scopes=SCOPES)
    elif args.client_id and args.client_secret:
        client_config = {
            "installed": {
                "client_id": args.client_id,
                "client_secret": args.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    else:
        print("Error: necesitas --credentials-file O --client-id + --client-secret")
        sys.exit(1)

    credentials = flow.run_local_server(port=8090, prompt="consent")

    print("\n" + "=" * 60)
    print("Agrega estas lineas a tu .env:")
    print("=" * 60)
    print(f"YOUTUBE_CLIENT_ID={credentials.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={credentials.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={credentials.refresh_token}")
    print("=" * 60)


if __name__ == "__main__":
    main()
