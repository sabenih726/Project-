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
        "admin": hash_password("admin123"),
        "petugas": hash_password("petugas123"),
        "manager": hash_password("manager123")
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

# ... (semua fungsi ekstraksi dan pemrosesan file dari kode asli Anda) ...

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

# ... (semua fungsi lain dari kode asli Anda) ...

# Salam waktu otomatis
def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Selamat Pagi"
    elif 12 <= hour < 17:
        return "Selamat Siang"
    else:
        return "Selamat Malam"

# ... (fungsi-fungsi lain dari kode asli Anda) ...

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
            st.image("https://via.placeholder.com/150x50?text=LDB", width=150)
            
            st.markdown(f'<p style="font-weight: 600; font-size: 1.2rem;">{get_greeting()}, {st.session_state.username}!</p>', unsafe_allow_html=True)
            
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
            # ... (Bagian tombol proses dan pemrosesan file sama seperti di aplikasi asli Anda) ...
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
            
            # ... (Bagian pemrosesan file setelah tombol ditekan sama seperti di aplikasi asli Anda) ...
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
