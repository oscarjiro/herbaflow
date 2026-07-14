# Analisis Validasi Sistem: Studi Pembanding Kawiswara dkk. (Diabetes Mellitus)

Dokumen ini menjelaskan secara rinci hasil validasi sistem terhadap studi pembanding
network pharmacology oleh Kawiswara dkk. (2026), yang meneliti *Curcuma amada* Roxb.,
*Curcuma longa*, dan *Allium cepa* L. var. *aggregatum* terhadap diabetes mellitus.
Fokusnya adalah menjelaskan setiap perbedaan angka antara keluaran sistem dan studi
pembanding, sehingga setiap selisih dapat dipertanggungjawabkan pada saat pengujian.

Semua angka pada dokumen ini diperoleh dengan menjalankan ulang validasi pada berkas
masukan yang sama (`docs/validation/kawiswara/inputs/`) dan mencocokkannya dengan hasil
run sistem `4d2c33e8-f225-4df7-9a90-a5bc20500930`.

---

## 1. Ringkasan hasil

Validasi menghasilkan dua metrik utama, dan keduanya kuat serta dapat dijelaskan sebab
setiap selisihnya:

- **Tingkat pemulihan target = 100%.** Seluruh 73 target irisan acuan studi pembanding
  muncul kembali pada hasil sistem. Hal ini telah diverifikasi langsung terhadap daftar
  73 target milik studi pembanding (`inputs/original-overlap.txt`), bukan sekadar klaim.
- **Tingkat pemulihan target hub = 40%.** Empat dari sepuluh target hub acuan muncul
  kembali. Angka ini wajar karena sistem memakai metode pemeringkatan yang berbeda
  (Maximal Clique Centrality) dibandingkan studi pembanding (Skyline query atas empat
  ukuran sentralitas).

Irisan sistem berjumlah 77 target, yaitu empat lebih banyak dari 73 target acuan. Empat
target tambahan tersebut bukan kesalahan, melainkan konsekuensi dari dua hal yang dapat
dijelaskan: normalisasi identitas protein yang menyatukan sinonim atau penggantian nama
simbol gen, dan perbedaan versi dataset yang digunakan ulang.

---

## 2. Angka acuan studi pembanding

Studi pembanding melaporkan pengumpulan target sebagai berikut:

| Sisi | Mentah | Setelah dedup (unik) |
| --- | --- | --- |
| Target tanaman | 1.394 target terprediksi | **784** |
| Target penyakit | 648 (88 UniProt + 5 OMIM + 163 MalaCards + 392 GeneCards) | **575** |
| Irisan tanaman ∩ penyakit | | **73** |
| Target hub (Skyline query) | | **10** |

Dengan demikian, angka acuan studi pembanding adalah **784 target tanaman**,
**575 target penyakit**, dan **73 target irisan**.

---

## 3. Alur data sisi tanaman

Berkas `cleaned-all-plants-targets.txt` berisi **778 token unik**. Sistem menerima
**seluruh 778 target secara satu-ke-satu**: tidak ada yang ditolak dan tidak ada yang
digabungkan. Hal ini terbukti dari run: jumlah target pada tahap identifikasi target
tanaman adalah 778, tanpa penghapusan.

**Selisih 778 lawan 784 terletak sepenuhnya di hulu, bukan pada sistem.** Validasi
menggunakan dataset target hasil pembersihan yang tersedia untuk pengujian ulang, bukan
mengulang seluruh proses prediksi target milik studi pembanding. Dedup yang dipakai
menyatukan token berdasarkan kecocokan string yang persis, sehingga selisih enam target
berasal dari perbedaan versi dataset yang digunakan ulang. Sistem sendiri tidak
menghilangkan satu target tanaman pun.

---

## 4. Alur data sisi penyakit

Ini adalah bagian dengan selisih paling banyak, dan seluruhnya dapat diuraikan secara
tertutup (angka-angka saling menutup).

Dataset penyakit studi pembanding yang digunakan ulang berupa berkas dengan **570 baris**.
Sebagian baris memuat lebih dari satu gen pada satu baris (spreadsheet asli tidak rapi),
sehingga skrip `clean.py` memisahkan setiap gen ke barisnya sendiri dan menghasilkan
**649 token unik**.

Sistem kemudian memvalidasi 649 token tersebut, dengan hasil berikut:

```
649 token unik
 − 76  baris sinonim/alias yang menunjuk protein yang sudah terhitung
 = 573 gen unik            ( = 505 protein + 68 non-protein )
 − 68  gen non-protein dibuang (66 RNA non-koding + 2 identifier tak dikenali)
 = 505 target protein yang dapat dipakai   ← masukan yang benar-benar digunakan run
```

Dengan demikian:

- **573** adalah jumlah gen unik sisi penyakit sebelum pembuangan 68 gen non-protein.
  Angka ini setara dengan 505 protein ditambah 68 gen non-protein.
- **505** adalah jumlah target protein yang benar-benar masuk ke perhitungan irisan.

