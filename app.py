import streamlit as st
import pandas as pd
import tempfile
import zipfile
import base64
import os
from datetime import datetime

# ---------------------------
# UI Styling and Visual Theme
# ---------------------------
st.set_page_config(
    page_title="Ekstraksi Dokumen Imigrasi",
    page_icon="🛂",
    layout="centered",
)

st.markdown("""
    <style>
    .main {
        background-color: #f0f2f6;
    }
    h1, h2, h3 {
        color: #0a3d62;
    }
    .stButton > button {
        background-color: #1e3799;
        color: white;
        border-radius: 8px;
        padding: 0.5em 1em;
    }
    .stDownloadButton > button {
        background-color: #38ada9;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🛂 Ekstraksi & Penamaan Ulang Dokumen PDF Imigrasi")
st.markdown("Unggah file PDF berisi SKTT, EVLN, ITAS, ITK, atau Notifikasi.")

# ---------------------------
# Helper Functions
# ---------------------------

def read_pdf(file):
    pdf = PdfReader(file)
    return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

def extract_sktt(text):
    return {
        "Jenis Dokumen": "SKTT",
        "Nama": find_between(text, "Nama", "Tempat"),
        "No Dokumen": find_between(text, "Nomor SKTT", "Tanggal"),
    }

def extract_evln(text):
    return {
        "Jenis Dokumen": "EVLN",
        "Nama": find_between(text, "Nama Lengkap", "Nomor Paspor"),
        "No Dokumen": find_between(text, "Nomor EVLN", "Tanggal"),
    }

def extract_itas(text):
    return {
        "Jenis Dokumen": "ITAS",
        "Nama": find_between(text, "Nama", "Tempat"),
        "No Dokumen": find_between(text, "Nomor ITAS", "Tanggal"),
    }

def extract_itk(text):
    return {
        "Jenis Dokumen": "ITK",
        "Nama": find_between(text, "Nama", "Kebangsaan"),
        "No Dokumen": find_between(text, "Nomor ITK", "Tanggal"),
    }

def extract_notifikasi(text):
    return {
        "Jenis Dokumen": "Notifikasi",
        "Nama": find_between(text, "Nama", "Tanggal Lahir"),
        "No Dokumen": find_between(text, "No Notifikasi", "Tanggal Berlaku"),
    }

def find_between(text, start, end):
    try:
        return text.split(start)[1].split(end)[0].strip()
    except:
        return ""

def rename_uploaded_file(file, extracted_data, use_name=True):
    name = extracted_data.get("Nama", "").strip().replace(" ", "_")
    passport = extracted_data.get("No Dokumen", "").strip().replace(" ", "_")
    parts = [p for p in [name, passport] if p]
    base_name = " ".join(parts) if parts else "RENAMED"
    new_filename = f"{base_name}.pdf"

    temp_dir = tempfile.mkdtemp()
    new_path = os.path.join(temp_dir, new_filename)
    with open(new_path, "wb") as f:
        f.write(file.getvalue())

    return new_path

# ---------------------------
# Main App Logic
# ---------------------------

uploaded_files = st.file_uploader("Pilih file PDF", type=["pdf"], accept_multiple_files=True)
doc_type = st.selectbox("Pilih jenis dokumen:", ["SKTT", "EVLN", "ITAS", "ITK", "Notifikasi"])

if st.button("🧾 Proses Dokumen") and uploaded_files:
    all_data = []
    renamed_paths = []

    for file in uploaded_files:
        text = read_pdf(file)

        if doc_type == "SKTT":
            data = extract_sktt(text)
        elif doc_type == "EVLN":
            data = extract_evln(text)
        elif doc_type == "ITAS":
            data = extract_itas(text)
        elif doc_type == "ITK":
            data = extract_itk(text)
        elif doc_type == "Notifikasi":
            data = extract_notifikasi(text)

        all_data.append(data)
        new_path = rename_uploaded_file(file, data)
        renamed_paths.append(new_path)

    df = pd.DataFrame(all_data)
    st.success("✅ Berhasil diproses!")
    st.dataframe(df)

    excel_path = os.path.join(tempfile.mkdtemp(), "hasil_ekstraksi.xlsx")
    df.to_excel(excel_path, index=False)

    zip_path = os.path.join(tempfile.mkdtemp(), "hasil_dokumen.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for path in renamed_paths:
            zipf.write(path, arcname=os.path.basename(path))
        zipf.write(excel_path, arcname="hasil_ekstraksi.xlsx")

    with open(zip_path, "rb") as f:
        btn = st.download_button(
            label="📦 Download Semua Hasil (ZIP)",
            data=f,
            file_name="hasil_ekstraksi.zip",
            mime="application/zip"
        )
