import os
import json
import glob
from groq import Groq
from config import DAILY_SUMMARY_DIR, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

api_key = os.getenv("API_KEY")
client = Groq(api_key=api_key) if api_key else None


def get_latest_summary():
    """Utility for nexus.py /recommend endpoint — reads newest daily summary from disk."""
    if not DAILY_SUMMARY_DIR.exists():
        return None, None

    summary_files = glob.glob(str(DAILY_SUMMARY_DIR / "*.json"))
    if not summary_files:
        return None, None

    latest_file = max(summary_files, key=os.path.getctime)
    try:
        with open(latest_file, "r") as f:
            return json.load(f), latest_file
    except Exception as e:
        print(f"[engine] Error reading summary: {e}")
        return None, None


def generate_recommendation(summary_data: dict, summary_path: str):
    """Generate LLM recommendations from a summary dict and patch them back into the file."""
    if not client:
        print("[engine] API_KEY not set — skipping recommendations.")
        return []

    if summary_data.get("overview", {}).get("total_anomaly_events", 0) == 0:
        print("[engine] No anomalies in summary — skipping recommendations.")
        return []

    overview       = summary_data.get("overview", {})
    incident_types = summary_data.get("incident_types", {})
    top_services   = summary_data.get("top_unstable_services", [])

    prompt_context = (
        f"Overview:\n{json.dumps(overview, indent=2)}\n\n"
        f"Incident Types:\n{json.dumps(incident_types, indent=2)}\n\n"
        f"Top Unstable Services:\n{json.dumps(top_services[:5], indent=2)}"
    )

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages = [
            {
                "role": "system",
                "content": (
                    "Kamu adalah AI observability dan monitoring system profesional.\n"
                    "Tugasmu adalah menganalisis anomaly monitoring report dan menghasilkan rekomendasi operasional yang singkat, teknis, jelas, dan actionable.\n\n"
        
                    "Report dapat berupa DAILY atau WEEKLY report.\n"
                    "Jika WEEKLY report, fokus pada:\n"
                    "- recurring anomalies\n"
                    "- service paling tidak stabil\n"
                    "- availability rendah\n"
                    "- repeated http errors\n"
                    "- latency berkepanjangan\n"
                    "- pola anomaly yang berulang\n\n"
        
                    "Jika DAILY report, fokus pada:\n"
                    "- anomaly paling signifikan\n"
                    "- lonjakan response time\n"
                    "- service down\n"
                    "- http error dominan\n\n"
        
                    "Prioritaskan issue dengan impact terbesar.\n"
                    "Jangan mengulang rekomendasi yang sama.\n"
                    "Gunakan insight langsung dari data yang diberikan.\n\n"
        
                    "Kamu HARUS mengembalikan output JSON valid tanpa markdown.\n\n"
        
                    "Aturan klasifikasi priority:\n"
                    "- critical: service down, banyak 5xx, atau availability turun drastis\n"
                    "- high: latency sangat tinggi atau anomaly berulang terus-menerus\n"
                    "- medium: spike response time atau http error terbatas\n"
                    "- low: anomaly kecil tanpa impact besar\n\n"
        
                    "Format output:\n"
                    "{\n"
                    '  "recommendations": [\n'
                    "    {\n"
                    '      "priority": "critical | high | medium | low",\n'
                    '      "what_happened": "deskripsi singkat masalah utama",\n'
                    '      "recommendation": "langkah remediasi teknis yang actionable"\n'
                    "    }\n"
                    "  ]\n"
                    "}\n\n"
        
                    "Buat 2-5 rekomendasi berdasarkan anomaly paling signifikan."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Berikut monitoring report:\n\n"
                    f"{prompt_context}\n\n"
                    "Analisis report tersebut dan hasilkan rekomendasi operasional."
                )
            }
        ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        recommendations = parsed.get("recommendations", [])

        summary_data["recommendations"] = recommendations
        with open(summary_path, "w") as f:
            json.dump(summary_data, f, indent=2)

        return recommendations

    except Exception as e:
        print(f"[engine] LLM generation failed: {e}")
        return []
