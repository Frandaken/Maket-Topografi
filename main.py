"""
main.py - Maket Topografi Interaktif (MVP)
============================================

Alur program (sesuai dokumen rancangan bagian 10 & 11):
    Webcam -> deteksi 4 marker ArUco -> koreksi perspektif (warp)
    -> baca zona warna -> buat peta elevasi (peta warna + kontur)
    -> tampilkan di window "OUTPUT PROYEKTOR"

MODE SIMULASI:
    Karena belum ada webcam fisik maket, program ini jalan pakai
    webcam laptop (CAMERA_ID = 0). Untuk testing tanpa marker fisik
    tercetak, tekan tombol 'd' untuk toggle DEBUG MODE yang akan
    memakai seluruh frame sebagai area maket (skip deteksi marker),
    supaya kamu bisa lihat proses klasifikasi warna & kontur bekerja
    lebih dulu sebelum marker fisik siap dicetak & ditempel.

MODE SCAN MANUAL (bukan real-time terus-menerus):
    Window "Kamera" selalu menampilkan preview langsung + status
    marker, supaya operator bisa lihat posisi kamera & marker kapan
    saja. TAPI window "OUTPUT PROYEKTOR" (peta warna + kontur) TIDAK
    diperbarui otomatis tiap frame. Ia hanya diperbarui sesaat setelah
    tombol SPASI ditekan, lalu hasilnya ditahan (statis) sampai SPASI
    ditekan lagi.

    Alasan: proyektor menyala menampilkan garis kontur PUTIH TERANG di
    atas maket. Kalau webcam terus membaca warna secara real-time
    SAAT proyektor sedang menyala, cahaya kontur putih itu bisa
    ikut terbaca dan mengacaukan klasifikasi warna lapisan (feedback
    loop kamera-proyektor). Dengan scan manual, pembacaan warna dan
    penayangan hasil tidak pernah terjadi bersamaan.

    Alur pemakaian expo: pengunjung ubah lapisan -> operator/pengunjung
    tekan SPASI -> sistem scan sekali -> proyektor tampilkan hasil baru
    -> diam sampai SPASI ditekan lagi.

KONTROL:
    q       -> keluar program
    d       -> toggle debug mode (skip marker, pakai seluruh frame)
    SPASI   -> SCAN SEKARANG: baca warna & perbarui output proyektor

GANTI SEBELUM DIPAKAI DI SEKOLAH:
    - CAMERA_ID: sesuaikan jika webcam sekolah terdeteksi sebagai 1/2
    - OUTPUT_WIDTH/HEIGHT: sesuaikan rasio 80x60 cm (4:3) jika perlu
    - WARNA_KONTUR: putih tipis secara default (lihat KONFIGURASI)
"""

import cv2
import numpy as np

# ============================================================
# KONFIGURASI - sesuaikan dengan kondisi lapangan
# ============================================================

CAMERA_ID = 0  # ganti ke 1 atau 2 jika webcam sekolah tidak terdeteksi di 0

# Ukuran hasil warp (area maket setelah koreksi perspektif).
# Rasio 80:60 = 4:3, dikalikan skala biar tetap tajam.
OUTPUT_WIDTH = 800
OUTPUT_HEIGHT = 600

# Dictionary ArUco - HARUS SAMA dengan buat_marker.py
ARUCO_DICT = cv2.aruco.DICT_4X4_50

# ID marker sesuai posisi (dokumen bagian 8)
ID_KIRI_ATAS = 0
ID_KANAN_ATAS = 1
ID_KANAN_BAWAH = 2
ID_KIRI_BAWAH = 3

# ------------------------------------------------------------
# TABEL LAPISAN TOPOGRAFI (disesuaikan tim: 6 level, dasar(1) -> puncak(6))
# Warna referensi dalam BGR (OpenCV pakai BGR, bukan RGB!)
# Sesuaikan angka ini setelah uji warna cat/bahan lapisan asli,
# karena warna cat fisik jarang persis sama dengan warna teoretis.
# ------------------------------------------------------------
LAPISAN_TOPOGRAFI = [
    # (level, nama, warna_bgr_referensi, warna_bgr_tampilan)
    (1, "Dasar - Biru laut", (205, 220, 70), (205, 220, 70)),     # biru laut (turquoise cerah)
    (2, "Hijau muda", (144, 238, 144), (144, 238, 144)),          # hijau muda
    (3, "Hijau tua", (0, 100, 0), (0, 100, 0)),                   # hijau tua
    (4, "Kuning", (0, 255, 255), (0, 255, 255)),                  # kuning
    (5, "Jingga", (0, 140, 255), (0, 140, 255)),                  # jingga
    (6, "Puncak - Merah", (0, 0, 255), (0, 0, 255)),              # merah
]

# Threshold jarak warna maksimum untuk dianggap "cocok" dengan salah
# satu level. Piksel yang tidak cocok dianggap latar/bayangan/papan.
BATAS_JARAK_WARNA = 60

