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
import hashlib
import json

# Fungsi untuk hashing password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Fungsi untuk memeriksa kredensial
def check_credentials(username, password):
    # Dalam implementasi nyata, gunakan database atau file yang lebih aman
    # Ini hanya contoh sederhana
    users = {
        "sinta": hash_password("sinta123"),
        "ainun": hash_password("ainun123"),
        "fatih": hash_password("fatih123")
    }
    
    hashed_pw = hash_password(password)
    if username in users and users[username] == hashed_pw:
        return True
    return False

# Fungsi untuk membersihkan teks (dari kode asli Anda)
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

# Inisialisasi session state untuk login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'login_attempt' not in st.session_state:
    st.session_state.login_attempt = 0

# Fungsi untuk login
def login():
    if st.session_state.username and st.session_state.password:
        if check_credentials(st.session_state.username, st.session_state.password):
            st.session_state.logged_in = True
            st.session_state.login_attempt = 0
        else:
            st.session_state.login_attempt += 1

# Fungsi untuk logout
def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""

# Halaman Login
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('''
        <div style="text-align: center; padding: 2rem 0;">
            <h1 style="margin-bottom: 0.5rem;">🖥️ PT LAMAN DAVINDO BAHMAN</h1>
            <p style="opacity: 0.8; margin-bottom: 2rem;">Sistem Ekstraksi Dokumen Imigrasi</p>
        </div>
        ''', unsafe_allow_html=True)
        
        # Card login dengan styling yang lebih baik
        st.markdown('''
        <div style="background-color: white; border-radius: 0.5rem; padding: 2rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
            <h2 style="text-align: center; margin-bottom: 1.5rem;">Login Pengguna</h2>
        ''', unsafe_allow_html=True)
        
        # Form login
        with st.form("login_form"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            
            # Tampilkan pesan error jika login gagal
            if st.session_state.login_attempt > 0:
                st.error(f"Username atau password salah! (Percobaan ke-{st.session_state.login_attempt})")
            
            # Tombol login
            col1, col2 = st.columns([3, 1])
            with col1:
                submit = st.form_submit_button("Login", on_click=login, use_container_width=True)
            with col2:
                demo = st.form_submit_button("Demo", use_container_width=True)
                if demo:
                    st.session_state.username = "demo"
                    st.session_state.password = "demo123"
                    login()
        
        st.markdown('''
        <div style="text-align: center; margin-top: 1rem;">
            <p style="color: #64748b; font-size: 0.85rem;">© 2025 PT Laman Davindo Bahman</p>
            <p style="color: #94a3b8; font-size: 0.75rem;">Versi 1.0.0</p>
        </div>
        ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# Aplikasi Utama
def main():
    # Cek status login
    if not st.session_state.logged_in:
        login_page()
    else:
        # Sisi kiri - sidebar
        with st.sidebar:
            st.markdown('<div class="sidebar-header">PT LAMAN DAVINDO BAHMAN</div>', unsafe_allow_html=True)
                        
            st.markdown(f'<p style="font-weight: 600; font-size: 1.2rem;">{get_greeting()}</p>', unsafe_allow_html=True)
            
            st.markdown('<div class="alert-warning">⚠️ Mohon Bayar Tagihan</div>', unsafe_allow_html=True)
            st.button("Transfer", type="primary")
            
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            
            with st.expander("📋 Menu Utama"):
                st.markdown("- 🏠 Beranda")
                st.markdown("- 📄 Dokumen")
                st.markdown("- 👥 Klien")
                st.markdown("- ⚙️ Pengaturan")
            
            # Tombol logout di sidebar
            if st.button("Logout", type="secondary", use_container_width=True):
                logout()
                st.rerun()
            
            st.caption("© 2025 PT Laman Davindo Bahman")

        # Header utama
        st.markdown('<div class="header"><h1 style="margin-bottom: 0.5rem;">📑 Ekstraksi Dokumen Imigrasi</h1><p style="opacity: 0.8;">Upload file PDF dan sistem akan mengekstrak data secara otomatis</p></div>', unsafe_allow_html=True)

        # Kolom untuk input
        st.markdown('<div class="container">', unsafe_allow_html=True)
        st.markdown('<h2>Upload Dokumen</h2>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="uploadfile">', unsafe_allow_html=True)
            uploaded_files = st.file_uploader("Upload File PDF", type=["pdf"], accept_multiple_files=True)
            if not uploaded_files:
                st.markdown('<p style="color: #64748b; margin-top: 10px;">Tarik file PDF ke sini atau klik untuk memilih</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            doc_type = st.selectbox(
                "Pilih Jenis Dokumen",
                ["SKTT", "EVLN", "ITAS", "ITK", "Notifikasi"]
            )
            
            st.markdown('<div style="margin-top: 1rem;">', unsafe_allow_html=True)
            use_name = st.checkbox("Gunakan Nama untuk Rename File", value=True)
            use_passport = st.checkbox("Gunakan Nomor Paspor untuk Rename File", value=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Display badge untuk jenis dokumen
            if doc_type:
                badge_color = {
                    "SKTT": "#0284c7",
                    "EVLN": "#7c3aed",
                    "ITAS": "#16a34a",
                    "ITK": "#ca8a04",
                    "Notifikasi": "#e11d48"
                }.get(doc_type, "#64748b")
                
                st.markdown(f'''
                <div style="margin-top: 1rem;">
                    <span style="background-color: {badge_color}; color: white; padding: 0.3rem 0.6rem; 
                    border-radius: 0.25rem; font-size: 0.8rem; font-weight: 600;">
                        {doc_type}
                    </span>
                    <span style="font-size: 0.85rem; margin-left: 0.5rem; color: #64748b;">Terpilih</span>
                </div>
                ''', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Tombol proses
        if uploaded_files:
            st.markdown('<div class="container">', unsafe_allow_html=True)
    
            # Panel informasi file
            st.markdown('<h3>File yang Diupload</h3>', unsafe_allow_html=True)
            file_info_cols = st.columns(len(uploaded_files) if len(uploaded_files) <= 3 else 3)
    
            for i, uploaded_file in enumerate(uploaded_files):
                col_idx = i % 3
                with file_info_cols[col_idx]:
                    st.markdown(f'''
                    <div style="background-color: #f8fafc; border-radius: 0.5rem; padding: 0.75rem; margin-bottom: 0.75rem;">
                        <div style="display: flex; align-items: center;">
                            <div style="background-color: #e2e8f0; border-radius: 0.375rem; padding: 0.5rem; margin-right: 0.75rem;">
                                📄
                            </div>
                            <div>
                                <p style="margin: 0; font-weight: 600; font-size: 0.9rem;">{uploaded_file.name}</p>
                                <p style="margin: 0; color: #64748b; font-size: 0.8rem;">PDF Document</p>
                            </div>
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
    
            # Tombol proses dengan style Tailwind-like
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                    process_button = st.button(
                    f"Proses {len(uploaded_files)} File PDF", 
                    type="primary", 
                    use_container_width=True,
                    key="process_button"
                )
    
            st.markdown('</div>', unsafe_allow_html=True)
    
            if process_button:
                # Tambahkan progress bar yang lebih menarik
                progress_placeholder = st.empty()
                progress_placeholder.markdown('''
                <div style="background-color: #f1f5f9; border-radius: 0.5rem; padding: 1.5rem; text-align: center;">
                    <div style="margin-bottom: 1rem;">
                        <img src="https://via.placeholder.com/50x50?text=⚙️" width="50" height="50" style="margin: 0 auto;">
                    </div>
                    <h3 style="margin-bottom: 0.5rem;">Memproses Dokumen</h3>
                    <p style="color: #64748b;">Mohon tunggu sebentar sementara kami mengekstrak informasi dari dokumen Anda...</p>
                    <div style="margin-top: 1rem; height: 0.5rem; background-color: #e2e8f0; border-radius: 1rem; overflow: hidden;">
                        <div style="width: 75%; height: 100%; background: linear-gradient(90deg, #0ea5e9, #3b82f6); border-radius: 1rem; animation: progress 2s infinite;"></div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
        
                # Proses file
                df, excel_path, renamed_files, zip_path, temp_dir = process_pdfs(
                    uploaded_files, doc_type, use_name, use_passport
                )
        
                # Hapus placeholder progress
                progress_placeholder.empty()
        
                # Tampilkan hasil dalam tab dengan styling yang lebih baik
                st.markdown('<div class="container">', unsafe_allow_html=True)
                st.markdown('''
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <div style="background-color: #d1fae5; color: #047857; border-radius: 50%; width: 2rem; height: 2rem; display: flex; align-items: center; justify-content: center; margin-right: 0.75rem;">
                        ✓
                    </div>
                    <h2 style="margin: 0;">Proses Berhasil</h2>
                </div>
                ''', unsafe_allow_html=True)
        
                tab1, tab2, tab3 = st.tabs(["💾 Hasil Ekstraksi", "📊 File Excel", "📁 File Rename"])
        
                with tab1:
                    st.subheader("Data Hasil Ekstraksi")
                    st.markdown('<div style="overflow-x: auto;">', unsafe_allow_html=True)
                    st.dataframe(df, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            
                    # Tambahkan ringkasan data
                    st.markdown(f'''
                    <div style="display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1rem;">
                        <div style="background-color: #f0f9ff; border-radius: 0.5rem; padding: 1rem; flex: 1;">
                            <h4 style="margin: 0 0 0.5rem 0; color: #0369a1;">Total Data</h4>
                            <p style="font-size: 1.5rem; font-weight: 600; margin: 0;">{len(df)}</p>
                        </div>
                        <div style="background-color: #f0fdf4; border-radius: 0.5rem; padding: 1rem; flex: 1;">
                            <h4 style="margin: 0 0 0.5rem 0; color: #166534;">Jenis Dokumen</h4>
                            <p style="font-size: 1.5rem; font-weight: 600; margin: 0;">{doc_type}</p>
                        </div>
                        <div style="background-color: #fef3c7; border-radius: 0.5rem; padding: 1rem; flex: 1;">
                            <h4 style="margin: 0 0 0.5rem 0; color: #92400e;">File Diproses</h4>
                            <p style="font-size: 1.5rem; font-weight: 600; margin: 0;">{len(uploaded_files)}</p>
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
        
                with tab2:
                    st.subheader("Download File Excel")
            
                    with open(excel_path, "rb") as f:
                        excel_data = f.read()
            
                    # Tampilan download lebih menarik
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown('''
                        <div style="background-color: #f8fafc; border-radius: 0.5rem; padding: 1rem; display: flex; align-items: center;">
                            <div style="background-color: #22c55e; border-radius: 0.5rem; padding: 0.75rem; margin-right: 1rem;">
                                <span style="color: white; font-size: 1.5rem;">📊</span>
                            </div>
                            <div>
                                <p style="margin: 0; font-weight: 600;">Hasil_Ekstraksi.xlsx</p>
                                <p style="margin: 0; color: #64748b; font-size: 0.85rem;">Excel Spreadsheet • Diekspor pada {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
            
                    with col2:
                        st.download_button(
                            label="Download Excel",
                            data=excel_data,
                            file_name="Hasil_Ekstraksi.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
        
                with tab3:
                    st.subheader("File yang Telah di-Rename")
            
                    # Tampilkan daftar file dengan UI yang lebih baik
                    st.markdown('<div style="background-color: #f8fafc; border-radius: 0.5rem; padding: 1rem;">', unsafe_allow_html=True)
            
                    for original_name, file_info in renamed_files.items():
                        st.markdown(f'''
                        <div style="display: flex; align-items: center; padding: 0.75rem; border-bottom: 1px solid #e2e8f0;">
                            <div style="flex: 1;">
                                <p style="margin: 0; color: #64748b; font-size: 0.85rem;">Nama Asli:</p>
                                <p style="margin: 0; font-weight: 600;">{original_name}</p>
                            </div>
                            <div style="margin: 0 1rem;">
                                <span style="color: #64748b;">→</span>
                            </div>
                            <div style="flex: 1;">
                                <p style="margin: 0; color: #64748b; font-size: 0.85rem;">Nama Baru:</p>
                                <p style="margin: 0; font-weight: 600; color: #0369a1;">{file_info['new_name']}</p>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
            
                    st.markdown('</div>', unsafe_allow_html=True)
            
                    # Tombol download ZIP
                    with open(zip_path, "rb") as f:
                        zip_data = f.read()
            
                    st.markdown('<div style="margin-top: 1rem;">', unsafe_allow_html=True)
                    st.download_button(
                        label="Download Semua File PDF (ZIP)",
                        data=zip_data,
                        file_name="Renamed_Files.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
        
                # Hapus folder sementara setelah selesai
                shutil.rmtree(temp_dir)
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('''
            <div class="alert-info">
                <h3 style="margin-top: 0;">Mulai Ekstraksi</h3>
                <p>Silakan upload file PDF dokumen imigrasi untuk memulai proses ekstraksi otomatis.</p>
                <ul style="margin-bottom: 0;">
                    <li>Pastikan file dalam format PDF</li>
                    <li>Pilih jenis dokumen yang sesuai</li>
                    <li>Sesuaikan opsi penamaan file jika diperlukan</li>
                </ul>
            </div>
            ''', unsafe_allow_html=True)
     
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

# Main program execution
if __name__ == "__main__":
    main()
