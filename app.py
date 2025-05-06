import streamlit as st
import pdfplumber
import pandas as pd
import re
import tempfile
import os
import shutil
import zipfile
from datetime import datetime
import io
import base64

# Fungsi untuk membersihkan teks
def clean_text(text, is_name_or_pob=False):
    text = re.sub(r"Reference No|Payment Receipt No|Jenis Kelamin|Kewarganegaraan|Pekerjaan|Alamat", "", text)
    if is_name_or_pob:
        text = re.sub(r"\.", "", text)
    text = re.sub(r"[^A-Za-z0-9\s,./-]", "", text).strip()
    return " ".join(text.split())

# Fungsi untuk format tanggal
def format_date(date_str):
    match = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", date_str)
    if match:
        day, month, year = match.groups()
        return f"{day}/{month}/{year}"
    return date_str

# Fungsi untuk membagi tempat dan tanggal lahir
def split_birth_place_date(text):
    if text:
        parts = text.split(", ")
        if len(parts) == 2:
            return parts[0].strip(), format_date(parts[1])
    return text, None

# Ekstraksi SKTT
def extract_sktt(text):
    nik = re.search(r'NIK/Number of Population Identity\s*:\s*(\d+)', text)
    name = re.search(r'Nama/Name\s*:\s*([\w\s]+)', text)
    gender = re.search(r'Jenis Kelamin/Sex\s*:\s*(MALE|FEMALE)', text)
    birth_place_date = re.search(r'Tempat/Tgl Lahir\s*:\s*([\w\s,0-9-]+)', text)
    nationality = re.search(r'Kewarganegaraan/Nationality\s*:\s*([\w\s]+)', text)
    occupation = re.search(r'Pekerjaan/Occupation\s*:\s*([\w\s]+)', text)
    address = re.search(r'Alamat/Address\s*:\s*([\w\s,./-]+)', text)
    kitab_kitas = re.search(r'Nomor KITAP/KITAS Number\s*:\s*([\w-]+)', text)
    expiry_date = re.search(r'Berlaku Hingga s.d/Expired date\s*:\s*([\d-]+)', text)

    birth_place, birth_date = split_birth_place_date(birth_place_date.group(1)) if birth_place_date else (None, None)

    return {
        "NIK": nik.group(1) if nik else None,
        "Name": clean_text(name.group(1), is_name_or_pob=True) if name else None,
        "Jenis Kelamin": gender.group(1) if gender else None,
        "Place of Birth": clean_text(birth_place, is_name_or_pob=True) if birth_place else None,
        "Date of Birth": birth_date,
        "Nationality": clean_text(nationality.group(1)) if nationality else None,
        "Occupation": clean_text(occupation.group(1)) if occupation else None,
        "Address": clean_text(address.group(1)) if address else None,
        "KITAS/KITAP": clean_text(kitab_kitas.group(1)) if kitab_kitas else None,
        "Passport Expiry": format_date(expiry_date.group(1)) if expiry_date else None,
        "Jenis Dokumen": "SKTT"
    }

# Ekstraksi EVLN
def extract_evln(text):
    data = {
        "Name": "",
        "Place of Birth": "",
        "Date of Birth": "",
        "Passport No": "",
        "Passport Expiry": "",
        "Jenis Dokumen": "EVLN"
    }

    for line in text.split("\n"):
        if re.search(r"(?i)\bName\b|\bNama\b", line):
            parts = line.split(":")
            if len(parts) > 1:
                data["Name"] = clean_text(parts[1], is_name_or_pob=True)
        elif re.search(r"(?i)\bPlace of Birth\b|\bTempat Lahir\b", line):
            parts = line.split(":")
            if len(parts) > 1:
                data["Place of Birth"] = clean_text(parts[1], is_name_or_pob=True)
        elif re.search(r"(?i)\bDate of Birth\b|\bTanggal Lahir\b", line):
            match = re.search(r"(\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})", line)
            if match:
                data["Date of Birth"] = format_date(match.group(1))
        elif re.search(r"(?i)\bPassport No\b", line):
            match = re.search(r"\b([A-Z0-9]+)\b", line)
            if match:
                data["Passport No"] = match.group(1)
        elif re.search(r"(?i)\bPassport Expiry\b", line):
            match = re.search(r"(\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})", line)
            if match:
                data["Passport Expiry"] = format_date(match.group(1))

    return data

