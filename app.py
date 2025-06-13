# app.py - Flask Backend (Complete Migration)
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import pdfplumber
import pandas as pd
import re
import tempfile
import os
import zipfile
from datetime import datetime
import hashlib
import io
import shutil
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Global storage for session results (in production, use Redis or database)
session_results = {}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============ UTILITY FUNCTIONS FROM STREAMLIT CODE ============

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username, password):
    users = {
        "sinta": hash_password("sinta123"),
        "ainun": hash_password("ainun123"),
        "fatih": hash_password("fatih123"),
        "demo": hash_password("demo123")
    }
    
    hashed_pw = hash_password(password)
    if username in users and users[username] == hashed_pw:
        return True
    return False

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

    data["Jenis Dokumen"] = "Notifikasi"
    return data

def sanitize_filename_part(text):
    return re.sub(r'[^\w\s-]', '', text).strip()

def generate_new_filename(extracted_data, use_name=True, use_passport=True):
    name_raw = (
        extracted_data.get("Name") or
        extracted_data.get("Nama TKA") or
        ""
    )

    passport_raw = (
        extracted_data.get("Passport Number") or
        extracted_data.get("Nomor Paspor") or
        extracted_data.get("Passport No") or
        extracted_data.get("KITAS/KITAP") or
        ""
    )

    name = sanitize_filename_part(name_raw) if use_name and name_raw else ""
    passport = sanitize_filename_part(passport_raw) if use_passport and passport_raw else ""

    parts = [p for p in [name, passport] if p]
    base_name = " ".join(parts) if parts else "RENAMED"
    
    return f"{base_name}.pdf"

def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Selamat Pagi"
    elif 12 <= hour < 17:
        return "Selamat Siang"
    else:
        return "Selamat Malam"

def process_pdfs(files, doc_type, use_name, use_passport):
    all_data = []
    renamed_files = {}
    
    temp_dir = tempfile.mkdtemp()
    
    for file in files:
        # Save uploaded file temporarily
        temp_file_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(temp_file_path)
        
        # Extract text from PDF
        with pdfplumber.open(temp_file_path) as pdf:
            texts = [page.extract_text() for page in pdf.pages if page.extract_text()]
            full_text = "\n".join(texts)
        
        # Extract data based on document type
        extraction_functions = {
            "SKTT": extract_sktt,
            "EVLN": extract_evln,
            "ITAS": extract_itas,
            "ITK": extract_itk,
            "Notifikasi": extract_notifikasi
        }
        
        extract_func = extraction_functions.get(doc_type)
        if extract_func:
            extracted_data = extract_func(full_text)
        else:
            extracted_data = {"Jenis Dokumen": doc_type}
        
        all_data.append(extracted_data)
        
        # Generate new filename
        new_filename = generate_new_filename(extracted_data, use_name, use_passport)
        
        # Copy file with new name
        new_file_path = os.path.join(temp_dir, new_filename)
        shutil.copy2(temp_file_path, new_file_path)
        
        renamed_files[file.filename] = {
            'new_name': new_filename, 
            'path': new_file_path
        }
    
    # Create DataFrame
    df = pd.DataFrame(all_data)
    
    # Save Excel file
    excel_path = os.path.join(temp_dir, "Hasil_Ekstraksi.xlsx")
    df.to_excel(excel_path, index=False)
    
    # Create ZIP file
    zip_path = os.path.join(temp_dir, "Renamed_Files.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_info in renamed_files.values():
            zipf.write(file_info['path'], arcname=file_info['new_name'])
    
    return {
        'dataframe': df,
        'excel_path': excel_path,
        'zip_path': zip_path,
        'renamed_files': renamed_files,
        'temp_dir': temp_dir
    }

# ============ FLASK ROUTES ============

@app.route('/')
def index():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login_page'))
    return render_template('index.html', 
                         username=session.get('username', ''),
                         greeting=get_greeting())

@app.route('/login')
def login_page():
    if 'logged_in' in session and session['logged_in']:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    if check_credentials(username, password):
        session['logged_in'] = True
        session['username'] = username
        session['session_id'] = str(uuid.uuid4())
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Username atau password salah!'})

@app.route('/logout')
def logout():
    session_id = session.get('session_id')
    if session_id and session_id in session_results:
        # Clean up temp files
        result_data = session_results[session_id]
        if 'temp_dir' in result_data:
            try:
                shutil.rmtree(result_data['temp_dir'])
            except:
                pass
        del session_results[session_id]
    
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        files = request.files.getlist('files')
        doc_type = request.form.get('doc_type', 'SKTT')
        use_name = request.form.get('use_name') == 'true'
        use_passport = request.form.get('use_passport') == 'true'
        
        if not files or all(file.filename == '' for file in files):
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Validate file types
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({'error': f'File {file.filename} is not a PDF'}), 400
        
        # Process files
        results = process_pdfs(files, doc_type, use_name, use_passport)
        
        # Store results in session
        session_id = session['session_id']
        session_results[session_id] = results
        
        return jsonify({
            'success': True,
            'data': results['dataframe'].to_dict('records'),
            'total_files': len(files),
            'doc_type': doc_type,
            'processed_at': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing files: {str(e)}'}), 500

@app.route('/download/excel')
def download_excel():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_id = session.get('session_id')
    if not session_id or session_id not in session_results:
        return jsonify({'error': 'No data available for download'}), 404
    
    try:
        excel_path = session_results[session_id]['excel_path']
        return send_file(
            excel_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Hasil_Ekstraksi_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        return jsonify({'error': f'Error downloading Excel file: {str(e)}'}), 500

@app.route('/download/zip')
def download_zip():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_id = session.get('session_id')
    if not session_id or session_id not in session_results:
        return jsonify({'error': 'No data available for download'}), 404
    
    try:
        zip_path = session_results[session_id]['zip_path']
        return send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'Renamed_Files_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
    except Exception as e:
        return jsonify({'error': f'Error downloading ZIP file: {str(e)}'}), 500

@app.route('/api/session-info')
def session_info():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_id = session.get('session_id')
    has_data = session_id in session_results if session_id else False
    
    return jsonify({
        'username': session.get('username', ''),
        'greeting': get_greeting(),
        'has_data': has_data,
        'session_id': session_id
    })

# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 16MB'}), 413

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# Cleanup function (call this periodically in production)
def cleanup_old_sessions():
    """Remove old session data and temp files"""
    # Implementation would check timestamps and remove old data
    pass

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)