**Perbandingan dengan studi pembanding.** Jumlah gen unik sistem (573) hanya berbeda dua
target dari jumlah unik studi pembanding (575). Selisih dua target ini adalah perbedaan
versi dataset, sehingga pada tataran himpunan gen kedua dataset praktis sama. Perbedaan
yang terlihat besar (649 menjadi 505) sepenuhnya berasal dari dua langkah pemrosesan yang
dilakukan sistem tetapi tidak dilakukan oleh spreadsheet studi pembanding: penggabungan
sinonim dan pembuangan gen non-protein.

---

## 5. Bagaimana sistem menggabungkan sinonim (76 baris)

Setiap simbol gen atau nomor akses UniProt yang dimasukkan dinormalisasi ke satu protein
manusia kanonik (organisme 9606). Simbol gen dinormalkan lebih dulu ke simbol HGNC resmi,
lalu dipetakan ke nomor akses primer UniProt. Identitas target dibangun dari nomor akses
primer tersebut, sehingga:

- Dua simbol gen yang berbeda tetapi menunjuk protein yang sama akan menyatu menjadi satu
  target.
- Nomor akses sekunder dan alias UniProt menyatu ke nomor akses primernya.

Karena itulah 76 dari 649 token menyatu ke protein yang sudah terhitung sebelumnya. Ini
adalah perilaku yang benar: satu protein hanya boleh dihitung satu kali.

---

## 6. Mengapa 68 gen ditolak (RNA non-koding)

Dari 68 gen yang ditolak, 66 adalah gen manusia yang dikenali tetapi tidak memiliki
protein di UniProt (umumnya gen RNA non-koding seperti miRNA atau lncRNA), dan 2 adalah
identifier yang tidak dikenali sebagai simbol gen maupun nomor akses UniProt manusia.

Penolakan ini benar secara ilmiah. Tahap jaringan interaksi protein-protein dibangun di
atas protein. Gen tanpa produk protein tidak memiliki simpul pada jaringan, sehingga tidak
dapat dipakai. Membuangnya menjaga jaringan tetap sahih, dan penolakannya dilaporkan
dengan alasan yang jelas per masukan, bukan dibuang secara diam-diam.

---

## 7. Hasil irisan: 77 target sebagai superset dari 73

Irisan sistem berjumlah **77 target** dan merupakan **superset** dari 73 target acuan:
seluruh 73 target acuan termuat di dalamnya (pemulihan 100%), ditambah empat target lain.

Sebagai pembanding, irisan berbasis pencocokan string biasa atas berkas masukan yang sama
hanya menghasilkan 75 target. Sistem menghasilkan 77 karena normalisasi identitas menemukan
kecocokan yang terlewat oleh pencocokan string.

Empat target tambahan dan sebabnya masing-masing:

| Target tambahan | Sebab | Penjelasan |
| --- | --- | --- |
| **GBA1** | Penyatuan penggantian nama simbol gen | Berkas tanaman memakai `GBA` (nama lama), berkas penyakit memakai `GBA1` (nama baru HGNC). Pencocokan string menganggapnya berbeda; sistem memetakan keduanya ke protein UniProt yang sama sehingga kecocokan ditemukan. |
| **MARS1** | Penyatuan penggantian nama simbol gen | Pola sama: tanaman `MARS`, penyakit `MARS1`. |
| **DYRK1B** | Perbedaan versi dataset | Muncul identik di berkas tanaman dan penyakit yang digunakan ulang, tetapi tidak ada pada daftar irisan studi pembanding. |
| **PPARG** | Perbedaan versi dataset | Sama seperti DYRK1B. Catatan: PPARG adalah target obat diabetes yang sangat dikenal (reseptor golongan tiazolidindion) dan juga menjadi salah satu target hub sistem. Sistem memunculkan protein diabetes yang relevan yang tidak tercakup pada irisan studi pembanding. |

Dua target pertama (GBA1, MARS1) menunjukkan keunggulan pendekatan sistem: irisan berbasis
identitas protein kanonik menangkap kecocokan tingkat sinonim yang tak terlihat oleh irisan
berbasis string. Dua target berikutnya (DYRK1B, PPARG) berasal dari perbedaan versi dataset
yang sama yang menjelaskan selisih 778 lawan 784 dan 573 lawan 575.

---

## 8. Hasil target hub

| Peringkat | Target hub sistem (MCC) | Target hub studi pembanding (Skyline) |
| --- | --- | --- |
| 1 | STAT3 | ACE |
| 2 | **TNF** | ADA |
| 3 | **BCL2** | **ALB** |
| 4 | PPARG | DPP4 |
| 5 | HIF1A | **TNF** |
| 6 | **ALB** | **IL2** |
| 7 | HSP90AA1 | ACP1 |
| 8 | **IL2** | AKR1B1 |
| 9 | ERBB2 | CCR5 |
| 10 | HMOX1 | **BCL2** |

Empat target yang muncul pada kedua daftar: **TNF, BCL2, ALB, IL2** (40%). Perbedaan
selebihnya adalah konsekuensi metodologis. MCC menilai keterlibatan protein pada struktur
klik jaringan, sedangkan Skyline query memilih titik optimal Pareto atas empat ukuran
sentralitas. Metode berbeda menghasilkan daftar berbeda, sehingga metrik ini lebih tepat
dibaca sebagai kesamaan anggota daftar, bukan kesamaan peringkat.