# Ekstraksi ITAS
def extract_itas(text):
    data = {}

    name_match = re.search(r"([A-Z\s]+)\nPERMIT NUMBER", text)
    data["Name"] = name_match.group(1).strip() if name_match else None

    permit_match = re.search(r"PERMIT NUMBER\s*:\s*([A-Z0-9-]+)", text)
    data["Permit Number"] = permit_match.group(1) if permit_match else None

    expiry_match = re.search(r"STAY PERMIT EXPIRY\s*:\s*([\d/]+)", text)
    data["Stay Permit Expiry"] = expiry_match.group(1) if expiry_match else None

    place_date_birth_match = re.search(r"Place / Date of Birth\s*.*:\s*([A-Za-z\s]+)\s*/\s*([\d-]+)", text)
    if place_date_birth_match:
        place = place_date_birth_match.group(1).strip()
        date = place_date_birth_match.group(2).strip()
        data["Place & Date of Birth"] = f"{place}, {format_date(date)}"
    else:
        data["Place & Date of Birth"] = None

    passport_match = re.search(r"Passport Number\s*: ([A-Z0-9]+)", text)
    data["Passport Number"] = passport_match.group(1) if passport_match else None

    passport_expiry_match = re.search(r"Passport Expiry\s*: ([\d-]+)", text)
    data["Passport Expiry"] = passport_expiry_match.group(1) if passport_expiry_match else None

    nationality_match = re.search(r"Nationality\s*: ([A-Z]+)", text)
    data["Nationality"] = nationality_match.group(1) if nationality_match else None

    gender_match = re.search(r"Gender\s*: ([A-Z]+)", text)
    data["Gender"] = gender_match.group(1) if gender_match else None

    address_match = re.search(r"Address\s*:\s*(.+)", text)
    data["Address"] = address_match.group(1).strip() if address_match else None

    occupation_match = re.search(r"Occupation\s*:\s*(.+)", text)
    data["Occupation"] = occupation_match.group(1).strip() if occupation_match else None

    guarantor_match = re.search(r"Guarantor\s*:\s*(.+)", text)
    data["Guarantor"] = guarantor_match.group(1).strip() if guarantor_match else None

    data["Jenis Dokumen"] = "ITAS"

    return data

# Ekstraksi ITK
def extract_itk(text):
    data = {}

    name_match = re.search(r"([A-Z\s]+)\nPERMIT NUMBER", text)
    data["Name"] = name_match.group(1).strip() if name_match else None

    permit_match = re.search(r"PERMIT NUMBER\s*:\s*([A-Z0-9-]+)", text)
    data["Permit Number"] = permit_match.group(1) if permit_match else None

    expiry_match = re.search(r"STAY PERMIT EXPIRY\s*:\s*([\d/]+)", text)
    data["Stay Permit Expiry"] = expiry_match.group(1) if expiry_match else None

    place_date_birth_match = re.search(r"Place / Date of Birth\s*.*:\s*([A-Za-z\s]+)\s*/\s*([\d-]+)", text)
    if place_date_birth_match:
        place = place_date_birth_match.group(1).strip()
        date = place_date_birth_match.group(2).strip()
        data["Place & Date of Birth"] = f"{place}, {format_date(date)}"
    else:
        data["Place & Date of Birth"] = None

    passport_match = re.search(r"Passport Number\s*: ([A-Z0-9]+)", text)
    data["Passport Number"] = passport_match.group(1) if passport_match else None

    passport_expiry_match = re.search(r"Passport Expiry\s*: ([\d-]+)", text)
    data["Passport Expiry"] = passport_expiry_match.group(1) if passport_expiry_match else None

    nationality_match = re.search(r"Nationality\s*: ([A-Z]+)", text)
    data["Nationality"] = nationality_match.group(1) if nationality_match else None

    gender_match = re.search(r"Gender\s*: ([A-Z]+)", text)
    data["Gender"] = gender_match.group(1) if gender_match else None

    address_match = re.search(r"Address\s*:\s*(.+)", text)
    data["Address"] = address_match.group(1).strip() if address_match else None

    occupation_match = re.search(r"Occupation\s*:\s*(.+)", text)
    data["Occupation"] = occupation_match.group(1).strip() if occupation_match else None

    guarantor_match = re.search(r"Guarantor\s*:\s*(.+)", text)
    data["Guarantor"] = guarantor_match.group(1).strip() if guarantor_match else None

    data["Jenis Dokumen"] = "ITK"

    return data

