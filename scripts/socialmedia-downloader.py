from pathlib import Path
import yt_dlp

def downloader(url: str, ruta_destino: str = None):
  # Si no se especifica ruta, usa Descargas de Windows por defecto
  if not ruta_destino:
    ruta_final = Path.home() / "Downloads"
  else:
    ruta_final = Path(ruta_destino)

  ruta_final.mkdir(parents=True, exist_ok=True)

  plantilla_salida = str(ruta_final / "%(title)s [%(id)s].%(ext)s")

  opciones = {
    "outtmpl": plantilla_salida,
    "format": "bestvideo+bestaudio/best",
  }

  print(f"Guardando en: {ruta_final}")
  with yt_dlp.YoutubeDL(opciones) as ydl:
    ydl.download([url])

if __name__ == "__main__":
  video_url = input("Ingresa la URL del video de TikTok: ").strip()
  carpeta_guardado = input("Ingresa la ruta de la carpeta (o Enter para Descargas): ").strip()

  # Pasa None si el usuario solo presiona Enter
  downloader(video_url, carpeta_guardado or None)