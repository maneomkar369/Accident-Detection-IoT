"""
gps_manager.py — Location provider with gpsd + IP geolocation fallback.
Falls back to configured default coordinates (Pune) if both methods fail.
"""

import requests
import subprocess
import time
from config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE


class GPSManager:

    def __init__(self):
        self._last = (DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
        self._gpsd  = self._check_gpsd()
        method = "gpsd (hardware)" if self._gpsd else "IP geolocation (fallback)"
        print(f"[GPS] ✅ Using {method}")

    def _check_gpsd(self) -> bool:
        try:
            r = subprocess.run(["gpspipe", "-w", "-n", "1"],
                               capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

    def _from_gpsd(self):
        try:
            import gps as gps_lib
            s = gps_lib.gps(mode=gps_lib.WATCH_ENABLE | gps_lib.WATCH_NEWSTYLE)
            for _ in range(10):
                r = s.next()
                if r['class'] == 'TPV':
                    lat = getattr(r, 'lat', None)
                    lon = getattr(r, 'lon', None)
                    if lat and lon:
                        s.close()
                        return float(lat), float(lon)
            s.close()
        except Exception as e:
            print(f"[GPS] gpsd error: {e}")
        return None, None

    def _from_ip(self):
        try:
            r = requests.get("https://ipinfo.io/json", timeout=5)
            loc = r.json().get("loc", "")
            if "," in loc:
                lat, lon = loc.split(",")
                return float(lat), float(lon)
        except Exception as e:
            print(f"[GPS] IP geolocation error: {e}")
        return None, None

    def get_location(self):
        """Returns (lat, lon). Never fails — uses cached or default values."""
        lat, lon = self._from_gpsd() if self._gpsd else self._from_ip()

        if lat is not None:
            self._last = (lat, lon)
            print(f"[GPS] 📍 {lat:.5f}, {lon:.5f}")
        else:
            lat, lon = self._last
            print(f"[GPS] ⚠️  Using {'cached' if self._last != (DEFAULT_LATITUDE, DEFAULT_LONGITUDE) else 'default'} location: {lat}, {lon}")
        return lat, lon

    def get_maps_url(self):
        lat, lon = self.get_location()
        return f"https://www.google.com/maps?q={lat},{lon}", lat, lon
