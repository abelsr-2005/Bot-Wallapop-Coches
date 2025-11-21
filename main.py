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

# --- CONFIGURACIÓN DE ENTORNO ---
EMAIL_SENDER = os.environ["EMAIL_USER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASS"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]

# IMPORTANTE: Aquí usamos ";" como separador para evitar romper las URLs de Wallapop
raw_urls = os.environ["WALLAPOP_URLS"]
URLS_BUSQUEDA = [url.strip() for url in raw_urls.split(";") if url.strip()]

def get_wallapop_listings(search_url):
    """
    Descarga el HTML de Wallapop y extrae el JSON de datos (__NEXT_DATA__)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    
    print(f"🌐 Consultando URL...")
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Error HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Wallapop guarda los datos en un script JSON hidratado
        script_data = soup.find("script", {"id": "__NEXT_DATA__"})
        
        if script_data:
            json_data = json.loads(script_data.string)
            try:
                # Ruta al array de productos en la estructura de Wallapop
                items = json_data['props']['pageProps']['searchObjects']
                return items
            except KeyError:
                print("⚠️ No se encontró la clave 'searchObjects' en el JSON.")
                return []
        else:
            print("⚠️ No se encontró el script __NEXT_DATA__ (posible bloqueo antibot).")
            return []
            
    except Exception as e:
        print(f"❌ Excepción durante el scraping: {e}")
        return []

def send_email_report(cars_found):
    """
    Envía el correo electrónico formateado en HTML
    """
    if not cars_found:
        return

    subject = f"🚗 Wallapop: {len(cars_found)} nuevos coches detectados"
    
    # Estilo CSS inline para el correo
    html_content = """
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #13c1ac;">🏎️ Oportunidades del día</h2>
        <p>Estos son los coches publicados en las últimas 24h en Huelva, Sevilla o Cádiz que cumplen tus criterios:</p>
        
        <table style="width:100%; border-collapse: collapse; margin-top: 20px;">
          <thead>
            <tr style="background-color: #f8f9fa; text-align: left;">
              <th style="padding: 12px; border-bottom: 2px solid #ddd;">Coche</th>
              <th style="padding: 12px; border-bottom: 2px solid #ddd;">Precio</th>
              <th style="padding: 12px; border-bottom: 2px solid #ddd;">Enlace</th>
            </tr>
          </thead>
          <tbody>
    """
    
    for car in cars_found:
        html_content += f"""
            <tr>
              <td style="padding: 12px; border-bottom: 1px solid #eee;">
                <strong>{car['title']}</strong><br>
                <span style="font-size: 12px; color: #666;">Ref: {car['id']}</span>
              </td>
              <td style="padding: 12px; border-bottom: 1px solid #eee; font-size: 16px; font-weight: bold; color: #333;">
                {car['price']}
              </td>
              <td style="padding: 12px; border-bottom: 1px solid #eee;">
                <a href="{car['url']}" style="background-color: #13c1ac; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px;">Ver Coche</a>
              </td>
            </tr>
        """

    html_content += """
          </tbody>
        </table>
        <p style="margin-top: 30px; font-size: 12px; color: #999;">
            Bot ejecutado automáticamente por Github Actions.<br>
            Criterios: Audi/BMW/Mercedes, >142cv, >2008, 3k-11k €.
        </p>
      </body>
    </html>
    """

    # Configuración del mensaje
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg.attach(MIMEText(html_content, "html"))

    # Envío
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("✅ Correo electrónico enviado correctamente.")
    except Exception as e:
        print(f"❌ Error enviando el correo: {e}")

def main():
    print(f"🚀 Iniciando bot de búsqueda...")
    print(f"📂 Se han cargado {len(URLS_BUSQUEDA)} zonas de búsqueda.")

    all_found_cars = []
    processed_ids = set()
    
    # Definir el límite de tiempo (Ayer a esta misma hora)
    yesterday = datetime.now() - timedelta(days=1)
    print(f"🕒 Buscando anuncios posteriores a: {yesterday.strftime('%Y-%m-%d %H:%M:%S')}")

    for i, url in enumerate(URLS_BUSQUEDA):
        print(f"\n--- Procesando URL {i+1}/{len(URLS_BUSQUEDA)} ---")
        
        items = get_wallapop_listings(url)
        print(f"📦 Se recibieron {len(items)} anuncios brutos de esta zona.")
        
        count_new = 0
        
        for item in items:
            # Evitar duplicados entre provincias
            item_id = item.get('id')
            if item_id in processed_ids:
                continue
            processed_ids.add(item_id)

            # Comprobar fecha
            try:
                # Wallapop devuelve timestamp en milisegundos
                creation_ts = item.get('creationDate')
                if not creation_ts: 
                    continue
                
                listing_date = datetime.fromtimestamp(creation_ts / 1000)
                
                # LÓGICA PRINCIPAL: ¿Es nuevo?
                if listing_date > yesterday:
                    # Formatear precio
                    price = item.get('price', 0)
                    if isinstance(price, (int, float)):
                        price_str = f"{price:,.0f} €".replace(",", ".")
                    else:
                        price_str = str(price)

                    car_data = {
                        'id': item_id,
                        'title': item.get('title', 'Sin título').strip(),
                        'price': price_str,
                        'url': f"https://es.wallapop.com/item/{item.get('web_slug','')}"
                    }
                    
                    all_found_cars.append(car_data)
                    count_new += 1
                    # Debug
                    print(f"   ⭐ NUEVO: {car_data['title']} ({price_str}) - {listing_date}")
            
            except Exception as e:
                print(f"   Error procesando item {item_id}: {e}")
                continue
        
        if count_new == 0:
            print("   ℹ️ Ningún coche nuevo en esta zona.")
            
        # Pequeña pausa para ser amables con el servidor
        time.sleep(2)

    print(f"\n🏁 Finalizado. Total coches nuevos encontrados: {len(all_found_cars)}")
    
    if all_found_cars:
        send_email_report(all_found_cars)
    else:
        print("📭 No se envía correo porque no hay novedades.")

if __name__ == "__main__":
    main()
