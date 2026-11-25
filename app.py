"""
Field Shift: Adapting Farms with NASA Data
-------------------------------------------
Spatial Virtual Farm Simulation & Decision-Support System
Featuring:
- Real-time Deep NASA Earth Observations (NASA POWER / MERRA-2 / GEOS)
- Parameters: Temperature, Precipitation, Root/Surface Soil Wetness, Solar Insolation,
  Wind Speed, Humidity, Dew Point, VPD (Vapor Pressure Deficit), GDD (Growing Degree Days)
- "Orien" The Minecraft Enderman Agro-Advisor Bot
- Gamified Adaptive Crop Rotation Engine & Spatial HUD
"""

import os
import csv
import json
import math
import secrets
from datetime import datetime, timedelta
import requests
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

NASA_POWER_ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"

PRESET_FARMS = [
    {
        "id": "punjab",
        "name": "Punjab Green Valley, India",
        "lat": 30.9010,
        "lon": 75.8573,
        "region_desc": "Intense pre-monsoon heatwaves & severe groundwater table drop",
        "crop_system": "Rice-Wheat Intensive",
        "recommended_shift": "Pearl Millet (Bajra) + Moong Bean Intercrop"
    },
    {
        "id": "california",
        "name": "Central Valley, California, USA",
        "lat": 36.7378,
        "lon": -119.7871,
        "region_desc": "Mediterranean summer drought & groundwater overdraft",
        "crop_system": "Almonds / Processing Tomatoes",
        "recommended_shift": "Grain Sorghum + Crimson Clover Mulch"
    },
    {
        "id": "iowa",
        "name": "Iowa Corn Belt, USA",
        "lat": 42.0308,
        "lon": -93.6319,
        "region_desc": "Intense convective downpours & topsoil nutrient runoff",
        "crop_system": "Continuous Corn / Soy",
        "recommended_shift": "No-Till Soy + Cereal Rye + Tillage Radish"
    },
    {
        "id": "kenya",
        "name": "Great Rift Valley, Kenya",
        "lat": -0.3031,
        "lon": 36.0800,
        "region_desc": "Erratic rainy season onset & dry soil crusting",
        "crop_system": "Smallholder Maize Monoculture",
        "recommended_shift": "Drought-Hardy Cowpea + Pigeon Pea + Sorghum"
    },
    {
        "id": "brazil",
        "name": "Cerrado Agricultural Core, Brazil",
        "lat": -12.5503,
        "lon": -55.7214,
        "region_desc": "High tropical solar radiation & rapid soil moisture leaching",
        "crop_system": "Soybean / Cotton Double Crop",
        "recommended_shift": "Sunn Hemp Green Manure + Brachiaria Grass Armor"
    }
]

def calculate_vpd(temp_c, rh_pct):
    """Calculate Vapor Pressure Deficit (VPD in kPa) - crucial for plant water stress."""
    es = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * (rh_pct / 100.0)
    return max(0.0, es - ea)

@app.route("/")
def index():
    return render_template("index.html", presets=PRESET_FARMS)

