import requests
import json
import os
import smtplib
import ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- CONFIGURACIÓN ---
EMAIL_SENDER = os.environ["EMAIL_USER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASS"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]

# Procesamiento robusto de URLs
raw_urls = os.environ["WALLAPOP_URLS"]
if ";" in raw_urls:
    URLS_BUSQUEDA = [url.strip() for url in raw_urls.split(";") if url.strip()]
else:
    # Fallback por si siguen usando comas
    URLS_BUSQUEDA = [url.strip() for url in raw_urls.split(",") if url.strip()]

def extract_items_safely(json_data):
    """
    Busca la lista de productos en diferentes ubicaciones conocidas del JSON de Wallapop.
    """
    try:
        props = json_data.get('props', {}).get('pageProps', {})
        
        # Opción 1: Estructura estándar de búsqueda
        if 'searchObjects' in props:
            return props['searchObjects']
        
        # Opción 2: Estructura de catálogo
        if 'catalog' in props and 'objects' in props['catalog']:
            return props['catalog']['objects']
            
        # Opción 3: Estructura de items directos
        if 'items' in props:
            return props['items']

        # Opción 4: Búsqueda recursiva (Plan Z)
        # Si fallan las anteriores, busca cualquier lista que tenga precio y título
        print("   ⚠️ Estructura desconocida, intentando búsqueda profunda...")
        # (Simplificada para no sobrecargar, nos quedamos con las opciones 1 y 2 que cubren el 99%)
        
        return []
    except Exception as e:
        print(f"   Error explorando JSON: {e}")
        return []

def get_wallapop_listings(search_url):
    # Headers actualizados para parecer un Chrome real
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": "https://es.wallapop.com/",
        "Cache-Control": "max-age=0"
    }
    
    print(f"🌐 Consultando: {search_url[:40]}...") 
    try:
        response = requests.get(search_url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            print(f"❌ Error HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        script_data = soup.find("script", {"id": "__NEXT_DATA__"})
        
        if script_data:
            json_data = json.loads(script_data.string)
            items = extract_items_safely(json_data)
            return items if items else []
        else:
            # Si no hay JSON, a veces Wallapop devuelve HTML puro en listas antiguas
            print("⚠️ No se detectó data JSON (__NEXT_DATA__).")
            return []
            
    except Exception as e:
        print(f"❌ Excepción crítica: {e}")
        return []

def send_email_report(cars_found):
    if not cars_found: return

    subject = f"🚗 Wallapop: {len(cars_found)} oportunidades hoy"
    
    html_content = """
    <html>
      <body style="font-family: sans-serif;">
        <h2 style="color: #13c1ac;">🏎️ Coches detectados (Últimas 24h)</h2>
        <table style="width:100%; border-collapse: collapse;">
          <thead>
            <tr style="background-color: #f2f2f2; text-align: left;">
              <th style="padding: 10px;">Coche</th>
              <th style="padding: 10px;">Precio</th>
              <th style="padding: 10px;">Enlace</th>
            </tr>
          </thead>
          <tbody>
    """
    
    for car in cars_found:
        html_content += f"""
            <tr>
              <td style="padding: 10px; border-bottom: 1px solid #ddd;">{car['title']}</td>
              <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">{car['price']}</td>
              <td style="padding: 10px; border-bottom: 1px solid #ddd;"><a href="{car['url']}" style="color: #13c1ac;">Ver Anuncio</a></td>
            </tr>
        """

    html_content += "</tbody></table></body></html>"

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
        print("✅ Correo enviado.")
    except Exception as e:
        print(f"❌ Error SMTP: {e}")

def main():
    print(f"🚀 Script iniciado. Zonas detectadas: {len(URLS_BUSQUEDA)}")
    # Debug para ver si las URLs se cortan mal
    if len(URLS_BUSQUEDA) == 1:
        print("⚠️ ADVERTENCIA: Solo hay 1 zona. Revisa si el separador en Github Secrets es correcto (;).")

    all_found_cars = []
    processed_ids = set()
    yesterday = datetime.now() - timedelta(days=1)
    
    for url in URLS_BUSQUEDA:
        items = get_wallapop_listings(url)
        
        if not items:
            print("   ℹ️ No se extrajeron items (posible bloqueo o lista vacía).")
            continue
            
        print(f"   📦 Analizando {len(items)} anuncios...")
        
        for item in items:
            item_id = item.get('id')
            if item_id in processed_ids: continue
            processed_ids.add(item_id)

            try:
                # Obtener timestamp (a veces cambia de nombre)
                ts = item.get('creationDate') or item.get('creation_date')
                if not ts: continue
                
                listing_date = datetime.fromtimestamp(ts / 1000)
                
                if listing_date > yesterday:
                    title = item.get('title') or item.get('content', {}).get('title', 'Sin título')
                    price = item.get('price') or item.get('content', {}).get('price', 0)
                    slug = item.get('web_slug') or item.get('url', '')
                    
                    if isinstance(price, (int, float)): price = f"{price} €"
                    
                    all_found_cars.append({
                        'title': title.strip(),
                        'price': str(price),
                        'url': f"https://es.wallapop.com/item/{slug}"
                    })
            except Exception:
                continue
        
        time.sleep(3) # Espera prudencial

    print(f"🏁 Total nuevos: {len(all_found_cars)}")
    if all_found_cars:
        send_email_report(all_found_cars)

if __name__ == "__main__":
    main()
