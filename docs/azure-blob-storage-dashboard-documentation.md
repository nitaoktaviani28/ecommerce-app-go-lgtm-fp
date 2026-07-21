# Dokumentasi Dashboard: Azure Blob Storage - LGTM Usage

**Dashboard UID**: `azure-blob-storage-lgtm`  
**Time Range Default**: Last 30 days  
**Datasource**: Azure Monitor (2 subscription: Observability & VS Enterprise)

---

## Panel: Storage Account Inventory

| Aspek | Detail |
|-------|--------|
| Tipe Panel | Text (Markdown) |
| Panel ID | 202 |
| Metric | Tidak ada (konten statis) |
| Datasource | Tidak ada |
| Kegunaan | Menampilkan daftar semua Azure Blob Storage account yang dimonitor beserta customer, project, environment, container, dan subscription |
| Fungsi | Referensi cepat inventaris — user langsung tahu storage mana milik siapa tanpa buka Azure Portal |

---

## Panel: Pricing

| Aspek | Detail |
|-------|--------|
| Tipe Panel | Text (Markdown) — bagian dari panel ID 202 |
| Metric | Tidak ada (konten statis) |
| Datasource | Tidak ada |
| Kegunaan | Menampilkan harga jual ke customer (Rp 20.000/GB/bulan) dan cost Azure sebagai perbandingan internal ($0.02/GB/bulan ~Rp 330/GB). Plus rumus billing: Capacity_GB × Rp 20.000 |
| Fungsi | Transparansi billing — user bisa verifikasi angka di panel billing karena rate dan rumus tertulis di sini. Juga sebagai referensi margin (jual Rp 20.000 vs modal Rp 330) |

---

## Panel: Total Storage Usage Overview (3x Stat Panel + 1 Total)

| Aspek | Detail |
|-------|--------|
| Tipe Panel | Stat (3 panel per-account + 1 panel total semua storage) |
| Panel ID | 1, 2, 3 (per-account), + panel total (manual) |
| Metric | `UsedCapacity` |
| Namespace | `Microsoft.Storage/storageAccounts` |
| Aggregation | Average (rata-rata nilai dalam 1 jam) |
| Time Grain | PT1H (data di-update setiap 1 jam oleh Azure) |
| Unit | Bytes (ditampilkan otomatis sebagai MB/GB) |
| Datasource | Azure Monitor (`azure-monitor-obs` untuk CMP, `azure-monitor-vse` untuk Ecommerce) |
| Reducer | lastNotNull — menampilkan nilai terakhir |
| Thresholds | Hijau: < 10 GB, Kuning: ≥ 10 GB, Merah: ≥ 14 GB |
| Kegunaan | Menampilkan total kapasitas storage terpakai saat ini per storage account, plus total gabungan semua account |
| Fungsi | Capacity monitoring & early warning — warna berubah kuning/merah kalau storage mendekati batas. Panel total (2.67 GB) menunjukkan total pemakaian semua customer digabung |

---

## Panel: Billing Customer (4x Stat Panel)

| Aspek | Detail |
|-------|--------|
| Tipe Panel | Stat (4 panel: CMP, Ecommerce Prod, Ecommerce Demo, Total) |
| Panel ID | 401, 402, 403, 404 |
| Metric | `UsedCapacity` (sama seperti di atas, tapi dikalkulasi jadi Rupiah) |
| Datasource | Mixed (Azure Monitor + Grafana Expression) |
| Expression | `$B / 1073741824 * 20000` (bytes → GB → × Rp 20.000) |
| Unit | none (angka plain, dalam Rupiah) |
| Decimals | 0 |
| Thresholds | Hijau: < 100K, Kuning: ≥ 100K, Orange: ≥ 500K, Merah: ≥ 1 Juta |
| Kegunaan | Menampilkan estimasi billing bulanan ke customer berdasarkan pemakaian storage real-time × harga jual Rp 20.000/GB |
| Fungsi | Revenue tracking — angka otomatis ikut naik/turun sesuai pemakaian, bisa dipakai sebagai dasar invoice ke customer |

**Alur query (per-storage panel):**
1. **A** → Query Azure Monitor: `UsedCapacity` (hidden)
2. **B** → Expression Reduce: ambil nilai terakhir dari A (hidden)
3. **C** → Expression Math: `$B / 1073741824 * 20000` (visible, ini yang tampil)

**Alur query (Total panel):**
1. **A,B,C** → Query UsedCapacity dari 3 storage account (hidden)
2. **D,E,F** → Reduce masing-masing ke nilai terakhir (hidden)
3. **Total** → Math: `($D + $E + $F) / 1073741824 * 20000` (visible)

