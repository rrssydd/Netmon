# Netmon Workspace v7

Aplikasi lokal untuk mengumpulkan CPU, memory, status port, dan traffic WAN/uplink dari perangkat Cisco melalui SSH. Netmon hanya mengumpulkan perangkat yang didaftarkan operator; aplikasi tidak melakukan autodiscovery atau memindai jaringan secara otomatis.

## Mulai dari Git clone di Windows

Gunakan Python 3.11 atau lebih baru dan Git. Jalankan dari PowerShell atau Command Prompt:

```powershell
git clone https://github.com/rrssydd/Netmon.git
cd Netmon
setup_windows.bat
```

Setup membuat virtual environment `.venv` lokal dan memasang dependency dari `requirements.txt`. Koneksi internet dibutuhkan saat pertama kali memasang dependency. Sesudah setup selesai, jalankan `start_windows.bat`, buka **http://127.0.0.1:5000**, lalu biarkan terminal tetap terbuka. Aplikasi hanya mendengarkan pada komputer lokal.

Pada pemakaian pertama, buat akun lokal sendiri di halaman setup. Tidak ada akun atau password default. Setiap clone memulai dengan database kosong: inventori, akun, history, dan backup konfigurasi milik pengguna lain tidak disertakan di repository.

## Siapkan perangkat agar bisa dikoleksi

1. Buka **Add Device & Uplinks**, lalu daftarkan perangkat dengan alamat management yang dapat dijangkau dari komputer Netmon, username SSH, driver perangkat, dan collection profile yang sesuai.
2. Isi password SSH pada form atau gunakan environment variable lokal. Jangan masukkan password ke source code atau file yang akan di-commit.
3. Untuk traffic, tambahkan mapping WAN/uplink dan nama interface yang benar pada perangkat tersebut. CPU/memory dikoleksi dari perangkat; traffic dikoleksi per mapping interface.
4. Pastikan SSH aktif di perangkat, kredensial dan hak akses perintah show benar, serta firewall/ACL dan routing mengizinkan koneksi dari komputer Netmon ke perangkat melalui TCP port 22.
5. Tekan **Collect Now** di Overview. Hasil hanya mencakup perangkat dan uplink yang sudah terdaftar. Periksa log hasil collect dan waktu data terakhir untuk melihat perangkat yang gagal dijangkau.

Nama perangkat, IP/hostname, label link, dan interface berasal dari inventori lokal setiap pengguna. Halaman hasil Import Capture juga dibentuk dari perangkat dan mapping yang cocok dengan isi file capture; tidak ada nama perangkat atau link ISP milik contoh yang dipakai sebagai default aplikasi. Setiap orang mengisi Capture Hostname dan mapping interface untuk lingkungannya sendiri.

`start_windows.bat` otomatis memakai `.venv` jika setup sudah dijalankan. Untuk menghentikan aplikasi, tekan Ctrl+C di terminal. Untuk koleksi berulang tanpa membuka browser, ikuti bagian **Koleksi terjadwal** di bawah.

### Jalankan manual tanpa file batch

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Folder clone harus dapat ditulis oleh akun Windows yang menjalankan aplikasi karena database lokal dan kunci sesi dibuat di dalam folder tersebut.

## Pembaruan grafik dan upload

- Seluruh grafik WAN, kartu History, dan grafik detail menggunakan area bergradasi mengikuti tema dark/light.
- Warna CPU biru dan memory toska; traffic input toska dan output ungu. Tooltip memakai panel bertema, waktu lengkap, dan nilai dengan unit.
- Sumbu X menggunakan jarak waktu sebenarnya. Sumbu Y dimulai dari nol; skala atas menyesuaikan data masing-masing grafik dan dapat berbeda antarkartu.
- Kurva monotone menghubungkan sampel tanpa menambah nilai data; dua sampel yang hampir sama tetap menghasilkan tren mendatar. Area berwarna tidak berarti ada tambahan koleksi.
- Kontrol file bawaan browser diganti tombol Pilih file dari komputer. Mendukung keyboard, drag-and-drop, ukuran/nama file, hapus pilihan, serta validasi .txt maksimal 5 MB.
- Setelah update, hard refresh browser dengan Ctrl+F5. Untuk memakai data laptop yang lebih baru, untuk pembaruan akun v7, salin juga app.py, auth.py, verification.py, dan reset_login.py. Jangan hanya menyalin CSS/template.
- Rendering grafik diperiksa dengan canvas untuk data dua sampel, satu sampel, kosong, dan nilai null. Pengujian ini bukan pengujian seluruh halaman di browser Windows.

