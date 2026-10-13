# Netmon Workspace

Netmon adalah aplikasi web lokal untuk memantau kondisi router dan switch serta traffic WAN/uplink melalui SSH. Dashboard menampilkan CPU, memory, status interface, riwayat pengukuran, dan peak traffic harian.

## Persiapan

- Windows dengan Python 3.11 atau lebih baru.
- Komputer tempat Netmon dijalankan dapat mengakses perangkat melalui SSH.
- Siapkan akun SSH dengan hak akses untuk menjalankan perintah monitoring yang dipakai perangkat.

## Instalasi dan menjalankan aplikasi

1. Unduh atau clone repository ini, lalu buka PowerShell di folder yang berisi `app.py`.
2. Pasang dependency:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Jalankan aplikasi:

   ```powershell
   python app.py
   ```

4. Buka `http://127.0.0.1:5000` di browser.
5. Pada penggunaan pertama, buat akun melalui halaman pendaftaran. Aplikasi tidak memiliki username atau password bawaan. Pada penggunaan berikutnya, login dengan akun yang sudah dibuat.

Setelah dependency terpasang, aplikasi juga dapat dijalankan dengan membuka `start_windows.bat`. Terminal harus tetap terbuka selama aplikasi digunakan. Hentikan aplikasi dengan `Ctrl+C` di terminal.

## Langkah penggunaan

1. **Daftarkan perangkat.** Buka **Add Device & Uplinks**, pilih **Tambah perangkat**, lalu isi nama perangkat, host/IP, username SSH, device type, dan collection profile. Masukkan password SSH atau gunakan environment variable. Simpan perangkat.
2. **Tambahkan interface WAN/uplink.** Pada halaman yang sama, tambahkan label link dan pilih perangkat serta nama interface yang akan dipantau. Pastikan nama interface sesuai dengan yang dikenali perangkat.
3. **Jalankan koleksi.** Buka **Overview**, klik **Collect Now**, lalu tunggu proses selesai. Perangkat yang dapat dijangkau melalui SSH akan menyimpan sampel CPU, memory, status port, dan traffic.
4. **Baca laporan harian.** Pada **Overview**, lihat tabel **Peak Traffic Harian**. Nilai peak input dan output dihitung terpisah dari sampel yang berhasil dikoleksi dalam periode laporan. Periksa juga waktu peak dan status terhadap batas bandwidth.
5. **Lihat tren.** Buka **History & Trend**, pilih rentang waktu, lalu klik baris perangkat atau uplink untuk melihat grafik dan ringkasan sampelnya.
6. **Ambil atau impor capture konfigurasi bila diperlukan.** Gunakan **Capture Device** untuk mengambil running-config melalui SSH atau **Import Capture** untuk membaca file capture. File konfigurasi dapat berisi informasi sensitif; jangan unggah ke repository.

## Pengumpulan berkala untuk peak harian

Klik **Collect Now** menjalankan koleksi satu kali. Agar peak lebih mewakili traffic sejak pagi, jadwalkan `cron_collect.py` di Windows Task Scheduler. Script ini menjalankan koleksi yang sama tanpa perlu browser.

1. Buka **Task Scheduler** dan buat task dengan trigger harian mulai pukul `08:00`.
2. Atur pengulangan, misalnya setiap 5 atau 15 menit selama jam operasional. Sesuaikan interval dengan durasi koleksi agar task tidak berjalan tumpang tindih.
3. Pada action **Start a program**, pilih `python.exe` yang sama dengan instalasi aplikasi.
4. Isi **Add arguments** dengan `cron_collect.py` dan **Start in** dengan path folder repository yang berisi `app.py`.
5. Pastikan komputer menyala, terhubung ke jaringan, dan task berjalan dengan akun Windows yang dapat mengakses database lokal serta kredensial yang diperlukan.

Untuk menjalankan koleksi satu kali secara manual dari folder repository, gunakan:

```powershell
python cron_collect.py
```

Task Scheduler tidak dibuat otomatis oleh aplikasi. Periksa **History & Trend** atau **Overview** setelah beberapa kali koleksi untuk memastikan data bertambah.

## Batas traffic dan cara membaca peak

Pengaturan terdapat di `config/thresholds.yaml`. Nilai bawaan daily report adalah mulai pukul `08:00` waktu lokal komputer dan batas `300 Mbps`. Ubah `daily_report.start_time` atau `daily_report.mbps_limit` bila kebutuhan laporan berbeda.

Peak adalah nilai tertinggi di antara sampel yang berhasil dikoleksi pada periode tersebut, bukan pengukuran setiap paket atau puncak sesaat. Rate traffic yang dibaca dari CLI perangkat merupakan rata-rata interval perangkat (umumnya sekitar lima menit). Karena itu, seberapa lengkap peak terpantau bergantung pada frekuensi koleksi. Data capture konfigurasi yang diimpor tidak dihitung sebagai sampel traffic.

Batas bandwidth diterapkan pada WAN/uplink. CPU dan memory router/switch tetap ditampilkan sebagai metrik perangkat dan tidak dinilai memakai batas Mbps.

## Data lokal dan keamanan

Saat pertama kali dijalankan, Netmon membuat `auth.db`, `netmon.db`, dan `.session_key` di folder aplikasi. Database menyimpan akun aplikasi, inventori perangkat, sampel monitoring, dan capture konfigurasi. Password login aplikasi disimpan dalam bentuk hash; password SSH yang dimasukkan melalui form tersimpan di database lokal.

Batasi akses ke komputer dan folder aplikasi. Jika memakai password SSH dari form, lindungi database lokal dan jangan kirim atau unggah database maupun file capture operasional. Alternatifnya, isi nama environment variable pada kolom **Environment password** di **Add Device & Uplinks**, lalu sediakan variable tersebut pada proses aplikasi.

`.gitignore` mengecualikan database, session key, file environment, cache, dan log dari pelacakan Git biasa. Aturan ini tidak menghapus file dari komputer dan tidak mengeluarkan file yang sudah terlanjur dilacak. Sebelum commit atau push, tinjau `git status` dan pastikan database, `.session_key`, file `.env`, serta capture operasional tidak tercantum.
