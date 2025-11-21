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

# !!! CONFIGURACIÓN DE TIEMPO !!!
# Puesto en 30 para probar. CÁMBIALO A 1 CUANDO FUNCIONE PARA QUE SEA DIARIO.
DIAS_ATRAS = 30 

# --- SEPARACIÓN DE URLS ---
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
        time.sleep(random.uniform(1, 3)) # Pausa humana
        response = requests.get(search_url, headers=get_headers(), timeout=30)
        
        if response.status_code != 200:
            print(f"   ❌ Error HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        script_data = soup.find("script", {"id": "__NEXT_DATA__"})
        
        if script_data:
            try:
                data = json.loads(script_data.string)
                props = data.get('props', {}).get('pageProps', {})
                
                # Búsqueda en ubicaciones conocidas del JSON
                if 'searchObjects' in props: return props['searchObjects']
                if 'catalog' in props and 'objects' in props['catalog']: return props['catalog']['objects']
                
                return []
            except Exception:
                return []
        return []

    except Exception as e:
        print(f"   ❌ Error conexión: {e}")
        return []

def send_email_report(cars_found):
    if not cars_found: return

    # Asunto más llamativo
    subject = f"✅ PRUEBA EXITOSA: {len(cars_found)} Coches encontrados"
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #2c3e50;">Reporte de Prueba (Últimos {DIAS_ATRAS} días)</h2>
        <p>Si estás leyendo esto, el bot funciona y el envío de correos es correcto.</p>
        <p>Se han encontrado <strong>{len(cars_found)}</strong> anuncios.</p>
        
        <table style="width:100%; border-collapse: collapse; margin-top: 15px;">
          <tr style="background-color: #ecf0f1;">
            <th style="padding: 10px; border: 1px solid #bdc3c7;">Coche</th>
            <th style="padding: 10px; border: 1px solid #bdc3c7;">Precio</th>
            <th style="padding: 10px; border: 1px solid #bdc3c7;">Enlace</th>
          </tr>
    """
    
    # Limitamos a 20 coches para no saturar el correo de prueba
    for car in cars_found[:20]:
        html_content += f"""
          <tr>
            <td style="padding: 10px; border: 1px solid #bdc3c7;">{car['title']}</td>
            <td style="padding: 10px; border: 1px solid #bdc3c7; font-weight:bold;">{car['price']}</td>
            <td style="padding: 10px; border: 1px solid #bdc3c7; text-align: center;">
                <a href="{car['url']}" style="background-color: #13c1ac; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px;">Ver</a>
            </td>
          </tr>
        """
        
    if len(cars_found) > 20:
        html_content += f"<tr><td colspan='3' style='padding:10px; text-align:center;'>... y {len(cars_found)-20} más ...</td></tr>"

    html_content += """
        </table>
        <p style='color:red; font-weight:bold;'>RECUERDA: Cambia DIAS_ATRAS = 1 en el script para uso diario.</p>
      </body>
    </html>
    """

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
        print("📧 CORREO DE PRUEBA ENVIADO CORRECTAMENTE.")
    except Exception as e:
        print(f"❌ Error enviando email: {e}")

def main():
    print(f"🚀 INICIANDO MODO PRUEBA (Mirando {DIAS_ATRAS} días atrás)...")
    print(f"📂 Zonas cargadas: {len(URLS_BUSQUEDA)}")

    all_found_cars = []
    seen_ids = set()
    
    # AQUÍ ESTÁ LA CLAVE DEL CAMBIO DE FECHA
    cutoff_date = datetime.now() - timedelta(days=DIAS_ATRAS)

    for i, url in enumerate(URLS_BUSQUEDA):
        print(f"--- Analizando zona {i+1}/{len(URLS_BUSQUEDA)} ---")
        items = get_wallapop_listings(url)
        
        count_zone = 0
        for item in items:
            item_id = item.get('id')
            if item_id in seen_ids: continue
            seen_ids.add(item_id)

            ts = item.get('creationDate')
            if ts and datetime.fromtimestamp(ts / 1000) > cutoff_date:
                price = item.get('price', 0)
                if isinstance(price, dict): price = price.get('amount', 0)
                
                all_found_cars.append({
                    'title': item.get('title', '').strip(),
                    'price': f"{price}€",
                    'url': f"https://es.wallapop.com/item/{item.get('web_slug','')}"
                })
                count_zone += 1
        
        print(f"   ✅ Encontrados: {count_zone}")

    print(f"🏁 Total global: {len(all_found_cars)}")
    
    if all_found_cars:
        send_email_report(all_found_cars)
    else:
        print("📭 Increíble, pero no hay nada ni siquiera en 30 días. Revisa los filtros de la URL.")

if __name__ == "__main__":
    main()
