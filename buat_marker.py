"""
buat_marker.py
Menghasilkan 4 gambar marker ArUco (ID 0, 1, 2, 3) siap cetak
untuk ditempel di empat sudut area aktif maket.

Sesuai dokumen rancangan (bagian 8):
  Marker A = Kiri atas   = ID 0
  Marker B = Kanan atas  = ID 1
  Marker C = Kanan bawah = ID 2
  Marker D = Kiri bawah  = ID 3

Cara pakai:
    python buat_marker.py

Output: folder ./marker_output/ berisi marker_0.png .. marker_3.png
Cetak masing-masing, tempel di sudut area aktif sesuai tabel di atas.
Ukuran cetak disarankan minimal 5x5 cm agar mudah terbaca kamera.
"""

import cv2
import os

# Dictionary ArUco yang dipakai. HARUS SAMA dengan yang dipakai di main.py
ARUCO_DICT = cv2.aruco.DICT_4X4_50

# Ukuran gambar marker dalam pixel (bukan ukuran cetak fisik)
UKURAN_PIXEL = 600

OUTPUT_DIR = "marker_output"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)

    posisi_label = {
        0: "kiri_atas (A)",
        1: "kanan_atas (B)",
        2: "kanan_bawah (C)",
        3: "kiri_bawah (D)",
    }

    for marker_id in range(4):
        img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, UKURAN_PIXEL)
        filename = os.path.join(OUTPUT_DIR, f"marker_{marker_id}.png")
        cv2.imwrite(filename, img)
        print(f"Marker ID {marker_id} ({posisi_label[marker_id]}) -> {filename}")

    print("\nSelesai. Cetak 4 file di folder 'marker_output/'.")
    print("Tempel sesuai posisi masing-masing di sudut area aktif maket.")
    print("Pastikan marker DATAR, tidak terlipat, dan kontrasnya tinggi (hitam-putih tegas).")


if __name__ == "__main__":
    main()
