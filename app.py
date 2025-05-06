import streamlit as st
import fitz  # PyMuPDF
import re

# Fungsi untuk membaca teks dari PDF
def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# Fungsi deteksi jenis dokumen
def detect_document_type(text):
    if "Nomor B.3" in text and "Nama TKA" in text:
        return "Notifikasi"
    elif "PERMIT NUMBER" in text and "STAY PERMIT EXPIRY" in text:
        return "ITAS"
    elif "NIK" in text and "Nama" in text and "KITAP" in text:
        return "SKTT"
    elif "Passport No" in text and "Place of Birth" in text:
        return "EVLN"
    else:
        return "Tidak dikenali"

# Fungsi ekstraksi berdasarkan tipe dokumen
def extract_fields(text, doc_type):
    data = {}
    if doc_type == "EVLN":
        data["Name"] = re.search(r"Name\s*[:\-]?\s*(.*)", text)
        data["Place of Birth"] = re.search(r"Place of Birth\s*[:\-]?\s*(.*)", text)
        data["Date of Birth"] = re.search(r"Date of Birth\s*[:\-]?\s*(.*)", text)
        data["Passport No"] = re.search(r"Passport No\s*[:\-]?\s*(.*)", text)
        data["Passport Expiry"] = re.search(r"Passport Expiry\s*[:\-]?\s*(.*)", text)
        data["Date"] = re.search(r"Date\s*[:\-]?\s*(.*)", text)
    elif doc_type == "SKTT":
        data["NIK"] = re.search(r"NIK.*?:\s*(.*)", text)
        data["Nama"] = re.search(r"Nama.*?:\s*(.*)", text)
        data["Tempat/Tgl Lahir"] = re.search(r"Tempat/Tgl Lahir.*?:\s*(.*)", text)
        data["Kewarganegaraan"] = re.search(r"Kewarganegaraan.*?:\s*(.*)", text)
        data["Alamat"] = re.search(r"Alamat.*?:\s*(.*)", text)
        data["Nomor KITAP/KITAS"] = re.search(r"Nomor KITAP.*?:\s*(.*)", text)
        data["Berlaku Hingga"] = re.search(r"Berlaku Hingga.*?:\s*(.*)", text)
    elif doc_type == "ITAS":
        data["Name"] = re.search(r"Name\s*[:\-]?\s*(.*)", text)
        data["PERMIT NUMBER"] = re.search(r"PERMIT NUMBER\s*[:\-]?\s*(.*)", text)
        data["STAY PERMIT EXPIRY"] = re.search(r"STAY PERMIT EXPIRY\s*[:\-]?\s*(.*)", text)
        data["Place / Date of Birth"] = re.search(r"Place / Date of Birth\s*[:\-]?\s*(.*)", text)
        data["Passport Number"] = re.search(r"Passport Number\s*[:\-]?\s*(.*)", text)
        data["Passport Expiry"] = re.search(r"Passport Expiry\s*[:\-]?\s*(.*)", text)
        data["Nationality"] = re.search(r"Nationality\s*[:\-]?\s*(.*)", text)
        data["Address"] = re.search(r"Address\s*[:\-]?\s*(.*)", text)
        data["Occupation"] = re.search(r"Occupation\s*[:\-]?\s*(.*)", text)
        data["Guarantor"] = re.search(r"Guarantor\s*[:\-]?\s*(.*)", text)
    elif doc_type == "Notifikasi":
        data["Nomor"] = re.search(r"(NOMOR.*?)\n", text)
        data["Nama TKA"] = re.search(r"Nama TKA\s*[:\-]?\s*(.*)", text)
        data["Tempat/Tanggal Lahir"] = re.search(r"Tempat/Tanggal Lahir\s*[:\-]?\s*(.*)", text)
        data["Kewarganegaraan"] = re.search(r"Kewarganegaraan\s*[:\-]?\s*(.*)", text)
        data["Alamat Tempat Tinggal"] = re.search(r"Alamat Tempat Tinggal\s*[:\-]?\s*(.*)", text)
        data["Nomor Paspor"] = re.search(r"Nomor Paspor\s*[:\-]?\s*(.*)", text)
        data["Jabatan"] = re.search(r"Jabatan\s*[:\-]?\s*(.*)", text)
        data["Lokasi kerja"] = re.search(r"Lokasi kerja\s*[:\-]?\s*(.*)", text)
        data["Berlaku"] = re.search(r"Berlaku\s*[:\-]?\s*(.*)", text)

    # Bersihkan hasil regex
    for key in data:
        if data[key]:
            data[key] = data[key].group(1).strip()
        else:
            data[key] = "-"
    return data

# UI Streamlit
st.title("Ekstraksi Data dari Dokumen Imigrasi")

uploaded_file = st.file_uploader("Unggah file PDF", type="pdf")

if uploaded_file is not None:
    with st.spinner("Membaca dan mengekstrak dokumen..."):
        # Ekstrak teks dari PDF
        text = extract_text_from_pdf(uploaded_file)

        # Tampilkan isi teks mentah untuk debugging atau review
        st.text_area("Preview Text", text, height=400)

        # Deteksi jenis dokumen
        doc_type = detect_document_type(text)
        st.subheader(f"Jenis Dokumen: {doc_type}")

        # Proses ekstraksi berdasarkan jenis dokumen
        if doc_type != "Tidak dikenali":
            if doc_type == "SKTT":
                data, renamed_file = extract_sktt(text, uploaded_file.name)
            elif doc_type == "EVLN":
                data, renamed_file = extract_evln(text, uploaded_file.name)
            elif doc_type == "ITAS":
                data, renamed_file = extract_itas(text, uploaded_file.name)
            elif doc_type == "ITK":
                data, renamed_file = extract_itk(text, uploaded_file.name)
            elif doc_type == "Notifikasi":
                data, renamed_file = extract_notifikasi(text, uploaded_file.name)
            else:
                st.warning("Jenis dokumen tidak dikenali.")
                data, renamed_file = None, None

            if data:
                st.subheader("Hasil Ekstraksi:")
                for key, value in data.items():
                    st.write(f"**{key}:** {value}")

