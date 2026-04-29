<div align="center">
  <img src="Nexus_Logo.png" alt="Nexus Logo" width="300">
</div>

<h1 align="center">Nexus - Anomaly Detector for Asentinel</h1>

<div align="center">
  <a href="README.md">English</a> | <strong>Indonesia</strong>
</div>

Mendeteksi anomali pada data pemantauan kesehatan API menggunakan **Isolation Forest**.

## Cara Kerjanya

1. Data pemantauan mentah masuk (dari CSV atau database)
2. Fitur direkayasa dari data mentah (`feature_engineer.py`)
3. Model Isolation Forest menilai setiap catatan (record)
4. Jika skor catatan berada di bawah ambang batas (threshold), catatan tersebut mendapat **strike**, tetapi belum ditandai sebagai anomali
5. Hanya setelah **3 strike berturut-turut**, endpoint tersebut dikonfirmasi sebagai anomali dan dicatat
6. Untuk pulih, endpoint harus melewati **3 pemeriksaan normal berturut-turut**
7. Setiap 12 jam (selama pelatihan ulang/retraining), `summarizer.py` mengelompokkan anomali ke dalam ringkasan dan membersihkan log.
8. Endpoint `/recommend` meneruskan ringkasan ke Groq LLM (`engine.py`) untuk menghasilkan rencana perbaikan teknis.

Sistem strike ini mencegah alarm palsu akibat lonjakan lag sementara. Dapat dikonfigurasi melalui `CONFIRM_STRIKES` dan `RECOVER_STRIKES` di `config.py`.

## Struktur Proyek

| File | Fungsi |
|------|-------------|
| `config.py` | Semua pengaturan (path, DB, parameter model, jadwal, konfigurasi LLM) |
| `detector.py` | Mesin deteksi utama (digunakan oleh file lainnya) |
| `feature_engineer.py` | Membangun fitur dari data pemantauan mentah |
| `nexus.py` | Server FastAPI dengan endpoint deteksi dan rekomendasi |
| `retrain_scheduler.py` | Melatih ulang model dari CSV atau DB (serta memicu summarizer) |
| `batch_detector.py` | Deteksi batch dari CSV (dev) atau polling DB (prod) |
| `summarizer.py` | Mengelompokkan log anomali 12 jam menjadi ringkasan JSON |
| `engine.py` | Berinteraksi dengan Groq API (LLM) untuk menghasilkan rekomendasi |
| `run.py` | Menu CLI interaktif untuk menjalankan bagian mana pun dari sistem dengan mudah |

## Persiapan Setup

1. Salin `.env.example` ke `.env` (atau buat file `.env` baru) dan isi kredensial DB Anda dan `GROQ_API_KEY`.
2. Instal dependencies:
```bash
pip install -r requirements.txt
```

## Penggunaan

Cara termudah untuk menjalankan bagian mana pun dari proyek ini adalah menggunakan menu CLI interaktif:

```bash
python run.py
```

Menu ini memungkinkan Anda untuk dengan mudah memilih dan menjalankan deteksi batch, deteksi tunggal interaktif, memulai server API, atau melatih ulang model.

### Eksekusi Manual

**Mulai server API (PENTING: gunakan file `.env` agar Python dapat membaca API key):**
```bash
uvicorn nexus:app --reload --env-file .env
```

**Latih ulang (retrain) model:**
```bash
python retrain_scheduler.py
```

**Latih ulang model (setiap 12 jam):**
```bash
python retrain_scheduler.py --loop
```

**Jalankan deteksi batch dari CSV:**
```bash
python batch_detector.py
```

**Jalankan deteksi batch dari DB (ketika DB sudah siap):**
```bash
python batch_detector.py --poll
```

## Database

Sistem ini sudah siap untuk koneksi database. Saat DB Anda sudah di-host:

1. Atur `DB_ENABLED = True` di `config.py`
2. Isi `DB_CONFIG` dengan kredensial Anda (atau gunakan `.env`)
3. Tabel `log_monitor` harus memiliki kolom-kolom berikut (**PENTING** jika tidak sistem akan gagal):
   `id_log_monitor`, `id_aplikasi`, `id_service`, `url`, `status`, `http_status_code`, `response_time_ms`, `checked_at`, `created_at`, `updated_at`
