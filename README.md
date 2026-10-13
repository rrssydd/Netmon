# Netmon Workspace v7

Netmon adalah aplikasi lokal untuk memantau CPU, memory, port, dan traffic WAN/uplink perangkat Cisco melalui SSH. Aplikasi hanya mengumpulkan perangkat yang Anda daftarkan; tidak melakukan autodiscovery.

## Menjalankan di Windows

Persyaratan: Python 3.11 atau lebih baru. Buka PowerShell di folder tempat Netmon akan disimpan, lalu jalankan:

    git clone https://github.com/rrssydd/Netmon.git
    cd Netmon
    setup_windows.bat

`setup_windows.bat` membuat virtual environment `.venv` dan memasang dependensi dari `requirements.txt` secara otomatis. Jika ingin menjalankan proses instalasi secara manual, gunakan:

    py -3 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt

Jika PowerShell memblokir aktivasi virtual environment, lewati perintah aktivasi dan gunakan:

    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Setelah setup selesai, jalankan:

    start_windows.bat

Buka http://127.0.0.1:5000. Biarkan terminal tetap berjalan selama aplikasi digunakan. Saat pertama kali membuka aplikasi, buat akun lokal sendiri; tidak ada akun bawaan. Clone baru memulai dengan database kosong.

## Menyiapkan perangkat

1. Di **Add Device & Uplinks**, daftarkan alamat management, username SSH, driver, dan collection profile perangkat.
2. Tambahkan mapping untuk setiap WAN/uplink dan isi nama interface yang benar.
3. Pastikan komputer Netmon dapat menjangkau perangkat melalui SSH (TCP port 22) dan akun memiliki hak menjalankan perintah monitoring.
4. Klik **Collect Now** pada Overview. Hasil koleksi dan waktu data terakhir membantu mengidentifikasi perangkat yang tidak terjangkau.

Password SSH dapat dimasukkan pada form perangkat atau disediakan melalui environment variable lokal. Jangan simpan password di source code.

## Menu utama

- **Overview:** ringkasan perangkat serta peak traffic harian per arah. Klik baris WAN/uplink untuk membuka grafik detail.
- **History & Trend:** pilih rentang waktu dan perangkat/uplink untuk melihat ringkasan serta grafik sampel.
- **Capture Device:** ambil dan simpan backup running-config; file konfigurasi dapat memuat informasi sensitif.
- **Import Capture:** impor output CLI berformat .txt (maksimal 5 MB). Pastikan Capture Hostname dan mapping interface sesuai dengan perangkat.

## Koleksi terjadwal dan batas traffic

Untuk menjalankan koleksi satu kali tanpa browser:

    python cron_collect.py

Untuk peak harian yang lebih mewakili kondisi jaringan, buat task di Windows Task Scheduler yang menjalankan script secara berkala, misalnya setiap 5 atau 15 menit. Gunakan Python dari folder .venv, isi **Start in** dengan folder project, dan hindari jadwal yang tumpang tindih. Komputer harus menyala, terhubung ke jaringan, dan memiliki akses ke perangkat.

Nilai traffic CLI adalah rata-rata interval perangkat (umumnya sekitar 5 menit), bukan puncak sesaat. Peak laporan adalah nilai tertinggi dari sampel yang berhasil dikumpulkan. Batas default WAN/uplink adalah 300 Mbps per arah; CPU dan memory router/switch memakai ambang terpisah.

Untuk mengubah pengaturan lokal, salin template lalu edit config/thresholds.yaml:

    Copy-Item config/thresholds.example.yaml config/thresholds.yaml

Default CPU/memory: warning 80%, critical 90%. Default traffic: warning 300 Mbps, critical 800 Mbps. Daily report dimulai pukul 08:00 waktu lokal dan menggunakan batas 300 Mbps. File thresholds.yaml lokal diabaikan oleh Git.

## Data dan keamanan

Netmon menyimpan akun, inventori perangkat, metrik, serta backup konfigurasi di database lokal. Password login disimpan sebagai hash; password SSH yang dimasukkan melalui form dan isi backup tetap berada di database lokal. Batasi akses ke komputer dan folder aplikasi, dan jangan unggah database, session key, file .env, atau capture operasional ke repository.

Untuk backup, hentikan aplikasi dan task koleksi terlebih dahulu, lalu salin netmon.db, auth.db, dan config/thresholds.yaml ke lokasi privat.

## Akun dan bantuan

Tautan pendaftaran dan lupa password tersedia di halaman login. Kode verifikasi ditampilkan di terminal aplikasi, bukan dikirim lewat email. Alternatif reset akun yang sudah ada: jalankan python reset_login.py dari folder project.

Jika data tidak bertambah, periksa koneksi SSH, kredensial, hak akses perintah, mapping interface, dan log hasil Collect. Setelah pembaruan tampilan, muat ulang browser dengan Ctrl+F5.
