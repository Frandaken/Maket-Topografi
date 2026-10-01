"""
cek_kamera.py
Mencari tahu ID kamera mana yang aktif/tersedia di sistem.

Kenapa perlu ini: laptop/PC sering punya lebih dari satu "kamera" yang
terdaftar (misal: webcam bawaan laptop di ID 0, webcam USB eksternal di
ID 1, kadang ada juga virtual camera dari aplikasi lain). CAMERA_ID di
main.py harus menunjuk ke webcam yang BENAR (untuk expo: webcam USB
sekolah yang dipasang di atas maket, BUKAN webcam bawaan laptop).

Cara pakai:
    python cek_kamera.py

Program akan mencoba ID 0 sampai 5, buka jendela preview untuk tiap ID
yang berhasil dibuka. Lihat mana yang menampilkan gambar dari webcam
maket (bukan gambar wajahmu dari webcam laptop).

Kontrol saat preview terbuka:
    SPASI atau 'n' -> lanjut ke ID berikutnya
    q              -> keluar sepenuhnya
"""

import cv2

MAKS_ID_DICOBA = 5


def main():
    print("Mencoba membuka kamera ID 0 sampai", MAKS_ID_DICOBA, "...")
    print("Jendela preview akan muncul satu per satu.")
    print("Tekan SPASI/'n' untuk lanjut ke ID berikutnya, 'q' untuk berhenti.\n")

    ditemukan = []

    for cam_id in range(MAKS_ID_DICOBA + 1):
        cap = cv2.VideoCapture(cam_id)
        if not cap.isOpened():
            print(f"ID {cam_id}: tidak tersedia / gagal dibuka")
            cap.release()
            continue

        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"ID {cam_id}: terbuka tapi tidak bisa ambil gambar")
            cap.release()
            continue

        print(f"ID {cam_id}: BERHASIL - menampilkan preview, lihat jendela...")
        ditemukan.append(cam_id)

        berhenti_semua = False
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            tampil = frame.copy()
            cv2.putText(tampil, f"CAMERA_ID = {cam_id}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            cv2.putText(tampil, "SPASI/n = lanjut, q = keluar", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imshow("Cek Kamera - lihat ID di pojok kiri atas", tampil)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                berhenti_semua = True
                break
            elif key == ord('n') or key == ord(' '):
                break

        cap.release()
        cv2.destroyAllWindows()

        if berhenti_semua:
            break

    print("\nRingkasan ID kamera yang berhasil dibuka:", ditemukan)
    print("Gunakan ID yang menampilkan gambar webcam maket sebagai CAMERA_ID di main.py")


if __name__ == "__main__":
    main()
