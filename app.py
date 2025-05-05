import streamlit as st
import pandas as pd
import tempfile
import zipfile
import base64
import os
import io
from datetime import datetime

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

    lines = text.split("\n")

    # [Tambahan] Cari nama berdasarkan sapaan seperti Dear Mr./Ms.
    for i, line in enumerate(lines):
        if re.search(r"Dear\s+(Mr\.|Ms\.|Sir|Madam)?", line, re.IGNORECASE):
            if i + 1 < len(lines):
                name_candidate = lines[i + 1].strip()
                if 3 < len(name_candidate) < 50:
                    # Gunakan clean_text jika tersedia
                    if 'clean_text' in globals():
                        data["Name"] = clean_text(name_candidate, is_name_or_pob=True)
                    else:
                        data["Name"] = re.sub(r'[^A-Z ]', '', name_candidate.upper())
            break  # hentikan loop setelah dapat nama

    # Lanjutkan parsing baris seperti biasa
    for line in lines:
        if not data["Name"] and re.search(r"(?i)\bName\b|\bNama\b", line):
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

# Rename file setelah upload
def rename_file(file_path, new_name):
    folder = tempfile.mkdtemp()
    new_path = os.path.join(folder, new_name)
    shutil.copy(file_path, new_path)
    return new_path

def sanitize_filename_part(text):
    # Biarkan spasi dan tanda hubung, hapus karakter ilegal lainnya
    return re.sub(r'[^\w\s-]', '', text).strip()

def rename_uploaded_file(original_filename, extracted_data, use_name=True, use_passport=True):
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
    new_filename = f"{base_name}.pdf"

    return rename_file(original_filename, new_filename)

# Salam waktu otomatis
def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"

# Proses utama ekstraksi + export
def extract_and_export(files, selected_doc_type, rename_name_checkbox, rename_passport_checkbox):
    all_data = []
    renamed_files = []

    for file in files:
        ext = file.name.split('.')[-1].lower()
        if ext == 'pdf':
            with pdfplumber.open(file) as pdf:
                texts = [page.extract_text() for page in pdf.pages if page.extract_text()]
                full_text = "\n".join(texts)

            # Panggil fungsi ekstraksi sesuai tipe dokumen
            if selected_doc_type == "SKTT":
                extracted_data = extract_sktt(full_text)
            elif selected_doc_type == "EVLN":
                extracted_data = extract_evln(full_text)
            elif selected_doc_type == "ITAS":
                extracted_data = extract_itas(full_text)
            elif selected_doc_type == "ITK":
                extracted_data = extract_itk(full_text)
            elif selected_doc_type == "Notifikasi":
                extracted_data = extract_notifikasi(full_text)
            else:
                extracted_data = {}

            all_data.append(extracted_data)

            # Rename file berdasarkan data
            new_file_path = rename_uploaded_file(
                file.name, extracted_data,
                rename_name_checkbox, rename_passport_checkbox
            )
            renamed_files.append(new_file_path)

    # Simpan ke Excel
    df = pd.DataFrame(all_data)
    temp_dir = tempfile.mkdtemp()
    excel_path = os.path.join(temp_dir, "Hasil_Ekstraksi.xlsx")
    df.to_excel(excel_path, index=False)

    return df, excel_path, renamed_files

# Proses utama ekstraksi + export
def extract_and_export(files, selected_doc_type, rename_name_checkbox, rename_passport_checkbox):
    all_data = []
    renamed_files = []

    # Buat folder sementara hanya sekali di awal
    temp_dir = tempfile.mkdtemp()

    for file in files:
        ext = file.name.split('.')[-1].lower()
        if ext == 'pdf':
            with pdfplumber.open(file) as pdf:
                texts = [page.extract_text() for page in pdf.pages if page.extract_text()]
                full_text = "\n".join(texts)

            # Ekstraksi sesuai jenis dokumen
            if selected_doc_type == "SKTT":
                extracted_data = extract_sktt(full_text)
            elif selected_doc_type == "EVLN":
                extracted_data = extract_evln(full_text)
            elif selected_doc_type == "ITAS":
                extracted_data = extract_itas(full_text)
            elif selected_doc_type == "ITK":
                extracted_data = extract_itk(full_text)
            elif selected_doc_type == "Notifikasi":
                extracted_data = extract_notifikasi(full_text)
            else:
                extracted_data = {}

            all_data.append(extracted_data)

            # Rename file dan simpan ke folder sementara
            new_file_path = rename_uploaded_file(
                file.name, extracted_data,
                rename_name_checkbox, rename_passport_checkbox
            )
            renamed_files.append(new_file_path)

    # Simpan ke Excel
    excel_path = os.path.join(temp_dir, "Hasil_Ekstraksi.xlsx")
    pd.DataFrame(all_data).to_excel(excel_path, index=False)

    # Buat ZIP dari semua file rename
    zip_path = os.path.join(temp_dir, "Renamed_Files.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in renamed_files:
            arcname = os.path.basename(file_path)
            zipf.write(file_path, arcname=arcname)

    return pd.DataFrame(all_data), excel_path, renamed_files, zip_path

# ---------------------------
# Main App Logic
# ---------------------------

# Setup UI
st.set_page_config(page_title="PDF Extractor Streamlit", layout="wide")
st.title("📄 Ekstraksi Dokumen PDF")

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    doc_type = st.selectbox("Jenis Dokumen", ["SKTT", "EVLN", "ITAS", "ITK", "Notifikasi"])
    rename_by = st.multiselect("Rename file berdasarkan:", ["NAMA", "NOMOR_PASPOR"])

uploaded_files = st.file_uploader("📤 Upload file PDF", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    results = []
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zipf:
        for file in uploaded_files:
            text = extract_text_from_pdf(file)
            if doc_type == "SKTT":
                data = extract_sktt(text)
            elif doc_type == "EVLN":
                data = extract_evl(text)
            elif doc_type == "ITAS":
                data = extract_itas(text)
            elif doc_type == "ITK":
                data = extract_itk(text)
            elif doc_type == "Notifikasi":
                data = extract_notifikasi(text)
            else:
                data = {}

            results.append(data)

            # Rename file
            name_parts = [data.get(part, "") for part in rename_by]
            filename = "_".join(name_parts).strip() or "hasil"
            filename = filename.replace(" ", "_")
            filename = f"{filename}_{datetime.now().strftime('%Y%m%d')}.pdf"

            file.seek(0)
            zipf.writestr(filename, file.read())

        # Simpan hasil ke Excel
        df = pd.DataFrame(results)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        zipf.writestr("hasil_ekstraksi.xlsx", excel_buffer.getvalue())

    st.success("✅ Ekstraksi selesai!")
    st.dataframe(df)

    st.download_button(
        label="⬇️ Download Hasil ZIP",
        data=zip_buffer.getvalue(),
        file_name="hasil_ekstraksi.zip",
        mime="application/zip"
    )
else:
    st.info("Silakan upload file PDF untuk diproses.")