## Pembaruan tampilan

- Nama menu: **Add Device & Uplinks**.
- Penjelasan driver dan collection profile langsung mengikuti pilihan dropdown, dengan panduan tambahan yang dapat dibuka.
- Dark theme tetap hitam/biru; light theme memakai permukaan putih dan aksen biru dengan bayangan lembut.
- Hover pada menu, tombol, dan kartu memakai bayangan serta gerakan ringan. Navigasi keyboard tetap memiliki indikator fokus; efek gerak dikurangi mengikuti preferensi reduced motion.
- Monitoring Scope diganti indikator **Local Online** hijau. Status aplikasi diperiksa setiap 30 detik selama halaman aktif. Koneksi terputus menampilkan Local Offline, dan sesi login yang berakhir ditandai terpisah. Ini indikator aplikasi lokal, bukan status online seluruh perangkat jaringan.
- Login memakai tampilan baru dan tombol Lihat/Sembunyikan password.

## Akun dan akses perangkat

Akun login aplikasi disimpan terpisah dalam `auth.db`. Password login memakai salted hash. Kunci sesi lokal dibuat otomatis pada pemakaian pertama. Login aplikasi berbeda dari username/password SSH perangkat.

Password SSH yang disimpan melalui form masih berada dalam database lokal, mengikuti sistem lama; login aplikasi tidak mengenkripsi database tersebut. Sebagai alternatif, isi nama environment variable pada form dan kosongkan password saat membuat perangkat:

```powershell
$env:NETMON_PASSWORD_SWITCH="password-perangkat-anda"
python app.py
```

Password SSH tersimpan memiliki prioritas lebih tinggi daripada environment variable. Untuk perangkat lama, kolom password yang kosong saat edit mempertahankan password sebelumnya. Jika ingin beralih ke environment variable, kosongkan nilai password perangkat secara terkontrol pada database atau buat mapping perangkat baru setelah mencatat konfigurasi yang diperlukan.

## Menu

- **Overview:** ringkasan perangkat/link, tabel CPU/memory/peak, tiga grafik WAN sejajar pada desktop lebar, serta tabel peak traffic harian per arah. Klik baris WAN/uplink pada tabel daily report untuk membuka grafik live sejak jam mulai report tepat di bawahnya; grafik menandai batas Mbps dan menampilkan peak input/output beserta waktu serta jumlah sampel. Tabel menghitung peak dari koleksi SSH live sampai halaman dibuka, menampilkan traffic terbaru dan status batas. Grafik Overview sekitar 160–180 px; pada layar kecil susunan menyesuaikan menjadi dua atau satu kolom. Tombol Collect memiliki indikator proses serta log hasil yang bisa dibuka.
- **Add Device & Uplinks:** tambah/edit/hapus perangkat, serta tambah/hapus mapping interface uplink. Menghapus perangkat juga menghapus mapping uplink terkait. History tetap disimpan.
- **History & Trend:** tabel ringkasan untuk membandingkan nilai terbaru, peak dan waktunya, serta jumlah sampel pada rentang 24 jam/7/14/30 hari. Pencarian dan filter memudahkan pemilihan perangkat atau uplink. Grafik besar, rata-rata, minimum, peak, dan 10 catatan terakhir terbuka tepat di bawah baris terpilih; klik baris yang sama lagi untuk menutupnya. Pemilih rentang memakai tombol cepat. WAN/uplink dibandingkan dengan batas bandwidth `daily_report.mbps_limit` (default 300 Mbps), sedangkan status router/switch mengikuti ambang CPU dan memory. Kurva grafik dihaluskan untuk tampilan, sementara nilai, peak, dan jumlah sampel tetap berasal dari catatan asli. Angka traffic berasal dari rate interface rata-rata lima menit, bukan puncak sesaat. Waktu mengikuti waktu lokal laptop tempat koleksi berjalan.
- **Capture Device:** pilih perangkat dari inventori yang sama dengan Add Device & Uplinks, klik Show Run, lihat output, salin teks, atau unduh `.txt`. Setiap capture berhasil disimpan terpisah dalam database; daftar backup mendukung pencarian dan penghapusan per backup.
- **Import Capture:** unggah capture `.txt` maksimal 5 MB; isi Capture Hostname sesuai prompt perangkat.
- **Dark / Light:** tombol di kanan atas; pilihan tersimpan pada browser.
- **Logout:** tombol keluar di bagian akun pada sidebar.

