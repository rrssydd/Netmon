"""Offline fallback to reset one local user from the machine running Netmon."""
import getpass
import auth

if __name__=='__main__':
    username=input('Username akun yang akan direset: ').strip()
    user=auth.account(username)
    if not user:raise SystemExit('Username tidak ditemukan. Gunakan Buat user baru pada halaman login untuk mendaftar.')
    password=getpass.getpass('Password baru (minimal 10 karakter): ')
    confirmation=getpass.getpass('Ulangi password: ')
    if len(password)<10 or password!=confirmation:raise SystemExit('Tidak disimpan. Periksa panjang dan konfirmasi password.')
    if not auth.reset_password(user['username'],password,user['revision']):raise SystemExit('Akun berubah selama proses. Coba kembali.')
    print('Password diperbarui. Sesi akun ini sebelumnya tidak berlaku lagi.')
