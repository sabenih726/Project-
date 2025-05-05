import streamlit as st
import re, os, shutil, zipfile
import pandas as pd
import pdfplumber
import tempfile
from datetime import datetime

# === Fungsi Utility ===
def clean_text(text, is_name_or_pob=False):
    text = re.sub(r"Reference No|Payment Receipt No|Jenis Kelamin|Kewarganegaraan|Pekerjaan|Alamat", "", text)
    if is_name_or_pob:
        text = re.sub(r"\.", "", text)
    text = re.sub(r"[^A-Za-z0-9\s,./-]", "", text).strip()
    return " ".join(text.split())

def format_date(date_str):
    match = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", date_str)
    if match:
        day, month, year = match.groups()
        return f"{day}/{month}/{year}"
    return date_str

def split_birth_place_date(text):
    if text:
        parts = text.split(", ")
        if len(parts) == 2:
            return parts[0].strip(), format_date(parts[1])
    return text, None

def sanitize_filename_part(text):
    return re.sub(r'[^\w\s-]', '', text).strip()

def rename_uploaded_file(file, extracted_data, use_name=True):
    # Ambil nama baru dari hasil ekstraksi
    name = extracted_data.get("Nama", "").strip().replace(" ", "_")
    passport = extracted_data.get("No Dokumen", "").strip().replace(" ", "_")
    parts = [p for p in [name, passport] if p]
    base_name = " ".join(parts) if parts else "RENAMED"
    new_filename = f"{base_name}.pdf"

    # Simpan file ke temporary path dengan nama baru
    temp_dir = tempfile.mkdtemp()
    new_path = os.path.join(temp_dir, new_filename)
    with open(new_path, "wb") as f:
        f.write(file.getvalue())

    return new_path

def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"

# === Fungsi Ekstraksi per Dokumen ===
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

def extract_evln(text):
    data = {"Name": "", "Place of Birth": "", "Date of Birth": "", "Passport No": "", "Passport Expiry": "", "Jenis Dokumen": "EVLN"}
    for line in text.split("\n"):
        if re.search(r"(?i)\bName\b|\bNama\b", line):
            parts = line.split(":")
            if len(parts) > 1: data["Name"] = clean_text(parts[1], is_name_or_pob=True)
        elif re.search(r"(?i)\bPlace of Birth\b", line):
            parts = line.split(":")
            if len(parts) > 1: data["Place of Birth"] = clean_text(parts[1], is_name_or_pob=True)
        elif re.search(r"(?i)\bDate of Birth\b", line):
            match = re.search(r"(\d{2}[-/]\d{2}[-/]\d{4})", line)
            if match: data["Date of Birth"] = format_date(match.group(1))
        elif re.search(r"(?i)Passport No", line):
            match = re.search(r"\b([A-Z0-9]+)\b", line)
            if match: data["Passport No"] = match.group(1)
        elif re.search(r"(?i)Passport Expiry", line):
            match = re.search(r"(\d{2}[-/]\d{2}[-/]\d{4})", line)
            if match: data["Passport Expiry"] = format_date(match.group(1))
    return data

def extract_itas(text): return extract_itk(text) | {"Jenis Dokumen": "ITAS"}
def extract_itk(text):
    data = {}
    name_match = re.search(r"([A-Z\s]+)\nPERMIT NUMBER", text)
    data["Name"] = name_match.group(1).strip() if name_match else None
    permit_match = re.search(r"PERMIT NUMBER\s*:\s*([A-Z0-9-]+)", text)
    data["Permit Number"] = permit_match.group(1) if permit_match else None
    expiry_match = re.search(r"STAY PERMIT EXPIRY\s*:\s*([\d/]+)", text)
    data["Stay Permit Expiry"] = expiry_match.group(1) if expiry_match else None
    place_date_birth_match = re.search(r"Place / Date of Birth\s*.*:\s*([A-Za-z\s]+)\s*/\s*([\d-]+)", text)
    data["Place & Date of Birth"] = (
        f"{place_date_birth_match.group(1).strip()}, {format_date(place_date_birth_match.group(2))}"
        if place_date_birth_match else None
    )
    data["Passport Number"] = re.search(r"Passport Number\s*: ([A-Z0-9]+)", text).group(1) if re.search(r"Passport Number\s*: ([A-Z0-9]+)", text) else None
    data["Passport Expiry"] = re.search(r"Passport Expiry\s*: ([\d-]+)", text).group(1) if re.search(r"Passport Expiry\s*: ([\d-]+)", text) else None
    data["Nationality"] = re.search(r"Nationality\s*: ([A-Z]+)", text).group(1) if re.search(r"Nationality\s*: ([A-Z]+)", text) else None
    data["Gender"] = re.search(r"Gender\s*: ([A-Z]+)", text).group(1) if re.search(r"Gender\s*: ([A-Z]+)", text) else None
    data["Address"] = re.search(r"Address\s*:\s*(.+)", text).group(1).strip() if re.search(r"Address\s*:\s*(.+)", text) else None
    data["Occupation"] = re.search(r"Occupation\s*:\s*(.+)", text).group(1).strip() if re.search(r"Occupation\s*:\s*(.+)", text) else None
    data["Guarantor"] = re.search(r"Guarantor\s*:\s*(.+)", text).group(1).strip() if re.search(r"Guarantor\s*:\s*(.+)", text) else None
    data["Jenis Dokumen"] = "ITK"
    return data

