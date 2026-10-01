"""
main.py - Maket Topografi Interaktif (MVP)
============================================

Alur program:
    Webcam -> deteksi 4 marker ArUco -> koreksi perspektif (warp)
    -> baca zona warna -> buat peta elevasi (peta warna + kontur)
    -> tampilkan di window "OUTPUT PROYEKTOR"

MODE SCAN MANUAL dengan LAYAR HITAM:
    Saat SPASI ditekan, urutannya begini:
        1. Window "OUTPUT PROYEKTOR" langsung jadi HITAM total
           (proyektor tidak menyinari maket sama sekali).
        2. Program menunggu JEDA_LAYAR_HITAM detik supaya cahaya
           kontur lama benar-benar hilang dari maket dan exposure
           kamera menyesuaikan diri.
        3. Buffer kamera dibuang, lalu 1 frame segar diambil
           dan dipakai untuk membaca warna.
        4. Hasil scan baru ditampilkan di proyektor dan ditahan
           (statis) sampai SPASI ditekan lagi.

    Window "Kamera" tetap jalan live selama proses, dengan hitung
    mundur supaya operator tahu kapan scan terjadi.

KONTROL:
    q       -> keluar program
    d       -> toggle debug mode (skip marker, pakai seluruh frame)
    SPASI   -> SCAN: layar hitam -> baca warna -> tampilkan hasil
"""

import time

import cv2
import numpy as np

# ============================================================
# KONFIGURASI - sesuaikan dengan kondisi lapangan
# ============================================================

CAMERA_ID = 0  # ganti ke 1 atau 2 jika webcam sekolah tidak terdeteksi di 0

OUTPUT_WIDTH = 800
OUTPUT_HEIGHT = 600

ARUCO_DICT = cv2.aruco.DICT_4X4_50

ID_KIRI_ATAS = 0
ID_KANAN_ATAS = 1
ID_KANAN_BAWAH = 2
ID_KIRI_BAWAH = 3

# ------------------------------------------------------------
# Pengaturan layar hitam sebelum scan
# ------------------------------------------------------------
# Lama proyektor hitam sebelum kamera mengambil gambar (detik).
# Naikkan kalau webcam lambat menyesuaikan exposure / auto-white-balance,
# atau kalau proyektor punya jeda respons. Mulai dari 1.5 lalu uji.
JEDA_LAYAR_HITAM = 1

# Jumlah frame lama yang dibuang tepat sebelum ambil gambar scan.
# Webcam biasanya menyimpan beberapa frame di buffer, jadi tanpa ini
# frame yang terbaca bisa saja masih frame dari saat proyektor menyala.
BUANG_FRAME_BUFFER = 5

# ------------------------------------------------------------
# TABEL LAPISAN TOPOGRAFI (6 level, dasar(1) -> puncak(6))
# Warna dalam BGR (OpenCV pakai BGR, bukan RGB!)
# ------------------------------------------------------------
LAPISAN_TOPOGRAFI = [
    # (level, nama, warna_bgr_referensi, warna_bgr_tampilan)
    (1, "Dasar - Biru laut", (205, 220, 70), (205, 220, 70)),
    (2, "Hijau muda", (144, 238, 144), (144, 238, 144)),
    (3, "Hijau tua", (0, 100, 0), (0, 100, 0)),
    (4, "Kuning", (0, 255, 255), (0, 255, 255)),
    (5, "Jingga", (0, 140, 255), (0, 140, 255)),
    (6, "Puncak - Merah", (0, 0, 255), (0, 0, 255)),
]

BATAS_JARAK_WARNA = 60

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
    """Mendeteksi marker ArUco di frame. Return dict {id: titik_tengah}."""
    corners, ids, _ = detector.detectMarkers(frame)

    titik = {}
    if ids is not None:
        for i, marker_id in enumerate(ids.flatten()):
            c = corners[i][0]
            pusat = c.mean(axis=0)
            titik[int(marker_id)] = pusat

    return titik


def urutan_marker_lengkap(titik_marker):
    """Cek apakah ke-4 marker yang dibutuhkan sudah terdeteksi."""
    id_dibutuhkan = [ID_KIRI_ATAS, ID_KANAN_ATAS, ID_KANAN_BAWAH, ID_KIRI_BAWAH]
    return all(i in titik_marker for i in id_dibutuhkan)


def warp_perspektif(frame, titik_marker):
    """Ubah area di dalam 4 marker jadi tampak lurus dari atas."""
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


def ambil_area_maket(frame, detector, debug_mode):
    """
    Ubah 1 frame kamera jadi area maket (OUTPUT_WIDTH x OUTPUT_HEIGHT).
    Return: (area_maket, titik_marker). area_maket = None jika belum siap.
    """
    if debug_mode:
        return cv2.resize(frame, (OUTPUT_WIDTH, OUTPUT_HEIGHT)), {}

    titik_marker = deteksi_empat_marker(frame, detector)
    if urutan_marker_lengkap(titik_marker):
        return warp_perspektif(frame, titik_marker), titik_marker
    return None, titik_marker


