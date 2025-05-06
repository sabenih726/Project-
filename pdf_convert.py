import re
import fitz  # PyMuPDF
import pandas as pd
from io import BytesIO
from zipfile import ZipFile

# Fungsi umum
def extract_text_from_pdf(file):
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        text = ""
        for page in doc:
            text += page.get_text()
    return text

def detect_document_type(text):
    if "SURAT KETERANGAN TEMPAT TINGGAL" in text:
        return "SKTT"
    elif "E-Visa" in text:
        return "EVLN"
    elif "ITAS" in text:
        return "ITAS"
    elif "PEMBERITAHUAN PERUBAHAN DATA" in text:
        return "Notifikasi"
    else:
        return "Tidak Diketahui"

# ========================== FUNGSI UTILITAS ==========================

def format_date(date_str):
    match = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", date_str)
    if match:
        day, month, year = match.groups()
        return f"{day}/{month}/{year}"
    return date_str

# ========================== FUNGSI EKSTRAKSI EVLN ==========================

def clean_evl_text(text):
    text = re.sub(r"Reference No|Payment Receipt No", "", text)
    text = re.sub(r"[^A-Za-z\s]", "", text).strip()
    return " ".join(text.split()[:2])

def extract_evln(text):
    data = {
        "Name": "",
        "Place of Birth": "",
        "Date of Birth": "",
        "Passport No": "",
        "Passport Expiry": ""
    }
    for line in text.split("\n"):
        if re.search(r"\bName\b|\bNama\b", line):
            parts = line.split(":")
            if len(parts) > 1:
                data["Name"] = clean_evl_text(parts[1])
        elif re.search(r"\bPlace of Birth\b|\bTempat Lahir\b", line):
            parts = line.split(":")
            if len(parts) > 1:
                data["Place of Birth"] = clean_evl_text(parts[1])
        elif re.search(r"\bDate of Birth\b|\bTanggal Lahir\b", line):
            match = re.search(r"(\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})", line)
            if match:
                data["Date of Birth"] = format_date(match.group(1))
        elif re.search(r"\bPassport No\b", line):
            match = re.search(r"\b([A-Z0-9]+)\b", line)
            if match:
                data["Passport No"] = match.group(1)
        elif re.search(r"\bPassport Expiry\b", line):
            match = re.search(r"(\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})", line)
            if match:
                data["Passport Expiry"] = format_date(match.group(1))
    return data

# ========================== FUNGSI EKSTRAKSI SKTT ==========================

