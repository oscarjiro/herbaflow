# Ringkasan Validasi untuk Sidang

Ringkas, siap dibawa saat pengujian. Menjelaskan setiap selisih angka antara keluaran
sistem dan studi pembanding Kawiswara dkk. (diabetes mellitus).

---

## Tabel perbandingan

| Besaran | Studi pembanding | Sistem | Sebab selisih |
| --- | --- | --- | --- |
| Target tanaman unik | **784** | **778** (diterima 1:1) | Perbedaan versi dataset di hulu. Sistem tidak membuang target apa pun. |
| Target penyakit, tingkat gen | **575** | **573** (505 protein + 68 non-protein) | Perbedaan versi dataset dua target. Himpunan praktis sama. |
| Target penyakit yang dipakai | 575 | **505** protein | Sistem membuang 68 gen non-protein dan menggabungkan 76 sinonim. |
| Irisan target | **73** | **77** (memuat seluruh 73) | Pemulihan 100% ditambah 4 target: 2 penyatuan sinonim, 2 perbedaan dataset. |
| Target hub bersama | 10 | **4 dari 10** (TNF, BCL2, ALB, IL2) | Metode pemeringkatan berbeda: MCC lawan Skyline query. |

**Dua metrik utama:** pemulihan target irisan **100%** (73/73), pemulihan target hub **40%** (4/10).

---

## Penjelasan tiap selisih

### 1. Target tanaman: 778 lawan 784
Berkas masukan berisi 778 target, dan sistem menerima seluruhnya satu-ke-satu (tidak ada
yang ditolak atau digabungkan). Selisih enam target berasal dari perbedaan versi dataset
yang digunakan ulang, bukan dari pemrosesan sistem.

### 2. Target penyakit: dari 649 token menjadi 505 protein
Berkas penyakit (570 baris, sebagian memuat banyak gen per baris) dipisahkan menjadi 649
token unik. Alurnya:

```
649 token unik
 − 76  sinonim/alias yang menunjuk protein yang sama  (digabungkan)
 = 573 gen unik   ( = 505 protein + 68 non-protein )
 − 68  gen non-protein dibuang
 = 505 target protein yang dipakai
```

- **573** = jumlah gen unik sebelum pembuangan 68 non-protein (inilah angka yang setara
  dengan 575 milik studi pembanding, selisih hanya dua = perbedaan versi dataset).
- **505** = target protein yang benar-benar masuk ke perhitungan irisan.

### 3. Mengapa 68 gen ditolak (RNA non-koding)
66 gen dikenali tetapi tidak memiliki protein di UniProt (umumnya RNA non-koding seperti
miRNA atau lncRNA), dan 2 identifier tidak dikenali. Jaringan interaksi protein-protein
hanya dibangun atas protein, sehingga gen tanpa protein tidak punya simpul dan tidak dapat
dipakai. Penolakan ini benar dan dilaporkan dengan alasan jelas per masukan.

### 4. Bagaimana sistem menggabungkan sinonim (76 baris)
Setiap simbol gen atau nomor akses UniProt dinormalisasi ke satu protein manusia kanonik:
simbol gen dinormalkan ke simbol HGNC resmi lalu ke nomor akses primer UniProt, dan alias
maupun nomor akses sekunder disatukan ke nomor akses primernya. Dua simbol berbeda yang
menunjuk protein yang sama menyatu menjadi satu target. Karena itu satu protein hanya
dihitung sekali.

### 5. Irisan: 77 sebagai superset dari 73 (mengapa +4)
Seluruh 73 target acuan termuat pada 77 target sistem (pemulihan 100%). Empat target
tambahan:

| Target | Sebab |
| --- | --- |
| **GBA1** | Sistem menyatukan penggantian nama simbol gen: tanaman `GBA` (nama lama), penyakit `GBA1` (nama baru). Pencocokan string menganggapnya beda; sistem memetakan ke protein yang sama. |
| **MARS1** | Pola sama: tanaman `MARS`, penyakit `MARS1`. |
| **DYRK1B** | Perbedaan versi dataset yang digunakan ulang. |
| **PPARG** | Perbedaan versi dataset. PPARG adalah target obat diabetes yang dikenal luas dan juga menjadi target hub sistem, contoh target relevan yang tidak tercakup pada irisan studi pembanding. |

GBA1 dan MARS1 menunjukkan keunggulan irisan berbasis identitas protein kanonik dibanding
irisan berbasis string. DYRK1B dan PPARG berasal dari perbedaan versi dataset yang sama yang
menjelaskan selisih 778/784 dan 573/575.

### 6. Target hub: 40% karena metode berbeda
Sistem memakai Maximal Clique Centrality (MCC), studi pembanding memakai Skyline query atas
empat ukuran sentralitas. Metode berbeda menghasilkan peringkat berbeda. Empat target
bersama (TNF, BCL2, ALB, IL2) adalah protein sentral yang disepakati kedua metode. Metrik
ini dibaca sebagai kesamaan anggota daftar, bukan kesamaan peringkat.

---

## Antisipasi pertanyaan penguji

- **"Mengapa irisan Anda lebih banyak dari studi pembanding?"**
  Karena 77 adalah superset yang memuat seluruh 73 target acuan. Empat tambahannya
  dijelaskan: dua dari penyatuan sinonim (GBA1, MARS1), dua dari perbedaan versi dataset
  (DYRK1B, PPARG). Irisan berbasis identitas protein kanonik menangkap kecocokan yang
  terlewat oleh pencocokan string.

- **"Katanya 575 target penyakit, tetapi sistem memakai 505. Jelaskan."**
  575 adalah jumlah baris dataset. Pada tataran gen, dataset saya berisi 573 gen unik
  (selisih dua dari 575). Sistem lalu membuang 68 gen non-protein dan menggabungkan 76
  sinonim, sehingga tersisa 505 target protein yang dipakai. Semua angka saling menutup.

- **"Apa yang sebenarnya divalidasi metrik pemulihan 100%?"**
  Karena target acuan dimasukkan langsung, metrik ini menguji kemampuan sistem memvalidasi,
  menormalisasi, menggabungkan, dan mengiriskan target, bukan tahap prediksi biologisnya.
  Ini adalah validasi sistem, dan disebut demikian secara jujur pada naskah.

- **"Mengapa pemulihan hub hanya 40%?"**
  Karena algoritma pemeringkatan berbeda (MCC lawan Skyline). Empat target sentral tetap
  sama, dan perbedaan selebihnya adalah konsekuensi metodologis, bukan kesalahan.