# Warna garis kontur saat DITAMPILKAN/DIPROYEKSIKAN (BGR).
# Putih tipis dipilih karena proyektor menembakkan cahaya PALING KUAT
# untuk putih, jadi kontras kontur jauh lebih pasti terlihat di atas
# warna cat apa pun -- termasuk di atas warna gelap (biru tua, merah
# tua) yang kalau pakai kontur hitam nyaris tidak terlihat.
WARNA_KONTUR = (255, 255, 255)
KETEBALAN_KONTUR = 1


# ============================================================
# FUNGSI-FUNGSI UTAMA
# ============================================================

def buat_aruco_detector():
    """Membuat detector ArUco (API OpenCV modern)."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    return detector


def deteksi_empat_marker(frame, detector):
    """
    Mendeteksi 4 marker ArUco di frame.
    Return: dict {id: titik_tengah(x,y)} jika ditemukan, atau None
            per id yang belum terdeteksi.
    """
    corners, ids, _ = detector.detectMarkers(frame)

    titik = {}
    if ids is not None:
        for i, marker_id in enumerate(ids.flatten()):
            c = corners[i][0]  # 4 titik sudut marker
            pusat = c.mean(axis=0)  # titik tengah marker
            titik[int(marker_id)] = pusat

    return titik


def urutan_marker_lengkap(titik_marker):
    """Cek apakah ke-4 marker yang dibutuhkan sudah terdeteksi."""
    id_dibutuhkan = [ID_KIRI_ATAS, ID_KANAN_ATAS, ID_KANAN_BAWAH, ID_KIRI_BAWAH]
    return all(i in titik_marker for i in id_dibutuhkan)


def warp_perspektif(frame, titik_marker):
    """
    Transformasi perspektif: ambil area yang dibatasi 4 marker,
    ubah jadi tampak lurus dari atas (bird's eye view) berukuran
    OUTPUT_WIDTH x OUTPUT_HEIGHT.
    """
    src = np.array([
        titik_marker[ID_KIRI_ATAS],
        titik_marker[ID_KANAN_ATAS],
        titik_marker[ID_KANAN_BAWAH],
        titik_marker[ID_KIRI_BAWAH],
    ], dtype=np.float32)

    dst = np.array([
        [0, 0],
        [OUTPUT_WIDTH - 1, 0],
        [OUTPUT_WIDTH - 1, OUTPUT_HEIGHT - 1],
        [0, OUTPUT_HEIGHT - 1],
    ], dtype=np.float32)

    matriks = cv2.getPerspectiveTransform(src, dst)
    hasil = cv2.warpPerspective(frame, matriks, (OUTPUT_WIDTH, OUTPUT_HEIGHT))
    return hasil


def klasifikasikan_warna(area_maket):
    """
    Untuk setiap piksel, cari level topografi dengan warna referensi
    paling dekat. Return: peta_level (array 2D berisi index level,
    -1 jika tidak cocok dengan level manapun / dianggap latar).
    """
    h, w = area_maket.shape[:2]
    peta_level = np.full((h, w), -1, dtype=np.int8)
    jarak_terbaik = np.full((h, w), 1e9, dtype=np.float32)

    area_float = area_maket.astype(np.float32)

    for idx, (level, nama, warna_ref, _) in enumerate(LAPISAN_TOPOGRAFI):
        warna_ref_arr = np.array(warna_ref, dtype=np.float32)
        selisih = area_float - warna_ref_arr
        jarak = np.sqrt(np.sum(selisih ** 2, axis=2))

        cocok_lebih_baik = jarak < jarak_terbaik
        peta_level[cocok_lebih_baik] = idx
        jarak_terbaik[cocok_lebih_baik] = jarak[cocok_lebih_baik]

    # piksel yang jaraknya masih terlalu jauh dari SEMUA warna referensi
    # dianggap bukan bagian lapisan (latar, bayangan, dsb)
    peta_level[jarak_terbaik > BATAS_JARAK_WARNA] = -1

    return peta_level


def buat_peta_warna(peta_level):
    """Ubah peta_level (index) jadi gambar BGR berwarna hipsometrik."""
    h, w = peta_level.shape
    hasil = np.zeros((h, w, 3), dtype=np.uint8)

    for idx, (level, nama, _, warna_tampil) in enumerate(LAPISAN_TOPOGRAFI):
        mask = peta_level == idx
        hasil[mask] = warna_tampil

    return hasil


def gambar_kontur(peta_warna, peta_level):
    """
    Menggambar garis kontur (garis putih/hitam) di batas antar-level
    topografi yang berbeda, mengikuti prinsip garis kontur = batas
    ketinggian yang sama.
    """
    hasil = peta_warna.copy()

    for idx in range(len(LAPISAN_TOPOGRAFI) - 1):
        # ambil semua area dengan level >= idx+1 (di atas batas ini)
        mask_atas = (peta_level >= 0) & (peta_level == idx)
        mask_naik = (peta_level == idx + 1)

        gabungan = (mask_atas | mask_naik).astype(np.uint8) * 255
        if gabungan.sum() == 0:
            continue

        kontur, _ = cv2.findContours(gabungan, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(hasil, kontur, -1, WARNA_KONTUR, KETEBALAN_KONTUR)

    return hasil


def tambah_legenda(gambar):
    """Menempelkan legenda warna di pojok kanan atas hasil output."""
    hasil = gambar.copy()
    x0, y0 = hasil.shape[1] - 180, 10
    kotak_tinggi = 22

    overlay = hasil.copy()
    cv2.rectangle(overlay, (x0 - 10, y0 - 5), (hasil.shape[1] - 5,
                  y0 + kotak_tinggi * len(LAPISAN_TOPOGRAFI) + 5), (255, 255, 255), -1)
    hasil = cv2.addWeighted(overlay, 0.75, hasil, 0.25, 0)

    for i, (level, nama, _, warna) in enumerate(reversed(LAPISAN_TOPOGRAFI)):
        y = y0 + i * kotak_tinggi
        cv2.rectangle(hasil, (x0, y), (x0 + 15, y + 15), warna, -1)
        cv2.rectangle(hasil, (x0, y), (x0 + 15, y + 15), (0, 0, 0), 1)
        cv2.putText(hasil, f"{level}: {nama}", (x0 + 20, y + 13),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1, cv2.LINE_AA)

    return hasil


# ============================================================
# PROGRAM UTAMA
# ============================================================

def main():
    print("=" * 60)
    print("MAKET TOPOGRAFI INTERAKTIF - MVP")
    print("=" * 60)
    print(f"Membuka kamera ID {CAMERA_ID}...")
    print("Kontrol: 'q' keluar | 'd' toggle debug mode (tanpa marker)")
    print()

    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print(f"GAGAL membuka kamera ID {CAMERA_ID}.")
        print("Coba ganti CAMERA_ID di bagian atas file ini ke 1 atau 2.")
        return

    detector = buat_aruco_detector()

    cv2.namedWindow("Kamera (deteksi marker)", cv2.WINDOW_NORMAL)
    cv2.namedWindow("OUTPUT PROYEKTOR", cv2.WINDOW_NORMAL)

    debug_mode = False  # jika True, skip deteksi marker, pakai seluruh frame

    # Layar output proyektor bersifat STATIS: hanya berubah saat SPASI
    # ditekan. Ini yang ditampilkan window "OUTPUT PROYEKTOR" di setiap
    # frame sampai scan berikutnya dilakukan.
    layar_output_terkini = np.zeros((OUTPUT_HEIGHT, OUTPUT_WIDTH, 3), dtype=np.uint8)
    cv2.putText(layar_output_terkini, "Tekan SPASI untuk scan pertama",
                (20, OUTPUT_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (255, 255, 255), 2)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Gagal membaca frame dari kamera.")
            break

        frame_tampil = frame.copy()
        area_maket_siap = False  # apakah frame SEKARANG punya area maket valid
        area_maket = None

        if debug_mode:
            # mode simulasi tanpa marker fisik: pakai seluruh frame
            area_maket = cv2.resize(frame, (OUTPUT_WIDTH, OUTPUT_HEIGHT))
            area_maket_siap = True
            cv2.putText(frame_tampil, "DEBUG MODE: skip deteksi marker",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            titik_marker = deteksi_empat_marker(frame, detector)

            # gambar marker yang terdeteksi untuk feedback visual
            for marker_id, pusat in titik_marker.items():
                cv2.circle(frame_tampil, tuple(pusat.astype(int)), 8, (0, 255, 0), -1)
                cv2.putText(frame_tampil, str(marker_id),
                            tuple(pusat.astype(int) + np.array([10, -10])),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            jumlah = len(titik_marker)
            status_teks = f"Marker terdeteksi: {jumlah}/4"
            warna_status = (0, 255, 0) if jumlah == 4 else (0, 165, 255)
            cv2.putText(frame_tampil, status_teks, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, warna_status, 2)

            if urutan_marker_lengkap(titik_marker):
                area_maket = warp_perspektif(frame, titik_marker)
                area_maket_siap = True

        # Petunjuk di window kamera supaya operator tahu kapan bisa scan
        if area_maket_siap:
            cv2.putText(frame_tampil, "Tekan SPASI untuk SCAN",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(frame_tampil, "Belum siap discan",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        cv2.imshow("Kamera (deteksi marker)", frame_tampil)
        # window proyektor HANYA menampilkan hasil scan terakhir (statis),
        # tidak diperbarui tiap frame -> mencegah feedback loop kamera-proyektor
        cv2.imshow("OUTPUT PROYEKTOR", layar_output_terkini)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d'):
            debug_mode = not debug_mode
            print(f"Debug mode: {'ON' if debug_mode else 'OFF'}")
        elif key == ord(' '):
            if area_maket_siap:
                print("SCAN: membaca warna & memperbarui output...")
                peta_level = klasifikasikan_warna(area_maket)
                peta_warna = buat_peta_warna(peta_level)
                hasil_kontur = gambar_kontur(peta_warna, peta_level)
                layar_output_terkini = tambah_legenda(hasil_kontur)
                print("SCAN selesai. Output diperbarui.")
            else:
                print("SCAN dibatalkan: area maket belum siap (marker belum lengkap).")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