## Kompatibilitas Collect dengan versi lama

Command, parser CPU/memory/traffic, urutan koleksi, dan perhitungan nilai metrik dipertahankan. Aturan status perangkat diperbarui pada v4.1 sesuai bagian Status port di bawah. Output yang sama dan konfigurasi yang sama menggunakan perhitungan yang sama; angka live tentu berubah mengikuti keadaan perangkat. Koleksi perangkat masih dilakukan satu per satu.

| Profile | Command |
| --- | --- |
| platform_xe | `show plat soft stat contr br`, `show processes cpu \| include utilization`, `show processes cpu history`, `show interfaces status` |
| classic_ios | `show processes cpu \| include utilization`, `show processes cpu history`, `show memory statistics`, `show interfaces status` |
| Uplink | `show interfaces <interface>` |

Grafik menunjukkan snapshot hasil koleksi, bukan polling real-time otomatis. Traffic memakai input/output rate 5 menit dari output interface. Parser CPU history serta perkiraan peak menggunakan metode versi lama; jangan menganggapnya pengukuran baru yang lebih presisi. Port `notconnect` tetap terlihat sebagai informasi dan tidak menaikkan status perangkat. Port `err-disabled` tetap dianggap gangguan. Koleksi yang gagal tidak menghapus snapshot terakhir; periksa log Collect dan waktu data terakhir. Nilai yang tidak terbaca ditampilkan sebagai tanda `—`. CPU/memory yang belum lengkap menghasilkan status Unknown jika tidak ada warning/critical yang terdeteksi.

Tidak ada koleksi WLC/AP, ekspor Excel/PDF, ataupun pemeriksaan perubahan konfigurasi dalam versi ini.

## Status port dan kesehatan perangkat

| Kondisi | Tampilan port | Status perangkat |
| --- | --- | --- |
| Port kosong / notconnect, CPU dan memory normal | Jumlah port down; klik untuk rincian nama port | Normal (hijau); tidak menambah Perlu diperiksa |
| Indikator down dari database lama, CPU dan memory normal | Down detected; Collect ulang untuk rincian | Normal (hijau) |
| CPU atau memory melewati warning | Indikator port tetap terpisah | Warning |
| CPU atau memory melewati critical | Indikator port tetap terpisah | Critical |
| Ada port err-disabled pada capture terbaru | Jumlah dan nama port err-disabled | Critical |
| CPU/memory belum berhasil terbaca lengkap | Tanda — pada metrik yang hilang | Unknown, jika tidak ada warning/critical |

Notconnect berarti tidak tersambung; aplikasi tidak menyimpulkan apakah port sengaja dikosongkan atau kabel lepas. Sesuai kebutuhan saat ini, semua notconnect diperlakukan sebagai informasi. Rincian port disimpan pada koleksi baru; nilai CPU/memory dan traffic tidak diubah oleh aturan ini.

## Capture Device / backup running-config

1. Tambahkan atau edit perangkat melalui Add Device & Uplinks.
2. Buka Capture Device dan pilih nama perangkat yang akan diambil konfigurasinya.
3. Klik **Show Run**. Aplikasi membuka SSH memakai kredensial perangkat tersebut dan mengirim command literal `show run`.
4. Output tampil sebagai teks dan disimpan otomatis di database lokal setelah capture berhasil.
5. Klik **Unduh .txt** untuk menyimpan file dengan nama perangkat dan waktu capture. Tombol **Salin** menyalin isi output.
6. Gunakan daftar Backup tersimpan untuk membuka atau mengunduh capture lama. Tombol **Hapus** menghapus hanya backup yang dipilih setelah konfirmasi; perangkat dan history monitoring tetap tersimpan.