def extract_notifikasi(text):
    def find(p): m = re.search(p, text, re.IGNORECASE); return m.group(1).strip() if m else ""
    data = {
        "Nomor Keputusan": re.search(r"NOMOR\s+([A-Z0-9./-]+)", text, re.IGNORECASE).group(1).strip() if re.search(r"NOMOR\s+([A-Z0-9./-]+)", text, re.IGNORECASE) else "",
        "Nama TKA": find(r"Nama TKA\s*:\s*(.*)"),
        "Tempat/Tanggal Lahir": find(r"Tempat/Tanggal Lahir\s*:\s*(.*)"),
        "Kewarganegaraan": find(r"Kewarganegaraan\s*:\s*(.*)"),
        "Alamat Tempat Tinggal": find(r"Alamat Tempat Tinggal\s*:\s*(.*)"),
        "Nomor Paspor": find(r"Nomor Paspor\s*:\s*(.*)"),
        "Jabatan": find(r"Jabatan\s*:\s*(.*)"),
        "Lokasi Kerja": find(r"Lokasi Kerja\s*:\s*(.*)"),
        "Berlaku": ""
    }
    valid_match = re.search(r"Berlaku\s*:?\s*(\d{2}[-/]\d{2}[-/]\d{4})\s*(?:s\.?d\.?|sampai dengan)?\s*(\d{2}[-/]\d{2}[-/]\d{4})", text, re.IGNORECASE)
    if valid_match:
        data["Berlaku"] = f"{format_date(valid_match.group(1))} - {format_date(valid_match.group(2))}"
    return data

# === Streamlit UI ===
st.set_page_config(page_title="PDF Document Extractor", layout="wide")
st.title(f"{get_greeting()}, welcome to the Document Extractor App")

doc_type = st.selectbox("Select Document Type", ["SKTT", "EVLN", "ITAS", "ITK", "Notifikasi"])
uploaded_files = st.file_uploader("Upload PDF files", accept_multiple_files=True, type=["pdf"])
rename_name = st.checkbox("Rename using Name", value=True)
rename_passport = st.checkbox("Rename using Passport", value=True)

if st.button("Start Extraction") and uploaded_files:
    all_data = []
    renamed_paths = []

    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
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
        new_path = rename_uploaded_file(file.name, data, rename_name, rename_passport)
        renamed_paths.append(new_path)

    df = pd.DataFrame(all_data)
    st.success("Extraction completed!")
    st.dataframe(df)

    with tempfile.TemporaryDirectory() as tmpdir:
        excel_path = os.path.join(tmpdir, "Hasil_Ekstraksi.xlsx")
        df.to_excel(excel_path, index=False)
        with open(excel_path, "rb") as f:
            st.download_button("Download Excel", f, file_name="Hasil_Ekstraksi.xlsx")

        zip_path = os.path.join(tmpdir, "Renamed_Files.zip")
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for path in renamed_paths:
                zipf.write(path, arcname=os.path.basename(path))
        with open(zip_path, "rb") as fz:
            st.download_button("Download Renamed Files (ZIP)", fz, file_name="Renamed_Files.zip")