@app.route("/api/fetch-nasa", methods=["POST"])
def fetch_nasa():
    try:
        data = request.get_json(force=True)
        lat = float(data.get("lat", 30.9010))
        lon = float(data.get("lon", 75.8573))
        start_date = data.get("start", "2024-05-01")
        end_date = data.get("end", "2024-05-25")

        start_fmt = start_date.replace("-", "")
        end_fmt = end_date.replace("-", "")

        # Extended Suite of NASA POWER Agroclimatology parameters
        params = [
            "T2M",               # Temperature at 2m (°C)
            "T2M_MAX",           # Maximum Daily Temperature (°C)
            "T2M_MIN",           # Minimum Daily Temperature (°C)
            "PRECTOTCORR",       # Corrected Precipitation (mm/day)
            "GWETROOT",          # Root Zone Soil Wetness (0 to 1 fraction)
            "GWETTOP",           # Surface Soil Wetness (0 to 1 fraction)
            "ALLSKY_SFC_SW_DWN", # Solar Radiation (MJ/m^2/day)
            "RH2M",              # Relative Humidity at 2m (%)
            "WS2M",              # Wind Speed at 2m (m/s)
            "T2MDEW"             # Dew/Frost Point Temperature (°C)
        ]

        nasa_url = (
            f"{NASA_POWER_ENDPOINT}"
            f"?parameters={','.join(params)}"
            f"&community=AG"
            f"&longitude={lon}"
            f"&latitude={lat}"
            f"&start={start_fmt}"
            f"&end={end_fmt}"
            f"&format=JSON"
        )

        resp = requests.get(nasa_url, timeout=25)
        if resp.status_code != 200:
            return jsonify({"success": False, "error": f"NASA API error {resp.status_code}: {resp.text[:120]}"}), 400

        nasa_json = resp.json()
        param_dict = nasa_json.get("properties", {}).get("parameter", {})

        dates = sorted(list(param_dict.get("T2M", {}).keys()))
        records = []

        temps, max_temps, precips, root_soils, top_soils = [], [], [], [], []
        solar_list, humidities, winds, vpds = [], [], [], []
        gdd_sum = 0.0
        heatwave_days = 0

        for d in dates:
            formatted_date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            t = param_dict.get("T2M", {}).get(d)
            t_max = param_dict.get("T2M_MAX", {}).get(d)
            t_min = param_dict.get("T2M_MIN", {}).get(d)
            p = param_dict.get("PRECTOTCORR", {}).get(d)
            gwet_r = param_dict.get("GWETROOT", {}).get(d)
            gwet_t = param_dict.get("GWETTOP", {}).get(d)
            solar = param_dict.get("ALLSKY_SFC_SW_DWN", {}).get(d)
            rh = param_dict.get("RH2M", {}).get(d)
            ws = param_dict.get("WS2M", {}).get(d)
            dew = param_dict.get("T2MDEW", {}).get(d)

            valid_t = t if (t is not None and t > -900) else 25.0
            valid_t_max = t_max if (t_max is not None and t_max > -900) else valid_t + 5
            valid_t_min = t_min if (t_min is not None and t_min > -900) else valid_t - 5
            valid_p = max(0.0, p) if (p is not None and p >= 0) else 0.0
            valid_gwet_r = gwet_r if (gwet_r is not None and gwet_r >= 0) else 0.45
            valid_gwet_t = gwet_t if (gwet_t is not None and gwet_t >= 0) else 0.40
            valid_solar = solar if (solar is not None and solar >= 0) else 18.0
            valid_rh = rh if (rh is not None and rh >= 0) else 50.0
            valid_ws = ws if (ws is not None and ws >= 0) else 2.5
            valid_dew = dew if (dew is not None and dew > -900) else valid_t - 8

            # Calculate agronomic metrics
            vpd = calculate_vpd(valid_t, valid_rh)
            gdd = max(0.0, ((valid_t_max + valid_t_min) / 2.0) - 10.0) # Base 10°C for crops
            gdd_sum += gdd

            if valid_t_max >= 38.0:
                heatwave_days += 1

            temps.append(valid_t)
            max_temps.append(valid_t_max)
            precips.append(valid_p)
            root_soils.append(valid_gwet_r)
            top_soils.append(valid_gwet_t)
            solar_list.append(valid_solar)
            humidities.append(valid_rh)
            winds.append(valid_ws)
            vpds.append(vpd)

            records.append({
                "date": formatted_date,
                "temp": round(valid_t, 1),
                "temp_max": round(valid_t_max, 1),
                "temp_min": round(valid_t_min, 1),
                "precip": round(valid_p, 1),
                "soil_root_pct": round(valid_gwet_r * 100, 1),
                "soil_top_pct": round(valid_gwet_t * 100, 1),
                "solar": round(valid_solar, 1),
                "humidity": round(valid_rh, 1),
                "wind_speed": round(valid_ws, 1),
                "vpd_kpa": round(vpd, 2),
                "dew_point": round(valid_dew, 1),
                "gdd": round(gdd, 1)
            })

        avg_temp = round(sum(temps) / len(temps), 1) if temps else 25.0
        peak_max_temp = round(max(max_temps), 1) if max_temps else 32.0
        total_precip = round(sum(precips), 1)
        avg_root_soil = round((sum(root_soils) / len(root_soils)) * 100, 1) if root_soils else 50.0
        avg_top_soil = round((sum(top_soils) / len(top_soils)) * 100, 1) if top_soils else 45.0
        avg_solar = round(sum(solar_list) / len(solar_list), 1) if solar_list else 18.0
        avg_humidity = round(sum(humidities) / len(humidities), 1) if humidities else 50.0
        avg_wind = round(sum(winds) / len(winds), 1) if winds else 2.5
        avg_vpd = round(sum(vpds) / len(vpds), 2) if vpds else 1.2

        # Soil & Climate Threat Diagnostics
        drought_alert = avg_root_soil < 35 or total_precip < 25
        heat_alert = peak_max_temp >= 38 or heatwave_days >= 3
        high_transpiration = avg_vpd > 2.0

        if drought_alert and heat_alert:
            climate_status = "Critical Arid Heatwave (High Crop Evaporative Strain)"
            recommended_primary = "Pearl Millet (Bajra) / Grain Sorghum"
            recommended_secondary = "Cowpea / Chickpea (Deep Taproot Legume)"
            water_savings = 42
        elif drought_alert:
            climate_status = "Moderate Drought (Soil Wetness Deficit)"
            recommended_primary = "Grain Sorghum / Sunflower"
            recommended_secondary = "Moong Bean / Lentil"
            water_savings = 35
        elif total_precip > 160:
            climate_status = "High Rainfall Runoff & Nutrient Washout Threat"
            recommended_primary = "No-Till Soy with Stubble Retention"
            recommended_secondary = "Cereal Rye & Deep Radish Bio-Drill"
            water_savings = 20
        else:
            climate_status = "Balanced Growing Season"
            recommended_primary = "High-Yield Maize / Canola Hybrid"
            recommended_secondary = "Pigeon Pea / Crimson Clover"
            water_savings = 25

        summary = {
            "avg_temp": avg_temp,
            "peak_max_temp": peak_max_temp,
            "total_precip": total_precip,
            "avg_root_soil": avg_root_soil,
            "avg_top_soil": avg_top_soil,
            "avg_solar": avg_solar,
            "avg_humidity": avg_humidity,
            "avg_wind": avg_wind,
            "avg_vpd": avg_vpd,
            "total_gdd": round(gdd_sum, 1),
            "heatwave_days": heatwave_days,
            "total_days": len(records),
            "climate_status": climate_status,
            "recommended_primary": recommended_primary,
            "recommended_secondary": recommended_secondary,
            "water_savings_pct": water_savings
        }

        # Save structured telemetry CSV for hackathon verification
        csv_filename = f"nasa_field_shift_{lat}_{lon}_{start_fmt}_{end_fmt}.csv"
        csv_path = os.path.join(DATA_DIR, csv_filename)
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date", "Temp_C", "Max_Temp_C", "Min_Temp_C", "Precipitation_mm",
                "Root_Soil_Moisture_Pct", "Surface_Soil_Moisture_Pct", "Solar_Radiation_MJ_m2",
                "Humidity_Pct", "Wind_Speed_m_s", "VPD_kPa", "Dew_Point_C", "GDD_Base10"
            ])
            for r in records:
                writer.writerow([
                    r["date"], r["temp"], r["temp_max"], r["temp_min"], r["precip"],
                    r["soil_root_pct"], r["soil_top_pct"], r["solar"],
                    r["humidity"], r["wind_speed"], r["vpd_kpa"], r["dew_point"], r["gdd"]
                ])

        return jsonify({
            "success": True,
            "location": {"lat": lat, "lon": lon},
            "summary": summary,
            "records": records,
            "csv_file": csv_filename
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/ask-orien", methods=["POST"])
def ask_orien():
    """
    Orien The Minecraft Enderman Agro-Advisor
    Intelligent response engine backed by real agronomy and the active NASA telemetry.
    """
    try:
        req = request.get_json(force=True)
        user_msg = req.get("message", "").strip().lower()
        context = req.get("context", {})

        # Extract active telemetry context if available
        avg_temp = context.get("avg_temp", 28.0)
        peak_temp = context.get("peak_max_temp", 36.0)
        total_precip = context.get("total_precip", 40.0)
        root_soil = context.get("avg_root_soil", 30.0)
        vpd = context.get("avg_vpd", 1.8)
        primary_crop = context.get("recommended_primary", "Pearl Millet (Bajra)")

        # Orien's Intelligent Knowledge Base
        if any(w in user_msg for w in ["who are you", "who r u", "name", "orien"]):
            reply = (
                "✦ *Vwoop!* I am **Orien**, your Enderman Agro-Advisor! I dwell between the void of space and your virtual soil. "
                "I decipher real-time NASA satellite beams (POWER, MERRA-2, GEOS) and translate them into simple, battle-tested "
                "crop rotation tactics so your farm survives any heatwave or drought!"
            )
        elif any(w in user_msg for w in ["thirsty", "dry", "moisture", "water", "irrigation"]):
            reply = (
                f"✦ *Teleporting into your soil pores...* NASA MERRA-2 reports your root-zone soil wetness is currently **{root_soil}%**! "
                f"If you're growing high-water crops like conventional rice or thirsty maize, your water table is vanishing fast. "
                f"**Orien's Tactic:** Shift at least one plot to **{primary_crop}** or intercrop with **Cowpeas**. Their deep taproots "
                "act like biological drills, sucking deep water without needing continuous flood irrigation!"
            )
        elif any(w in user_msg for w in ["heat", "hot", "temperature", "heatwave", "sun"]):
            reply = (
                f"✦ *Eyes glowing violet!* NASA telemetry reveals peak temperatures hit **{peak_temp}°C** with high solar radiation. "
                f"High temperatures spike your Vapor Pressure Deficit (VPD is ~{vpd} kPa), making plants sweat out water faster than roots can drink. "
                "**Orien's Tactic:** Plant **Sunn Hemp or Clover cover crops**! They create a living green blanket over the soil that drops soil temperature by up to 6°C!"
            )
        elif any(w in user_msg for w in ["crop", "plant", "rotate", "shift", "seed", "recommend"]):
            reply = (
                f"✦ *Shuffling the Ender Seed Deck!* Based on the satellite climate scan, your best adaptation strategy is:\n"
                f"1. **Phase 1 (Cash Crop):** {primary_crop} — thrives in heat, cuts water consumption by 35-40%.\n"
                f"2. **Phase 2 (Soil Recharge):** Moong Bean or Cowpea — fixes 60-80 kg of atmospheric nitrogen per hectare.\n"
                f"3. **Phase 3 (Soil Shield):** Sunn Hemp & Cereal Rye — locks topsoil in place and halts wind erosion!"
            )
        elif any(w in user_msg for w in ["nasa", "satellite", "data", "source", "how"]):
            reply = (
                "✦ *Vwooop! Beaming from orbit!* We stream daily satellite observations straight from NASA Langley Research Center "
                "via the **NASA POWER Agroclimatology API** and **MERRA-2 assimilation model**. We track solar flux (ALLSKY_SFC_SW_DWN), "
                "precipitation anomalies (PRECTOTCORR), and root-zone wetness (GWETROOT) without guesswork!"
            )
        elif any(w in user_msg for w in ["vpd", "vapor"]):
            reply = (
                f"✦ **Vapor Pressure Deficit (VPD)** is the drying power of the air. Your field's current VPD is **{vpd} kPa**. "
                "When VPD climbs above 2.0 kPa, plant stomata snap shut to prevent dehydration, which stops crop growth in its tracks! "
                "Cover crops and high-albedo mulches keep your microclimate humid and cool."
            )
        elif any(w in user_msg for w in ["xp", "game", "score", "level"]):
            reply = (
                "✦ *Ding!* Every time you tap **'Shift Crop'** to replace an endangered high-water crop with a resilient legume or millet, "
                "you gain **+50 to +80 Resilience XP** and add to your **Liters of Water Saved** tally! Level up from Apprentice Grower to NASA Agro-Guardian!"
            )
        elif any(w in user_msg for w in ["help", "what can you do", "commands"]):
            reply = (
                "✦ I can assist you with:\n"
                "• **Soil Moisture & Water Stress** — type *'Why is my field thirsty?'*\n"
                "• **Extreme Heat & VPD** — type *'How hot is it?'*\n"
                "• **Crop Adaptation Strategy** — type *'What should I plant?'*\n"
                "• **NASA Satellite Science** — type *'How does NASA read my farm?'*"
            )
        else:
            reply = (
                f"✦ *Vwoop!* Orien hears you, grower! Looking at your live NASA observations (Avg Temp: **{avg_temp}°C**, Root Moisture: **{root_soil}%**), "
                f"the most critical action right now is keeping your soil covered and rotating in **{primary_crop}** to bank groundwater for tomorrow. "
                "Ask me about crop rotation, drought alerts, or NASA satellite data!"
            )

        return jsonify({"success": True, "reply": reply})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/download-csv/<filename>")
def download_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=filename)
    return "File not found", 404

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