# File Notifikasi
def extract_notifikasi(text):
    data = {
        "Nomor Keputusan": "",
        "Nama TKA": "",
        "Tempat/Tanggal Lahir": "",
        "Kewarganegaraan": "",
        "Alamat Tempat Tinggal": "",
        "Nomor Paspor": "",
        "Jabatan": "",
        "Lokasi Kerja": "",
        "Berlaku": ""
    }

    def find(pattern):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""
    
    # Ekstraksi nomor keputusan, contoh: B.3/121986/PK.04.01/IX/2024
    nomor_keputusan_match = re.search(r"NOMOR\s+([A-Z0-9./-]+)", text, re.IGNORECASE)
    data["Nomor Keputusan"] = nomor_keputusan_match.group(1).strip() if nomor_keputusan_match else ""

    data["Nama TKA"] = find(r"Nama TKA\s*:\s*(.*)")
    data["Tempat/Tanggal Lahir"] = find(r"Tempat/Tanggal Lahir\s*:\s*(.*)")
    data["Kewarganegaraan"] = find(r"Kewarganegaraan\s*:\s*(.*)")
    data["Alamat Tempat Tinggal"] = find(r"Alamat Tempat Tinggal\s*:\s*(.*)")
    data["Nomor Paspor"] = find(r"Nomor Paspor\s*:\s*(.*)")
    data["Jabatan"] = find(r"Jabatan\s*:\s*(.*)")
    data["Lokasi Kerja"] = find(r"Lokasi Kerja\s*:\s*(.*)")

    valid_match = re.search(r"Berlaku\s*:?\s*(\d{2}[-/]\d{2}[-/]\d{4})\s*(?:s\.?d\.?|sampai dengan)?\s*(\d{2}[-/]\d{2}[-/]\d{4})", text, re.IGNORECASE)
    if not valid_match:
        valid_match = re.search(r"Tanggal Berlaku\s*:?\s*(\d{2}[-/]\d{2}[-/]\d{4})\s*s\.?d\.?\s*(\d{2}[-/]\d{2}[-/]\d{4})", text, re.IGNORECASE)

    if valid_match:
        start_date = format_date(valid_match.group(1))
        end_date = format_date(valid_match.group(2))
        data["Berlaku"] = f"{start_date} - {end_date}"

    return data

# Sanitize nama file
def sanitize_filename_part(text):
    # Biarkan spasi dan tanda hubung, hapus karakter ilegal lainnya
    return re.sub(r'[^\w\s-]', '', text).strip()

# Buat nama file baru berdasarkan data yang diekstrak
def generate_new_filename(extracted_data, use_name=True, use_passport=True):
    # Ambil value nama dari berbagai kemungkinan key
    name_raw = (
        extracted_data.get("Name") or
        extracted_data.get("Nama TKA") or
        ""
    )

    # Ambil value paspor dari berbagai kemungkinan key
    passport_raw = (
        extracted_data.get("Passport Number") or
        extracted_data.get("Nomor Paspor") or
        extracted_data.get("Passport No") or
        extracted_data.get("KITAS/KITAP") or  # Tambahan untuk SKTT
        ""
    )

    # Bersihkan isi nama dan paspor
    name = sanitize_filename_part(name_raw) if use_name and name_raw else ""
    passport = sanitize_filename_part(passport_raw) if use_passport and passport_raw else ""

    # Gabungkan untuk nama file dengan spasi
    parts = [p for p in [name, passport] if p]
    base_name = " ".join(parts) if parts else "RENAMED"
    
    return f"{base_name}.pdf"

# Salam waktu otomatis
def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Selamat Pagi"
    elif 12 <= hour < 17:
        return "Selamat Siang"
    else:
        return "Selamat Malam"

