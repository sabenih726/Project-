import streamlit as st
import pandas as pd
import zipfile
import io
import base64
import re
from datetime import datetime
from PyPDF2 import PdfReader

# ====================
# Ekstraksi PDF
# ====================
def extract_text_from_pdf_bytes(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join([page.extract_text() or "" for page in reader.pages])
    return text

# ====================
# Fungsi Rename Aman
# ====================
def rename_uploaded_file(nama, nomor, original_filename):
    safe_nama = re.sub(r'[^a-zA-Z0-9]', '_', nama.upper().strip())
    safe_nomor = re.sub(r'[^a-zA-Z0-9]', '_', nomor.upper().strip())
    ext = original_filename.split('.')[-1] if '.' in original_filename else 'pdf'
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe_nama}_{safe_nomor}_{timestamp}.{ext}"

# ====================
# Ekspor Excel + ZIP
# ====================
def export_to_excel_and_zip(results):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipf:
        excel_data = []
        for result in results:
            excel_data.append({
                "Nama File Asli": result["original_filename"],
                "Nama File Baru": result["new_filename"],
                **result["extracted_data"]
            })
            zipf.writestr(result["new_filename"], result["pdf_bytes"])

        df = pd.DataFrame(excel_data)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        zipf.writestr("hasil_ekstraksi.xlsx", excel_buffer.getvalue())
    output.seek(0)
    return output

# ====================
# Fungsi Ekstraksi Tipe Dokumen
# (Contoh sederhana – sesuaikan sesuai kebutuhan)
# ====================
def extract_sktt(text):
    nama = re.search(r"Nama\s*:\s*(.+)", text)
    nomor = re.search(r"Nomor SKTT\s*:\s*(\S+)", text)
    return {
        "Nama": nama.group(1).strip() if nama else "Tidak ditemukan",
        "No Dokumen": nomor.group(1).strip() if nomor else "Tidak ditemukan"
    }

def extract_evln(text):
    nama = re.search(r"Nama\s*:\s*(.+)", text)
    nomor = re.search(r"Nomor EVLN\s*:\s*(\S+)", text)
    return {
        "Nama": nama.group(1).strip() if nama else "Tidak ditemukan",
        "No Dokumen": nomor.group(1).strip() if nomor else "Tidak ditemukan"
    }

# Tambah fungsi lain: ITAS, ITK, Notifikasi sesuai pola

# ====================
# Fungsi Utama Ekstraksi & Ekspor
# ====================
def extract_and_export(uploaded_files, doc_type, extractor_functions):
    if not uploaded_files:
        st.warning("Silakan unggah satu atau beberapa file PDF.")
        return

    if doc_type not in extractor_functions:
        st.error("Tipe dokumen tidak dikenali.")
        return

    extractor_function = extractor_functions[doc_type]
    extracted_results = []

    for uploaded_file in uploaded_files:
        try:
            pdf_bytes = uploaded_file.read()
            pdf_text = extract_text_from_pdf_bytes(pdf_bytes)
            extracted_data = extractor_function(pdf_text)
            nama = extracted_data.get("Nama", "TIDAK_DIKETAHUI")
            nomor = extracted_data.get("No Dokumen", "TIDAK_DIKETAHUI")
            new_filename = rename_uploaded_file(nama, nomor, uploaded_file.name)
            extracted_results.append({
                "original_filename": uploaded_file.name,
                "new_filename": new_filename,
                "extracted_data": extracted_data,
                "pdf_bytes": pdf_bytes
            })
        except Exception as e:
            st.error(f"Gagal memproses file {uploaded_file.name}: {e}")

    if not extracted_results:
        st.warning("Tidak ada file yang berhasil diproses.")
        return

    zip_buffer = export_to_excel_and_zip(extracted_results)
    st.success("Ekstraksi berhasil. Unduh hasil di bawah ini:")
    st.download_button(
        label="📦 Unduh ZIP Hasil",
        data=zip_buffer,
        file_name="hasil_ekstraksi.zip",
        mime="application/zip"
    )

# ====================
# UI Streamlit
# ====================
def main():
    st.set_page_config(page_title="Ekstraksi Dokumen PDF", layout="centered")
    st.title("📄 Ekstraksi Data Dokumen Imigrasi")

    uploaded_files = st.file_uploader("Unggah PDF", type=["pdf"], accept_multiple_files=True)
    doc_type = st.selectbox("Pilih Jenis Dokumen", ["SKTT", "EVLN"])  # Tambahkan ITAS, ITK, dll sesuai kebutuhan

    extractor_functions = {
        "SKTT": extract_sktt,
        "EVLN": extract_evln,
        # Tambahkan: "ITAS": extract_itas, dll
    }

    if st.button("🚀 Mulai Ekstraksi"):
        extract_and_export(uploaded_files, doc_type, extractor_functions)

if __name__ == "__main__":
    main()