def clean_sktt_text(text):
    text = re.sub(r'\n+', ' ', text.strip())
    text = re.sub(r'\b(Jenis Kelamin|Kewarganegaraan|Pekerjaan|Alamat)\b', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def split_birth_place_date(text):
    parts = text.split(", ")
    return (parts[0], format_date(parts[1])) if len(parts) == 2 else (text, None)

def extract_sktt(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        all_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    data = {}
    nik = re.search(r'NIK/Number of Population Identity\s*:\s*(\d+)', all_text)
    name = re.search(r'Nama/Name\s*:\s*([\w\s]+)', all_text)
    gender = re.search(r'Jenis Kelamin/Sex\s*:\s*(MALE|FEMALE)', all_text)
    birth = re.search(r'Tempat/Tgl Lahir\s*:\s*([\w\s,0-9-]+)', all_text)
    nationality = re.search(r'Kewarganegaraan/Nationality\s*:\s*([\w\s]+)', all_text)
    job = re.search(r'Pekerjaan/Occupation\s*:\s*([\w\s]+)', all_text)
    address = re.search(r'Alamat/Address\s*:\s*([\w\s,./-]+)', all_text)
    kitas = re.search(r'Nomor KITAP/KITAS Number\s*:\s*([\w-]+)', all_text)
    exp = re.search(r'Berlaku Hingga s.d/Expired date\s*:\s*([\d-]+)', all_text)
    birth_place, birth_date = split_birth_place_date(birth.group(1)) if birth else (None, None)

    data["NIK"] = clean_sktt_text(nik.group(1)) if nik else None
    data["Nama"] = clean_sktt_text(name.group(1)) if name else None
    data["Jenis Kelamin"] = clean_sktt_text(gender.group(1)) if gender else None
    data["Tempat Lahir"] = clean_sktt_text(birth_place)
    data["Tanggal Lahir"] = birth_date
    data["Kewarganegaraan"] = clean_sktt_text(nationality.group(1)) if nationality else None
    data["Pekerjaan"] = clean_sktt_text(job.group(1)) if job else None
    data["Alamat"] = clean_sktt_text(address.group(1)) if address else None
    data["Nomor KITAP/KITAS"] = clean_sktt_text(kitas.group(1)) if kitas else None
    data["Berlaku Hingga"] = clean_sktt_text(exp.group(1)) if exp else None

    return data

# ========================== FUNGSI EKSTRAKSI ITAS ==========================

def format_date_itas(date_str):
    """Ubah format tanggal dari DD-MM-YYYY ke DD/MM/YYYY"""
    match = re.match(r'(\d{2})-(\d{2})-(\d{4})', date_str)
    if match:
        day, month, year = match.groups()
        return f"{day}/{month}/{year}"
    return date_str

def extract_itas(text):
    data = {}

    data["Name"] = re.search(r"([A-Z\s]+)\nPERMIT NUMBER", text)
    data["Name"] = data["Name"].group(1).strip() if data["Name"] else None

    data["Permit Number"] = re.search(r"PERMIT NUMBER\s*:\s*([A-Z0-9-]+)", text)
    data["Permit Number"] = data["Permit Number"].group(1) if data["Permit Number"] else None

    data["Stay Permit Expiry"] = re.search(r"STAY PERMIT EXPIRY\s*:\s*([\d/]+)", text)
    data["Stay Permit Expiry"] = data["Stay Permit Expiry"].group(1) if data["Stay Permit Expiry"] else None

    birth = re.search(r"Place / Date of Birth\s*.*:\s*([A-Za-z\s]+)\s*/\s*([\d-]+)", text)
    if birth:
        place = birth.group(1).strip()
        date = format_date_itas(birth.group(2).strip())
        data["Place & Date of Birth"] = f"{place}, {date}"
    else:
        data["Place & Date of Birth"] = None

    data["Passport Number"] = re.search(r"Passport Number\s*: ([A-Z0-9]+)", text)
    data["Passport Number"] = data["Passport Number"].group(1) if data["Passport Number"] else None

    data["Passport Expiry"] = re.search(r"Passport Expiry\s*: ([\d-]+)", text)
    data["Passport Expiry"] = data["Passport Expiry"].group(1) if data["Passport Expiry"] else None

    data["Nationality"] = re.search(r"Nationality\s*: ([A-Z]+)", text)
    data["Nationality"] = data["Nationality"].group(1) if data["Nationality"] else None

    data["Gender"] = re.search(r"Gender\s*: ([A-Z]+)", text)
    data["Gender"] = data["Gender"].group(1) if data["Gender"] else None

    data["Address"] = re.search(r"Address\s*:\s*(.+)", text)
    data["Address"] = data["Address"].group(1).strip() if data["Address"] else None

    data["Occupation"] = re.search(r"Occupation\s*:\s*(.+)", text)
    data["Occupation"] = data["Occupation"].group(1).strip() if data["Occupation"] else None

    data["Guarantor"] = re.search(r"Guarantor\s*:\s*(.+)", text)
    data["Guarantor"] = data["Guarantor"].group(1).strip() if data["Guarantor"] else None

    return data

# ========================== FUNGSI EKSTRAKSI SKTT ==========================

def format_date_notif(date_str):
    month_map = {
        "Januari": "01", "Februari": "02", "Maret": "03", "April": "04",
        "Mei": "05", "Juni": "06", "Juli": "07", "Agustus": "08",
        "September": "09", "Oktober": "10", "November": "11", "Desember": "12"
    }
    match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", date_str)
    if match:
        day, month, year = match.groups()
        month_num = month_map.get(month, month)
        return f"{day}/{month_num}/{year}"
    return date_str

def extract_notifikasi(text):
    data = {}
    data["Nama TKA"] = re.search(r"Nama TKA\s*:\s*(.+)", text)
    data["Nama TKA"] = data["Nama TKA"].group(1).strip() if data["Nama TKA"] else None

    birth = re.search(r"Tempat/Tanggal Lahir\s*:\s*([A-Za-z\s]+),\s*([\d\s\w]+)", text)
    if birth:
        place = birth.group(1).strip()
        date_str = format_date_notif(birth.group(2).strip())
        data["Tempat/Tanggal Lahir"] = f"{place}, {date_str}"
    else:
        data["Tempat/Tanggal Lahir"] = None

    data["Kewarganegaraan"] = re.search(r"Kewarganegaraan\s*:\s*(.+)", text)
    data["Kewarganegaraan"] = data["Kewarganegaraan"].group(1).strip() if data["Kewarganegaraan"] else None

    data["Alamat Tempat Tinggal"] = re.search(r"Alamat Tempat Tinggal\s*:\s*(.+)", text)
    data["Alamat Tempat Tinggal"] = data["Alamat Tempat Tinggal"].group(1).strip() if data["Alamat Tempat Tinggal"] else None

    data["Nomor Paspor"] = re.search(r"Nomor Paspor\s*:\s*(.+)", text)
    data["Nomor Paspor"] = data["Nomor Paspor"].group(1).strip() if data["Nomor Paspor"] else None

    data["Jabatan"] = re.search(r"Jabatan\s*:\s*(.+)", text)
    data["Jabatan"] = data["Jabatan"].group(1).strip() if data["Jabatan"] else None

    data["Lokasi Kerja"] = re.search(r"Lokasi kerja\s*:\s*(.+)", text)
    data["Lokasi Kerja"] = data["Lokasi Kerja"].group(1).strip() if data["Lokasi Kerja"] else None

    berlaku = re.search(r"Berlaku\s*:\s*(\d{2}-\d{2}-\d{4})\s*s\.d\s*(\d{2}-\d{2}-\d{4})", text)
    if berlaku:
        start = berlaku.group(1).replace("-", "/")
        end = berlaku.group(2).replace("-", "/")
        data["Berlaku"] = f"{start} - {end}"
    else:
        data["Berlaku"] = None

    return data

def rename_file_and_export_excel(data_list):
    df = pd.DataFrame(data_list)
    output = BytesIO()
    with ZipFile(output, 'w') as zipf:
        # Simpan Excel
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        zipf.writestr("data_ekstraksi.xlsx", excel_buffer.getvalue())

        # Rename file (jika ada kolom penentu nama baru)
        for item in data_list:
            old_name = item.get("filename", "file.pdf")
            new_name = f"{item.get('Nama') or item.get('No EVLN') or item.get('No ITAS') or old_name}".replace(" ", "_")
            zipf.writestr(f"renamed/{new_name}.txt", str(item))

    output.seek(0)
    return output
