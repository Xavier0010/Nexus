<div align="center">
  <img src="/assets/Nexus_Logo.png" alt="Nexus Logo" width="300">
</div>

<h1 align="center">Nexus - Anomaly Detector for Asentinel</h1>

<div align="center">
  <a href="README.md">English</a> | <strong>Indonesia</strong>
</div>

Mendeteksi anomali pada data pemantauan kesehatan API menggunakan **Isolation Forest**.

## Cara Kerjanya

1. Data pemantauan mentah masuk (dari CSV atau database)
2. Fitur direkayasa dari data mentah (`feature_engineer.py`)
3. Model Isolation Forest menilai setiap record
4. Jika skor di bawah threshold, endpoint mendapat **strike** — belum ditandai sebagai anomali
5. Setelah **3 strike berturut-turut**, endpoint dikonfirmasi sebagai anomali dan dicatat
6. Untuk pulih, endpoint harus melewati **3 pemeriksaan normal berturut-turut**
7. Anomali yang dikonfirmasi diklasifikasikan berdasarkan prioritas: **CRITICAL** (dikirim langsung) atau **WARNING** (dikirim setiap 3 menit)
8. Laporan ringkasan harian dan mingguan dibuat secara otomatis oleh scheduler di `main.py`
9. Endpoint `/recommend` meneruskan log anomali terbaru ke LLM untuk menghasilkan rencana perbaikan teknis

> Strike mencegah alarm palsu akibat lonjakan sementara. Dapat dikonfigurasi melalui `CONFIRM_STRIKES` dan `RECOVER_STRIKES` di `config.py`.

## Struktur Proyek

| File / Module | Fungsi |
|---|---|
| `config.py` | Semua pengaturan (path, DB, parameter model, jadwal, webhook, LLM) |
| `nexus.py` | Server FastAPI — endpoint deteksi, ringkasan, dan rekomendasi |
| `main.py` | Entry point produksi — menjalankan deteksi DB, retrain per jam, dan scheduler ringkasan harian/mingguan di background thread |
| `run.py` | Menu CLI interaktif untuk menjalankan bagian mana pun dari sistem secara manual |
| `anomaly_detector/detector.py` | Mesin deteksi utama (state machine strike/recovery) |
| `anomaly_detector/feature_engineer.py` | Membangun fitur dari data pemantauan mentah |
| `anomaly_detector/batch_detector.py` | Deteksi batch dari CSV (dev) atau polling DB (prod) |
| `anomaly_detector/retrain_scheduler.py` | Melatih ulang model sesuai permintaan atau jadwal |
| `webhook/notifier.py` | Mengirim alert Telegram (CRITICAL langsung, WARNING digest) |
| `webhook/priority_classifier.py` | Mengklasifikasikan anomali konfirmasi sebagai CRITICAL atau WARNING |
| `report/daily_summary.py` | Membuat ringkasan anomali harian dari log (one-shot) |
| `report/weekly_summary.py` | Mengagregasi N ringkasan harian terakhir menjadi laporan mingguan (one-shot) |
| `report/engine.py` | Mengirim ringkasan ke LLM dan mengembalikan rencana perbaikan |

## Persiapan Setup

1. Salin `.env.example` ke `.env` dan isi kredensial DB serta LLM API key Anda.
2. Instal dependencies:
```bash
pip install -r requirements.txt
```

## Penggunaan

Nexus dapat digunakan dengan tiga cara:

### 1. Scheduler Produksi (`main.py`)

Cara yang direkomendasikan untuk menjalankan Nexus di produksi (misalnya di dalam Docker). Menjalankan tiga background thread:
- **Loop deteksi DB** — polling database setiap `FETCH_INTERVAL_SECONDS` untuk record baru
- **Retrain per jam** — melatih ulang model setiap jam
- **Ringkasan harian/mingguan** — membuat ringkasan harian di tengah malam; juga membuat ringkasan mingguan setiap hari Minggu

```bash
python main.py
```

### 2. CLI Interaktif (`run.py`)

Untuk pengembangan lokal dan penggunaan operasional. Jalankan menu interaktif:

```bash
python run.py
```

Dari menu ini Anda dapat menjalankan deteksi batch (CSV atau DB), deteksi tunggal, retrain model, membuat laporan, dan mengelola log — semua dari satu tempat.

### 3. API Endpoint (`nexus.py`)

Untuk sistem eksternal (misalnya backend Asentinel) yang ingin mengirim satu record dan mendapatkan hasil deteksi anomali secara langsung. Jalankan server API:

```bash
uvicorn nexus:app --reload --env-file .env
```

Kemudian kirim request `POST` ke `/detect` dengan satu record pemantauan. Lihat `NEXUS API DOCUMENTATION.md` untuk referensi endpoint lengkap.

## Database

Saat DB Anda sudah di-host:

1. Atur `DB_ENABLED = True` di `config.py`
2. Isi kredensial DB di `.env`
3. Tabel `log_monitor` harus memiliki kolom berikut:
   `id_log_monitor`, `id_aplikasi`, `nama`, `id_service`, `url`, `status`, `http_status_code`, `response_time_ms`, `checked_at`, `created_at`, `updated_at`

## Notifikasi Webhook

Anomali yang dikonfirmasi dikirim ke Telegram dengan dua tingkatan prioritas:

| Prioritas | Pemicu | Perilaku |
|---|---|---|
| 🔴 CRITICAL | Error server (5xx/0), service down, RT > 8000ms, skor parah, 10+ strike | Dikirim langsung |
| ⚠️ WARNING | Service aktif tapi drifting, skor anomali ringan | Digest setiap 3 menit |
