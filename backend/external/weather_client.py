import requests
from datetime import datetime

class WeatherClient:
    """Boundary per il Servizio Meteo reale tramite Open-Meteo API (Pattern ECB)"""
    
    def check_rain(self, citta: str, data: datetime) -> bool:
        """
        Interroga le API reali per determinare se pioverà nella città e data indicate.
        """
        try:
            # Otteniamo le coordinate della città
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={citta}&count=1&language=it"
            geo_res = requests.get(geo_url, timeout=5)
            geo_data = geo_res.json()
            
            if not geo_data.get("results"):
                print(f"Meteo: Città {citta} non trovata. Assumo nessuna pioggia.")
                return False
                
            lat = geo_data["results"][0]["latitude"]
            lon = geo_data["results"][0]["longitude"]
            
            # Otteniamo la previsione di pioggia per i prossimi giorni
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&timezone=auto"
            weather_res = requests.get(weather_url, timeout=5)
            weather_data = weather_res.json()
            
            # Formattiamo la data per cercarla nell'array di risposta (YYYY-MM-DD)
            target_date_str = data.strftime("%Y-%m-%d")
            
            if "daily" in weather_data and target_date_str in weather_data["daily"]["time"]:
                indice_data = weather_data["daily"]["time"].index(target_date_str)
                # Se la precipitazione è maggiore di 1 millimetro, consideriamo che piove
                pioggia = weather_data["daily"]["precipitation_sum"][indice_data]
                if pioggia is not None and pioggia > 1.0:
                    return True
            
            return False
            
        except Exception as e:
            print(f"Errore durante la chiamata API Meteo: {e}")
            return False