---

## Panel: Transactions per Storage Account

| Aspek | Detail |
|-------|--------|
| Tipe Panel | Timeseries (bar chart) |
| Panel ID | 501 |
| Metric | `Transactions` |
| Namespace | `Microsoft.Storage/storageAccounts/blobServices` |
| Aggregation | Total (jumlah semua operasi dalam 1 hari) |
| Time Grain | P1D (1 hari) |
| Unit | short (angka biasa) |
| Datasource | Mixed (Azure Monitor dari 2 subscription) |
| Legend | Table dengan calcs: Sum, Mean, Max, Last |
| Kegunaan | Menampilkan jumlah total operasi (read/write/list/delete) per hari per storage account selama 30 hari |
| Fungsi | Monitoring aktivitas — melihat pola traffic blob storage, mendeteksi spike anomali, dan sebagai data pendukung operasional |

---

## Panel: Storage Usage Over Time — All Projects

| Aspek | Detail |
|-------|--------|
| Tipe Panel | Timeseries (line chart) |
| Panel ID | 4 |
| Metric | `UsedCapacity` |
| Namespace | `Microsoft.Storage/storageAccounts` |
| Aggregation | Average |
| Time Grain | PT1H (1 jam) |
| Unit | Bytes (ditampilkan sebagai MB/GB) |
| Datasource | Mixed (Azure Monitor dari 2 subscription) |
| Legend | Table dengan calcs: Last, Min, Max, Mean, Diff |
| Kegunaan | Menampilkan trend pertumbuhan storage dari waktu ke waktu (30 hari) dalam satu grafik untuk semua storage account |
| Fungsi | Capacity planning & trend analysis — bisa lihat apakah storage naik terus, stabil, atau turun. Diff di legend menunjukkan selisih awal vs akhir periode |

---

## Panel: Blob Capacity per Container (Detail Row)

| Aspek | Detail |
|-------|--------|
| Tipe Panel | Timeseries (line chart) |
| Panel ID | 9, 5, 7 (masing-masing per storage account) |
| Metric | `BlobCapacity` |
| Namespace | `Microsoft.Storage/storageAccounts/blobServices` |
| Aggregation | Average |
| Time Grain | PT1H |
| Unit | Bytes |
| Dimension Filter | BlobType = BlockBlob |
| Kegunaan | Menampilkan breakdown storage per container (loki, mimir-blocks, tempo-traces, dll) — bisa lihat container mana yang paling banyak makan storage |
| Fungsi | Root cause analysis — kalau storage tiba-tiba naik, bisa identifikasi container mana penyebabnya |

---

## Panel: Blob Count per Container (Detail Row)

| Aspek | Detail |
|-------|--------|
| Tipe Panel | Timeseries (line chart) |
| Panel ID | 10, 6, 8 (masing-masing per storage account) |
| Metric | `BlobCount` |
| Namespace | `Microsoft.Storage/storageAccounts/blobServices` |
| Aggregation | Average |
| Time Grain | PT1H |
| Unit | short (angka) |
| Dimension Filter | BlobType = BlockBlob |
| Kegunaan | Menampilkan jumlah file/blob per container — berapa banyak object yang tersimpan |
| Fungsi | Monitoring fragmentasi — kalau blob count naik drastis tapi capacity tidak, artinya banyak file kecil (indikasi masalah compaction). Kalau count turun, berarti retention/cleanup berjalan |

---

## Glosarium

| Istilah | Penjelasan |
|---------|-----------|
| **Aggregation** | Cara merangkum banyak data jadi 1 angka per interval waktu (Average, Total, Max, Min) |
| **Time Grain** | Interval waktu Azure menghitung ulang metric. PT1H = 1 jam, P1D = 1 hari |
| **UsedCapacity** | Metric Azure yang mengukur total bytes terpakai di storage account |
| **Transactions** | Metric Azure yang menghitung jumlah panggilan API (read, write, list, delete) |
| **BlobCapacity** | Storage terpakai per container (lebih granular dari UsedCapacity) |
| **BlobCount** | Jumlah file/object di setiap container |
| **BlockBlob** | Tipe blob yang dipakai LGTM stack (untuk menyimpan data dalam chunks) |
| **Grafana Expression** | Server-side calculation di Grafana untuk mengolah data (reduce, math) |
| **lastNotNull** | Reducer yang mengambil nilai terakhir yang bukan null |