def klasifikasikan_warna(area_maket):
    """
    Untuk setiap piksel, cari level topografi dengan warna referensi
    paling dekat. -1 jika tidak cocok dengan level manapun.
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
    """Gambar garis kontur di batas antar-level topografi."""
    hasil = peta_warna.copy()

    for idx in range(len(LAPISAN_TOPOGRAFI) - 1):
        mask_atas = (peta_level >= 0) & (peta_level == idx)
        mask_naik = (peta_level == idx + 1)

        gabungan = (mask_atas | mask_naik).astype(np.uint8) * 255
        if gabungan.sum() == 0:
            continue

        kontur, _ = cv2.findContours(gabungan, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(hasil, kontur, -1, WARNA_KONTUR, KETEBALAN_KONTUR)

    return hasil


def tambah_legenda(gambar):
    """Tempel legenda warna di pojok kanan atas hasil output."""
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


def buat_layar_hitam():
    """Layar hitam total untuk proyektor (tanpa teks apa pun,
    supaya tidak ada cahaya yang jatuh ke maket)."""
    return np.zeros((OUTPUT_HEIGHT, OUTPUT_WIDTH, 3), dtype=np.uint8)


# ============================================================
# PROGRAM UTAMA
# ============================================================

def main():
    print("=" * 60)
    print("MAKET TOPOGRAFI INTERAKTIF - MVP")
    print("=" * 60)
    print(f"Membuka kamera ID {CAMERA_ID}...")
    print("Kontrol: 'q' keluar | 'd' toggle debug mode | SPASI scan")
    print(f"Jeda layar hitam sebelum scan: {JEDA_LAYAR_HITAM} detik")
    print()

    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print(f"GAGAL membuka kamera ID {CAMERA_ID}.")
        print("Coba ganti CAMERA_ID di bagian atas file ini ke 1 atau 2.")
        return

    detector = buat_aruco_detector()

    cv2.namedWindow("Kamera (deteksi marker)", cv2.WINDOW_NORMAL)
    cv2.namedWindow("OUTPUT PROYEKTOR", cv2.WINDOW_NORMAL)

    debug_mode = False

    # Layar proyektor statis: hanya berubah saat proses scan.
    layar_output_terkini = buat_layar_hitam()
    cv2.putText(layar_output_terkini, "Tekan SPASI untuk scan pertama",
                (20, OUTPUT_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (255, 255, 255), 2)

    # State proses scan
    sedang_scan = False        # True selama layar hitam menunggu
    waktu_mulai_scan = 0.0
    output_sebelum_scan = None  # cadangan, dipulihkan kalau scan gagal

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Gagal membaca frame dari kamera.")
            break

        frame_tampil = frame.copy()

        # --- Preview live: deteksi marker & status (selalu jalan) ---
        area_maket, titik_marker = ambil_area_maket(frame, detector, debug_mode)
        area_maket_siap = area_maket is not None

        if debug_mode:
            cv2.putText(frame_tampil, "DEBUG MODE: skip deteksi marker",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            for marker_id, pusat in titik_marker.items():
                cv2.circle(frame_tampil, tuple(pusat.astype(int)), 8, (0, 255, 0), -1)
                cv2.putText(frame_tampil, str(marker_id),
                            tuple(pusat.astype(int) + np.array([10, -10])),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            jumlah = len(titik_marker)
            warna_status = (0, 255, 0) if jumlah == 4 else (0, 165, 255)
            cv2.putText(frame_tampil, f"Marker terdeteksi: {jumlah}/4", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, warna_status, 2)

        # --- Proses scan (non-blocking, preview kamera tetap hidup) ---
        if sedang_scan:
            sisa = JEDA_LAYAR_HITAM - (time.time() - waktu_mulai_scan)

            if sisa > 0:
                cv2.putText(frame_tampil, f"Layar hitam... scan dalam {sisa:.1f} dtk",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            else:
                # Waktunya scan. Buang frame lama dari buffer kamera supaya
                # frame yang dipakai benar-benar diambil saat layar hitam.
                for _ in range(BUANG_FRAME_BUFFER):
                    cap.grab()
                ret_scan, frame_scan = cap.read()

                area_scan = None
                if ret_scan:
                    area_scan, _ = ambil_area_maket(frame_scan, detector, debug_mode)

                if area_scan is not None:
                    print("SCAN: membaca warna & memperbarui output...")
                    peta_level = klasifikasikan_warna(area_scan)
                    peta_warna = buat_peta_warna(peta_level)
                    hasil_kontur = gambar_kontur(peta_warna, peta_level)
                    layar_output_terkini = tambah_legenda(hasil_kontur)
                    print("SCAN selesai. Output diperbarui.")
                else:
                    print("SCAN dibatalkan: marker tidak terbaca saat layar hitam. "
                          "Output lama dikembalikan.")
                    layar_output_terkini = output_sebelum_scan

                sedang_scan = False
                output_sebelum_scan = None
        else:
            if area_maket_siap:
                cv2.putText(frame_tampil, "Tekan SPASI untuk SCAN",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(frame_tampil, "Belum siap discan",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        cv2.imshow("Kamera (deteksi marker)", frame_tampil)
        cv2.imshow("OUTPUT PROYEKTOR", layar_output_terkini)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d'):
            debug_mode = not debug_mode
            print(f"Debug mode: {'ON' if debug_mode else 'OFF'}")
        elif key == ord(' '):
            if sedang_scan:
                print("Scan sedang berjalan, tunggu sebentar.")
            elif area_maket_siap:
                print("SPASI: layar proyektor jadi hitam, menunggu sebelum scan...")
                output_sebelum_scan = layar_output_terkini
                layar_output_terkini = buat_layar_hitam()
                waktu_mulai_scan = time.time()
                sedang_scan = True
            else:
                print("SCAN dibatalkan: area maket belum siap (marker belum lengkap).")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
