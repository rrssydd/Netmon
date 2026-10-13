# Netmon Workspace

Aplikasi web lokal untuk memantau CPU, memory router/switch, dan traffic WAN/uplink melalui SSH. Aplikasi menyediakan ringkasan harian, history/trend, pengelolaan perangkat, dan penyimpanan capture konfigurasi.

## Menjalankan di Windows

Gunakan Python 3.11 atau lebih baru. Dari folder ini, jalankan:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Buka `http://127.0.0.1:5000`. Pada penggunaan pertama, buat akun melalui halaman login. Tidak ada username atau password default. `start_windows.bat` juga dapat digunakan setelah dependency terpasang.

## Pengaturan

- Ambang CPU, memory, traffic WAN, dan waktu mulai daily report diatur melalui `config/thresholds.yaml`.
- Batas daily report bawaan adalah 300 Mbps dan periode dimulai pukul 08:00 waktu lokal.
- Perangkat dan uplink ditambahkan dari menu **Add Device & Uplinks**. Koneksi SSH ke perangkat diperlukan saat menjalankan koleksi.

## Data dan keamanan

Database lokal dibuat saat aplikasi dijalankan. Database tersebut dapat berisi akun aplikasi, inventori perangkat, kredensial SSH yang dimasukkan, history traffic, dan capture konfigurasi. File database, session key, konfigurasi rahasia, cache, dan log lokal dikecualikan oleh `.gitignore`; jangan menghapus pengecualian tersebut saat menyiapkan commit.

Password SSH yang disimpan lewat form berada di database lokal. Batasi akses ke komputer/folder aplikasi dan jangan mengunggah database atau capture operasional ke repository.

## Cara membaca traffic

Daily report dan History & Trend menghitung peak dari sampel yang berhasil dikoleksi. Nilai traffic CLI merupakan rata-rata interval perangkat, bukan pengukuran setiap paket atau puncak sesaat. Koleksi berkala membantu membuat peak harian lebih mewakili kondisi jaringan.
