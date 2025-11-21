import requests
import json
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- CONFIGURACIÓN EMAIL ---
EMAIL_SENDER = os.environ["EMAIL_USER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASS"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]

# --- CONFIGURACIÓN BÚSQUEDA ---
# Las URLs deben estar separadas por comas en los Secretos de Github
URLS_BUSQUEDA = os.environ["WALLAPOP_URLS"].split(",")

def get_wallapop_listings(search_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    try:
        response = requests.get(search_url, headers=headers)
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            # Buscamos el JSON de datos (Next.js hydration)
            script_data = soup.find("script", {"id": "__NEXT_DATA__"})
            
            if script_data:
                json_data = json.loads(script_data.string)
                try:
                    # Intentamos acceder a los objetos de búsqueda
                    return json_data['props']['pageProps']['searchObjects']
                except KeyError:
                    return []
        return []
    except Exception as e:
        print(f"Error en scraping: {e}")
        return []

def send_email_report(cars_found):
    if not cars_found:
        return

    subject = f"🚗 Resumen Wallapop: {len(cars_found)} nuevos coches encontrados"
    
    # Construimos el cuerpo del correo en HTML
    html_content = """
    <html>
      <body>
        <h2>🏎️ Novedades del día (Audi, BMW, Mercedes)</h2>
        <p>Aquí tienes los coches publicados en las últimas 24h en Huelva, Sevilla y Cádiz:</p>
        <table style="width:100%; border-collapse: collapse; text-align: left;">
          <thead>
            <tr style="background-color: #f2f2f2;">
              <th style="padding: 10px; border-bottom: 1px solid #ddd;">Coche</th>
              <th style="padding: 10px; border-bottom: 1px solid #ddd;">Precio</th>
              <th style="padding: 10px; border-bottom: 1px solid #ddd;">Enlace</th>
            </tr>
          </thead>
          <tbody>
    """
    
    for car in cars_found:
        html_content += f"""
            <tr>
              <td style="padding: 10px; border-bottom: 1px solid #ddd;">{car['title']}</td>
              <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">{car['price']}</td>
              <td style="padding: 10px; border-bottom: 1px solid #ddd;"><a href="{car['url']}" style="background-color: #13c1ac; color: white; padding: 5px 10px; text-decoration: none; border-radius: 5px;">Ver Anuncio</a></td>
            </tr>
        """

    html_content += """
          </tbody>
        </table>
        <p style="font-size: 12px; color: #888;">Este reporte ha sido generado automáticamente por Github Actions.</p>
      </body>
    </html>
    """

    # Configuración del envío
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = EMAIL_SENDER
    message["To"] = EMAIL_RECEIVER
    message.attach(MIMEText(html_content, "html"))

    # Envío seguro mediante SMTP_SSL (Gmail usa puerto 465)
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, message.as_string())
        print("✅ Correo enviado con éxito.")
    except Exception as e:
        print(f"❌ Error enviando correo: {e}")

def main():
    found_cars = []
    seen_ids = set()
    yesterday = datetime.now() - timedelta(days=1)
    
    print(f"🔍 Buscando en {len(URLS_BUSQUEDA)} URLs configuradas...")

    for url in URLS_BUSQUEDA:
        if not url.strip(): continue
        items = get_wallapop_listings(url.strip())
        
        for item in items:
            if item['id'] in seen_ids: continue
            seen_ids.add(item['id'])

            # Fecha
            try:
                ts = item.get('creationDate', 0) / 1000
                listing_date = datetime.fromtimestamp(ts)
                
                # Filtro: Últimas 24 horas
                if listing_date > yesterday:
                    car_data = {
                        'title': item.get('title', 'Desconocido').strip(),
                        'price': f"{item.get('price', 0)}€",
                        'url': f"https://es.wallapop.com/item/{item.get('web_slug','')}"
                    }
                    found_cars.append(car_data)
            except Exception:
                continue

    if found_cars:
        print(f"🎉 Se encontraron {len(found_cars)} coches nuevos. Enviando email...")
        send_email_report(found_cars)
    else:
        print("🤷‍♂️ No se encontraron coches nuevos hoy.")

if __name__ == "__main__":
    main()