---

## 9. Tabel rekonsiliasi lengkap

| Besaran | Studi pembanding | Sistem (dataset ulang) | Sebab selisih |
| --- | --- | --- | --- |
| Target tanaman unik | 784 | 778 (diterima 1:1) | Perbedaan versi dataset di hulu; sistem tidak membuang target apa pun. |
| Target penyakit, tingkat gen | 575 | 573 (505 protein + 68 non-protein) | Perbedaan versi dataset dua target; himpunan praktis sama. |
| Target penyakit yang dipakai | 575 | 505 protein | Sistem membuang 68 gen non-protein dan menggabungkan 76 sinonim. |
| Irisan | 73 | 77 (memuat seluruh 73) | Pemulihan 100% ditambah 2 penyatuan sinonim dan 2 perbedaan dataset. |
| Target hub bersama | 10 | 4 dari 10 | Metode pemeringkatan berbeda (MCC lawan Skyline). |

---

## 10. Penilaian metode validasi dan batasannya

**Kekuatan.** Rancangan validasi ini baik untuk tujuannya. Dengan memasukkan target acuan
secara manual, validasi mengisolasi kemampuan sistem dalam memvalidasi, menormalisasi,
menggabungkan, dan mengiriskan target, terlepas dari perbedaan sumber data pada tahap
pengumpulan. Studi pembanding yang dipakai relevan dengan ruang lingkup (tumbuhan obat
Indonesia dan diabetes) dan datanya dapat digunakan ulang dengan izin. Dua metrik yang
dipakai saling melengkapi: pemulihan himpunan irisan dan kesamaan daftar hub.

**Batasan yang perlu disadari saat sidang.** Karena target acuan dimasukkan langsung,
tingkat pemulihan target terutama menguji jalur pemrosesan (penguraian, normalisasi,
penggabungan, dan pengirisan), bukan tahap prediksi biologis (pengumpulan senyawa,
penyaringan ADME, prediksi target senyawa, pengumpulan target penyakit). Bagian sistem
yang melakukan prediksi ilmiah justru dilewati pada skenario ini. Karena itu, validasi ini
paling tepat disebut validasi sistem, bukan validasi metode prediksi. Selain itu, hanya ada
satu studi kasus pembanding, sehingga tidak ada klaim statistik. Metrik hub juga dibaur oleh
perbedaan algoritma, sehingga 40% lebih merupakan kesepakatan antara dua metode sentralitas
daripada pemulihan murni. Semua batasan ini sudah dinyatakan secara jujur pada naskah dan
sebaiknya tetap ditegaskan pada saat pengujian.

---

## 11. Usulan paragraf hasil yang lebih lengkap

Paragraf hasil pada naskah saat ini belum menyebut angka 505, 649, 573, penolakan gen RNA
non-koding, maupun penggabungan sinonim, dan menjelaskan empat target tambahan hanya secara
umum. Berikut usulan paragraf yang memasukkan seluruh nuansa tersebut:

> Pada sisi penyakit, dataset pembanding yang digunakan ulang berupa berkas dengan 570
> baris. Karena sebagian baris memuat lebih dari satu gen, pemisahan gen per baris
> menghasilkan 649 token unik. Sistem kemudian menormalisasi setiap masukan ke protein
> manusia kanonik. Sebanyak 76 token merupakan sinonim atau alias yang menunjuk protein yang
> sudah terhitung sehingga digabungkan, dan 68 gen ditolak karena tidak memiliki protein di
> UniProt (66 di antaranya gen RNA non-koding) atau tidak dikenali. Setelah kedua langkah
> tersebut, diperoleh 573 gen unik yang setara dengan 505 target protein yang dapat dipakai.
> Jumlah 573 gen ini hanya berbeda dua target dari 575 target penyakit unik studi
> pembanding, sehingga pada tataran himpunan gen kedua dataset praktis sama. Pada sisi
> tanaman, sistem menerima seluruh 778 target secara satu-ke-satu, dan selisihnya terhadap
> 784 target studi pembanding berasal dari perbedaan versi dataset di hulu, bukan dari
> pemrosesan sistem.
>
> Irisan target tanaman dan target penyakit menghasilkan 77 target yang memuat seluruh 73
> target irisan acuan, sehingga tingkat pemulihan target mencapai 100%. Empat target
> tambahan dapat dijelaskan. Dua target, yaitu GBA1 dan MARS1, muncul karena normalisasi
> identitas menyatukan penggantian nama simbol gen antar-sisi (misalnya GBA pada sisi
> tanaman dan GBA1 pada sisi penyakit), yaitu kecocokan yang terlewat oleh pencocokan string.
> Dua target lainnya, yaitu DYRK1B dan PPARG, berasal dari perbedaan versi dataset yang sama.
> Kemunculan PPARG, yang merupakan target obat diabetes yang dikenal luas, memperlihatkan
> bahwa irisan berbasis identitas protein kanonik dapat memunculkan target relevan yang tidak
> tercakup pada irisan berbasis string.
