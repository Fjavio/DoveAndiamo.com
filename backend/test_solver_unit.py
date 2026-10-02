from core.solver import ItinerarySolver

def test_calcolo_minuti_mezzanotte():
    solver = ItinerarySolver()
    
    # Test caso normale
    assert solver._minuti("20:30") == 20 * 60 + 30
    
    # Test varco di mezzanotte (es. le 02:00 devono valere +24h)
    assert solver._minuti("02:00") == 26 * 60

def test_distanza_haversine():
    solver = ItinerarySolver()
    
    # Coordinate fittizie: Napoli (Piazza Plebiscito) a Roma (Colosseo)
    distanza = solver._calcola_distanza_haversine(40.8359, 14.2487, 41.8902, 12.4922)
    
    # La distanza in linea d'aria è circa 188 km
    assert 180.0 < distanza < 195.0