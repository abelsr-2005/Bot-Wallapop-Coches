import requests
import json
import os
import smtplib
import ssl
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- CONFIGURACIÓN ---
EMAIL_SENDER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASS")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")
RAW_URLS = os.environ.get("WALLAPOP_URLS", "")

# --- SEPARACIÓN DE URLS (SOLO BARRA VERTICAL | ) ---
# Aquí está la clave: usamos | para separar las 9 búsquedas sin romper las comas internas
URLS_BUSQUEDA = [url.strip() for url in RAW_URLS.split("|") if url.strip()]

def get_headers():
    """Genera headers aleatorios para evitar bloqueos"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": "https://es.wallapop.com/"
    }

def get_wallapop_listings(search_url):
    print(f"🔎 Consultando zona...")
    
    try:
        # Pausa aleatoria para parecer humano
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(search_url, headers=get_headers(), timeout=30)
        
        if response.status_code != 200:
            print(f"   ❌ Error HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        script_data = soup.find("script", {"id": "__NEXT_DATA__"})
        
        if script_data:
            try:
                data = json.loads(script_data.string)
                # Estrategia de búsqueda profunda en el JSON
                props = data.get('props', {}).get('pageProps', {})
                
                # Intento 1: SearchObjects
                if 'searchObjects' in props:
                    return props['searchObjects']
                
                # Intento 2: Catalog Objects
                if 'catalog' in props and 'objects' in props['catalog']:
                    return props['catalog']['objects']
                
                return []
            except Exception:
                return []
        return []

    except Exception as e:
        print(f"   ❌ Error conexión: {e}")
        return []

def send_email_report(cars_found):
    if not cars_found: return

    subject = f"🚗 {len(cars_found)} Coches Nuevos (Audi/BMW/Mercedes)"
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #2c3e50;">Resumen Diario</h2>
        <p>Se han encontrado <strong>{len(cars_found)}</strong> anuncios en las últimas 24 horas.</p>
        <table style="width:100%; border-collapse: collapse;">
          <tr style="background-color: #ecf0f1;">
            <th style="padding: 10px; border: 1px solid #bdc3c7;">Coche</th>
            <th style="padding: 10px; border: 1px solid #bdc3c7;">Precio</th>
            <th style="padding: 10px; border: 1px solid #bdc3c7;">Ver</th>
          </tr>
    """
    
    for car in cars_found:
        html_content += f"""
          <tr>
            <td style="padding: 10px; border: 1px solid #bdc3c7;">{car['title']}</td>
            <td style="padding: 10px; border: 1px solid #bdc3c7; font-weight:bold;">{car['price']}</td>
            <td style="padding: 10px; border: 1px solid #bdc3c7;"><a href="{car['url']}">Enlace</a></td>
          </tr>
        """

    html_content += "</table></body></html>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg.attach(MIMEText(html_content, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("✅ Email enviado correctamente.")
    except Exception as e:
        print(f"❌ Error enviando email: {e}")

def main():
    # Este print te confirmará si el código es el nuevo
    print("🚀 INICIANDO RASTREO (VERSIÓN TUBERÍA | )...")
    print(f"📂 Zonas cargadas: {len(URLS_BUSQUEDA)}")

    if len(URLS_BUSQUEDA) == 1 and "|" in RAW_URLS:
         print("⚠️ Error crítico: El código no está separando bien las URLs.")

    all_found_cars = []
    seen_ids = set()
    yesterday = datetime.now() - timedelta(days=1)

    for i, url in enumerate(URLS_BUSQUEDA):
        print(f"--- Procesando zona {i+1}/{len(URLS_BUSQUEDA)} ---")
        items = get_wallapop_listings(url)
        
        count_zone = 0
        for item in items:
            item_id = item.get('id')
            if item_id in seen_ids: continue
            seen_ids.add(item_id)

            ts = item.get('creationDate')
            if ts and datetime.fromtimestamp(ts / 1000) > yesterday:
                price = item.get('price', 0)
                if isinstance(price, dict): price = price.get('amount', 0)
                
                all_found_cars.append({
                    'title': item.get('title', '').strip(),
                    'price': f"{price}€",
                    'url': f"https://es.wallapop.com/item/{item.get('web_slug','')}"
                })
                count_zone += 1
        
        print(f"   ✅ Nuevos en esta zona: {count_zone}")

    print(f"🏁 Total encontrados: {len(all_found_cars)}")
    if all_found_cars:
        send_email_report(all_found_cars)
    else:
        print("📭 No hay novedades hoy.")

if __name__ == "__main__":
    main()