Aplikasi membaca running-config saja; tidak mengubah konfigurasi dan tidak menjalankan write memory atau restore. Akun SSH harus sudah punya hak akses untuk show run; aplikasi tidak meminta enable password tambahan. Timeout pembacaan output adalah 120 detik setelah koneksi terbuka. Output kosong, command ditolak, atau output tanpa penanda akhir `end` tidak disimpan sebagai backup berhasil. Jika koneksi gagal, periksa pesan pada halaman; backup sebelumnya tetap tersimpan.

Backup dan unduhannya hanya dapat diakses setelah login. Database lokal menyimpan isi konfigurasi sebagaimana diterima. Backup tetap tersedia meskipun perangkat dihapus dari inventori. Halaman yang dimuat ulang setelah capture tidak menjalankan command lagi; untuk snapshot baru, klik Show Run kembali.

## Threshold

Clone baru memakai ambang aman dari `config/thresholds.example.yaml`. Untuk mengubah setting lokal, salin template tersebut lalu edit `config/thresholds.yaml`:

```powershell
Copy-Item config\thresholds.example.yaml config\thresholds.yaml
```

File `thresholds.yaml` lokal diabaikan Git, jadi perubahan threshold pribadi tidak ikut terunggah. File dibaca saat dashboard dibuka.

| Metrik | Warning | Critical |
| --- | --- | --- |
| CPU router/switch | >=80% | >=90% |
| Memory router/switch | >=80% | >=90% |
| Traffic WAN per arah | >=300 Mbps | >=800 Mbps |

Pengaturan tabel peak harian berada di bagian `daily_report` pada file yang sama:

```yaml
daily_report:
  start_time: "08:00"  # waktu lokal laptop; periode berakhir saat Overview dibuka
  mbps_limit: 300       # tepat 300 ditandai di batas; lebih dari 300 melebihi batas
```

Peak harian dihitung dari sampel koleksi SSH live di `metrics` dan tidak menghapus history. Capture yang diimpor manual tidak dihitung dalam tabel peak harian. Angka `show interfaces` adalah rata-rata traffic lima menit; hasilnya merupakan peak sampel rata-rata lima menit tertinggi yang berhasil dikoleksi, bukan puncak sesaat. Untuk cakupan yang lebih lengkap, jalankan koleksi terjadwal secara berkala dan pastikan satu proses selesai sebelum proses berikutnya dimulai.

## Import capture

Gunakan hasil command lengkap dengan prompt, misalnya:

```text
SW-CORE#show processes cpu
CPU utilization for five seconds: 9%/1%; one minute: 8%; five minutes: 7%
SW-CORE#show interfaces Gi0/0/0
GigabitEthernet0/0/0 is up, line protocol is up
  5 minute input rate 123000000 bits/sec
  5 minute output rate 45000000 bits/sec
SW-CORE#
```

Isi Capture Hostname perangkat dengan `SW-CORE` dan mapping interface WAN dengan `Gi0/0/0`. Ini hanya contoh format; gunakan capture asli ketika membuat report.

## Koleksi terjadwal

`cron_collect.py` menjalankan koleksi satu kali tanpa browser:

```powershell
python cron_collect.py
```

Untuk Windows Task Scheduler, pilih `python.exe` dari `.venv\Scripts\python.exe`, argumen `cron_collect.py`, dan **Start in** berisi folder project. Atur jadwal sesuai kebutuhan. Tidak ada jadwal yang dibuat otomatis oleh clone ini. Kredensial harus tersedia melalui database atau environment variable milik proses tersebut. Hindari menjadwalkan dua proses koleksi pada waktu yang sama.

## Lupa password dan buat user baru

Kedua tautan tersedia langsung di halaman login dan memakai tema dark/light yang sama.

### Lupa password

1. Klik **Lupa password?** dan masukkan username akun.
2. Klik **Minta kode verifikasi**.
3. Buka terminal Command Prompt / PowerShell yang menjalankan `python app.py`. Kode ditampilkan di terminal tersebut jika username ditemukan; kode tidak dikirim lewat email atau ditampilkan di halaman web.
4. Masukkan kode 8 digit, password baru minimal 10 karakter, dan konfirmasi password.
5. Klik **Simpan password baru**, kemudian login kembali. Sesi lama akun ini tidak berlaku lagi; akun lain tidak ikut direset.

