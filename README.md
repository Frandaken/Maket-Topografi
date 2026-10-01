# Maket Topografi Interaktif - Kode MVP

## Isi folder
- `main.py` — program utama (webcam -> marker -> warp -> klasifikasi warna -> kontur -> output)
- `buat_marker.py` — generate 4 gambar marker ArUco untuk dicetak
- `requirements.txt` — daftar library

## Cara pakai

1. Install Python 3.10/3.11
2. Install library:
   ```
   pip install -r requirements.txt
   ```
3. Generate marker untuk dicetak:
   ```
   python buat_marker.py
   ```
   Cetak isi folder `marker_output/`, tempel sesuai posisi (lihat komentar di file).

4. Jalankan program utama:
   ```
   python main.py
   ```
   - Tekan `d` untuk toggle DEBUG MODE (skip deteksi marker, langsung
     pakai seluruh gambar webcam) — pakai ini SEBELUM marker fisik jadi,
     supaya bisa lihat proses klasifikasi warna & kontur bekerja dulu.
   - Tekan `SPASI` untuk SCAN — baca warna & perbarui window
     "OUTPUT PROYEKTOR" sekali. Window proyektor TIDAK update otomatis
     tiap frame; harus SPASI tiap kali ingin memperbarui hasil.
   - Tekan `q` untuk keluar.

### Kenapa mode scan manual (bukan real-time)?
Proyektor menyala menampilkan garis kontur putih terang di atas maket.
Kalau webcam membaca warna secara terus-menerus SAAT proyektor sedang
menyala, cahaya kontur itu bisa ikut terbaca sensor dan mengacaukan
klasifikasi warna lapisan (efeknya seperti feedback loop / lingkaran
setan antara kamera dan proyektor). Dengan scan manual, pembacaan warna
dan penayangan hasil dipisahkan waktu sehingga hal ini tidak terjadi.
Alur di expo: pengunjung ubah lapisan -> tekan SPASI -> hasil baru
muncul di proyektor -> diam sampai SPASI ditekan lagi.

### Kenapa garis kontur putih, bukan hitam?
Proyektor tidak bisa menghasilkan hitam sungguhan (hanya memblokir
cahaya secara parsial), jadi garis hitam kontrasnya lemah — terutama
di atas warna lapisan yang sudah gelap (biru tua, merah tua). Putih
adalah keluaran cahaya terkuat proyektor, sehingga kontras kontur jauh
lebih pasti terlihat di atas warna apa pun. Ubah `WARNA_KONTUR` dan
`KETEBALAN_KONTUR` di main.py jika perlu disesuaikan lagi.

## Skema warna lapisan (6 level, dasar -> puncak)
| Level | Nama | Warna |
|---|---|---|
| 1 | Dasar | Biru laut (turquoise cerah) |
| 2 | - | Hijau muda |
| 3 | - | Hijau tua |
| 4 | - | Kuning |
| 5 | - | Jingga |
| 6 | Puncak | Merah |

Warna ini masih **referensi teoretis**, lihat catatan di bawah soal
kalibrasi ulang dari cat/bahan asli.

## Yang masih perlu disesuaikan tim software
- `CAMERA_ID` di main.py — ganti ke 1/2 jika webcam sekolah tidak di ID 0
- Warna referensi `LAPISAN_TOPOGRAFI` — HARUS diukur ulang dari warna
  cat/bahan lapisan ASLI yang dipakai tim maket, karena warna teoretis
  di kode ini kemungkinan besar tidak identik dengan warna fisik.
  (Saran: foto tiap lapisan pakai webcam yang sama, cek nilai BGR
  pakai color picker, masukkan ke tabel.)
- `BATAS_JARAK_WARNA` — kalau warna sering salah baca, coba naikkan;
  kalau warna antar-level sering tertukar, coba turunkan atau perbesar
  jarak warna antar-level saat mengecat.

## Status pengujian
Logika klasifikasi warna, kontur, dan legenda sudah diuji dengan data
sintetis (blok warna & pola "gunung" konsentris) dan bekerja benar.
Belum diuji dengan webcam/marker fisik sungguhan — itu langkah
berikutnya begitu webcam & marker cetak tersedia.