# Fungsi untuk membuat link download
def get_binary_file_downloader_html(bin_data, file_label='File', button_text='Download'):
    bin_str = base64.b64encode(bin_data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{file_label}" style="text-decoration:none;"><button style="background-color:#4CAF50; color:white; padding:10px 20px; border:none; border-radius:4px; cursor:pointer;">{button_text}</button></a>'
    return href

# Fungsi untuk memproses file PDF
def process_pdfs(uploaded_files, doc_type, use_name, use_passport):
    all_data = []
    renamed_files = {}
    
    # Buat folder sementara untuk menyimpan file
    temp_dir = tempfile.mkdtemp()
    
    for uploaded_file in uploaded_files:
        # Baca isi file PDF
        with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
            texts = [page.extract_text() for page in pdf.pages if page.extract_text()]
            full_text = "\n".join(texts)
        
        # Ekstraksi data sesuai jenis dokumen
        if doc_type == "SKTT":
            extracted_data = extract_sktt(full_text)
        elif doc_type == "EVLN":
            extracted_data = extract_evln(full_text)
        elif doc_type == "ITAS":
            extracted_data = extract_itas(full_text)
        elif doc_type == "ITK":
            extracted_data = extract_itk(full_text)
        elif doc_type == "Notifikasi":
            extracted_data = extract_notifikasi(full_text)
        else:
            extracted_data = {}
        
        all_data.append(extracted_data)
        
        # Buat nama file baru
        new_filename = generate_new_filename(extracted_data, use_name, use_passport)
        
        # Simpan file dengan nama baru di folder sementara
        temp_file_path = os.path.join(temp_dir, new_filename)
        with open(temp_file_path, 'wb') as f:
            # Reset file pointer dan tulis file asli dengan nama baru
            uploaded_file.seek(0)
            f.write(uploaded_file.read())
        
        renamed_files[uploaded_file.name] = {'new_name': new_filename, 'path': temp_file_path}
    
    # Buat DataFrame dari data yang diekstrak
    df = pd.DataFrame(all_data)
    
    # Simpan DataFrame ke Excel
    excel_path = os.path.join(temp_dir, "Hasil_Ekstraksi.xlsx")
    df.to_excel(excel_path, index=False)
    
    # Buat ZIP dari semua file yang direname
    zip_path = os.path.join(temp_dir, "Renamed_Files.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_info in renamed_files.values():
            zipf.write(file_info['path'], arcname=file_info['new_name'])
    
    return df, excel_path, renamed_files, zip_path, temp_dir

# Set konfigurasi halaman
st.set_page_config(
    page_title="Ekstraksi Dokumen Imigrasi",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sisi kiri - sidebar
with st.sidebar:
    st.image("https://via.placeholder.com/150x50?text=LDB", width=150)
    st.title("Menu")
    st.info(f"{get_greeting()}, PT Laman Davindo Bahman")
    
    st.warning("⚠️ Mohon Bayar Tagihan")
    st.button("Transfer", type="primary")
    
    st.divider()
    st.caption("© 2025 PT Laman Davindo Bahman")

# Header utama
st.title("Ekstraksi Dokumen Imigrasi")
st.write("Upload file PDF dan sistem akan mengekstrak data secara otomatis")

# Kolom untuk input
with st.container():
    st.subheader("Upload Dokumen")
    
    col1, col2 = st.columns(2)
    with col1:
        uploaded_files = st.file_uploader("Upload File PDF", type=["pdf"], accept_multiple_files=True)
    
    with col2:
        doc_type = st.selectbox(
            "Pilih Jenis Dokumen",
            ["SKTT", "EVLN", "ITAS", "ITK", "Notifikasi"]
        )
        
        use_name = st.checkbox("Gunakan Nama untuk Rename File", value=True)
        use_passport = st.checkbox("Gunakan Nomor Paspor untuk Rename File", value=True)

# Tombol proses
if uploaded_files:
    process_button = st.button("Proses PDF", type="primary", use_container_width=True)
    
    if process_button:
        with st.spinner("Sedang memproses dokumen..."):
            df, excel_path, renamed_files, zip_path, temp_dir = process_pdfs(
                uploaded_files, doc_type, use_name, use_passport
            )
            
            # Tampilkan hasil dalam tab
            tab1, tab2, tab3 = st.tabs(["Hasil Ekstraksi", "File Excel", "File Rename"])
            
            with tab1:
                st.subheader("Data Hasil Ekstraksi")
                st.dataframe(df, use_container_width=True)
            
            with tab2:
                st.subheader("Download Excel")
                with open(excel_path, "rb") as f:
                    excel_data = f.read()
                st.download_button(
                    label="Download Excel Hasil Ekstraksi",
                    data=excel_data,
                    file_name="Hasil_Ekstraksi.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with tab3:
                st.subheader("File yang Telah di-Rename")
                
                # Tampilkan daftar file
                for original_name, file_info in renamed_files.items():
                    st.write(f"**{original_name}** → **{file_info['new_name']}**")
                
                # Tombol download ZIP
                with open(zip_path, "rb") as f:
                    zip_data = f.read()
                st.download_button(
                    label="Download Semua File Rename (ZIP)",
                    data=zip_data,
                    file_name="Renamed_Files.zip",
                    mime="application/zip"
                )
            
            # Hapus folder sementara setelah selesai
            shutil.rmtree(temp_dir)
            
            st.success("Proses ekstraksi berhasil!")
else:
    st.info("Silakan upload file PDF untuk memulai.")

# Tambahkan informasi bantuan
with st.expander("Bantuan"):
    st.write("""
    **Cara Menggunakan Aplikasi:**
    1. Upload satu atau beberapa file PDF dokumen imigrasi
    2. Pilih jenis dokumen yang sesuai (SKTT, EVLN, ITAS, ITK, Notifikasi)
    3. Tentukan apakah ingin menyertakan nama dan/atau nomor paspor dalam nama file
    4. Klik tombol "Proses PDF" untuk mulai mengekstrak data
    5. Lihat dan unduh hasil ekstraksi dalam format Excel atau file PDF yang sudah direname
    
    **Catatan:** Aplikasi ini dapat menangani beberapa jenis dokumen imigrasi Indonesia dan akan secara otomatis mengekstrak informasi penting dari dokumen-dokumen tersebut.
    """)