### Buat user baru

1. Klik **Buat user baru** pada halaman login.
2. Masukkan username baru dan minta kode verifikasi dari terminal aplikasi.
3. Masukkan kode, password minimal 10 karakter, serta konfirmasi password.
4. Klik **Buat akun**, kemudian login menggunakan akun baru.

Semua akun lokal mempunyai akses yang sama ke inventori, kredensial perangkat yang dipakai tools, monitoring, dan backup konfigurasi. Belum ada role read-only atau pembatasan per perangkat. Verifikasi terminal memastikan pendaftaran membutuhkan akses ke komputer tempat aplikasi berjalan. Jika dijalankan oleh orang lain, minta bantuan pemilik komputer tersebut untuk verifikasi.

Kode berlaku 5 menit dan satu kali pakai, terikat pada alur/browser peminta, dengan maksimal 5 percobaan. Permintaan baru dibatasi sekali per 30 detik dan maksimal 10 permintaan per 15 menit untuk aplikasi. Restart aplikasi membatalkan semua kode yang belum digunakan. Tetap gunakan browser/sesi yang sama saat memasukkan kode. Jika gagal atau kedaluwarsa, minta kode baru.

Akun lama dimigrasikan otomatis ke struktur multi-user saat aplikasi dibuka. Username, hash password, dan sesi yang masih valid dipertahankan. Mendaftarkan user baru tidak mengganti akun lama.

### Pemulihan alternatif dari terminal

Jika diperlukan, jalankan `python reset_login.py`, lalu masukkan username akun yang sudah ada dan password baru. Script ini hanya mereset akun tersebut; pembuatan akun baru dilakukan melalui halaman login.

## Backup dan pemindahan

Hentikan aplikasi dan koleksi terjadwal sebelum backup. `netmon.db` menyimpan inventori, history, dan backup konfigurasi; `auth.db` menyimpan akun login; `config/thresholds.yaml` menyimpan threshold lokal. File-file tersebut tidak masuk ke Git. Simpan backup di lokasi privat dan jangan commit atau unggah database karena dapat berisi kredensial SSH serta running-config perangkat. Untuk memulai ulang dengan database kosong, tutup aplikasi lalu pindahkan `netmon.db` dan `auth.db` ke lokasi backup; aplikasi membuat database kosong dan meminta setup akun saat dijalankan kembali.

## Pemeriksaan yang sudah dilakukan

- 19 pengujian integrasi offline lolos, mencakup autentikasi, CSRF, perangkat, import, Collect, port notconnect yang tetap normal, err-disabled/CPU tinggi, Capture Device, unduhan dengan isi identik, kegagalan capture, pemilihan history, dan migrasi schema lama.
- Pengujian menggunakan inventori sintetis, database sementara, serta SSH simulasi; tidak membutuhkan database pribadi.
- Sintaks Python dan JavaScript diperiksa.
- SSH ke perangkat asli dan tampilan browser Windows belum diuji di lingkungan pengguna.

Jalankan kembali pengujian dengan:

```powershell
python tests/test_app.py
```

Pengujian menggunakan salinan sementara dan tidak terhubung ke perangkat jaringan.

## Struktur

- `app.py`: route web, login, proteksi form, dan kontrol Collect.
- `auth.py`: akun multi-user, migrasi akun lama, salted password hash, dan kunci sesi.
- `verification.py`: kode verifikasi lokal sekali pakai untuk reset dan pendaftaran.
- `db.py`: database inventori, metrik, rincian port, dan backup konfigurasi.
- `logic.py`: koleksi, import capture, dan perhitungan dashboard.
- `netmon/`: collector SSH dan parser CLI.
- `templates/`: halaman web.
- `static/`: CSS, JavaScript, dan Chart.js lokal.
- `tests/`: pengujian offline.

Chart.js 4.4.8 menggunakan lisensi MIT; atribusi ada dalam `static/chart.umd.js` dan `THIRD_PARTY_NOTICES.md`.
