import requests
import json
from bs4 import BeautifulSoup
import time
import random

# Usamos UNA sola URL de prueba (Sevilla, Audi)
TEST_URL = "https://es.wallapop.com/app/search?category_ids=100&brand=Audi&min_sale_price=3000&max_sale_price=11000&min_year=2008&max_year=2025&min_horse_power=142&min_doors=5&order_by=newest&latitude=37.3886&longitude=-5.9823"

def debug_wallapop():
    print(f"🕵️ ANALIZANDO ESTRUCTURA DE: {TEST_URL}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://es.wallapop.com/"
    }

    try:
        response = requests.get(TEST_URL, headers=headers, timeout=10)
        print(f"📡 Estado HTTP: {response.status_code}")

        if response.status_code != 200:
            print("❌ Error: Wallapop rechazó la conexión.")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        script_data = soup.find("script", {"id": "__NEXT_DATA__"})

        if not script_data:
            print("⚠️ NO SE ENCONTRÓ EL SCRIPT JSON (__NEXT_DATA__).")
            print("Posible causa: Wallapop devolvió una página de 'Verificación' o HTML estático.")
            # Imprimir título de la página para ver si es un error
            print(f"Título de la página recibida: {soup.title.string if soup.title else 'Sin título'}")
            return

        print("✅ Script JSON encontrado. Analizando claves...")
        data = json.loads(script_data.string)
        
        # Navegamos paso a paso para ver dónde rompe
        props = data.get('props', {})
        page_props = props.get('pageProps', {})
        
        print(f"🔑 Claves en pageProps: {list(page_props.keys())}")
        
        if 'searchObjects' in page_props:
            items = page_props['searchObjects']
            print(f"🎉 ¡ENCONTRADO! Hay {len(items)} items en 'searchObjects'.")
            if len(items) > 0:
                print(f"Ejemplo: {items[0].get('title')} - Fecha: {items[0].get('creationDate')}")
        
        elif 'catalog' in page_props:
            items = page_props['catalog'].get('objects', [])
            print(f"🎉 ¡ENCONTRADO! Hay {len(items)} items en 'catalog'.")
        
        elif 'layoutProps' in page_props:
            print("⚠️ Estructura detectada: 'layoutProps'. Buscando dentro...")
            # A veces está muy anidado aquí
            children = page_props['layoutProps'].get('children', [])
            print(f"   Hay {len(children)} secciones en layoutProps.")
            
        else:
            print("❌ LOS DATOS NO ESTÁN EN LAS UBICACIONES HABITUALES.")

    except Exception as e:
        print(f"❌ Error fatal: {e}")

if __name__ == "__main__":
    debug_wallapop()
