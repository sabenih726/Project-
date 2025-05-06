import streamlit as st
from pdf_convert import (
    extract_text_from_pdf,
    detect_document_type,
    extract_sktt,
    extract_evln,
    extract_itas,
    extract_itk,
    extract_notifikasi,
    rename_file_and_export_excel
)

st.set_page_config(page_title="Ekstraksi Dokumen Imigrasi", layout="wide")

st.title("Ekstraksi Data dari Dokumen Imigrasi")

uploaded_files = st.file_uploader("Unggah file PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for uploaded_file in uploaded_files:
        with st.spinner(f"Mengekstrak: {uploaded_file.name}"):
            text = extract_text_from_pdf(uploaded_file)
            doc_type = detect_document_type(text)
            st.write(f"**Jenis Dokumen:** {doc_type}")
            st.text_area("Isi Dokumen", text, height=250)

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
            else:
                data = {"Error": "Jenis dokumen tidak dikenali"}

            st.write("### Hasil Ekstraksi")
            st.json(data)
            data["filename"] = uploaded_file.name
            all_data.append(data)

    if all_data:
        zip_buffer = rename_file_and_export_excel(all_data)
        st.download_button("Unduh Hasil (ZIP)", zip_buffer, file_name="hasil_ekstraksi.zip")
