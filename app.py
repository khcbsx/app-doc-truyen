import streamlit as st
import docx
import re
import os
import subprocess
import urllib.request

st.set_page_config(page_title="Word to Audio TTS", layout="wide")
st.title("📚 Chuyển Đổi Truyện Chữ Sang Audio (Đa Nền Tảng)")

os.makedirs("models", exist_ok=True)
os.makedirs("output", exist_ok=True)

# ---------------------------------------------------------
# DANH SÁCH GIỌNG ĐỌC TỔNG HỢP (ONLINE & OFFLINE)
# ---------------------------------------------------------
VOICES = {
    "🌟 Microsoft Hoài My (Online - Nữ Truyền Cảm)": {
        "engine": "edge", "id": "vi-VN-HoaiMyNeural"
    },
    "🌟 Microsoft Nam Minh (Online - Nam Trầm Ấm)": {
        "engine": "edge", "id": "vi-VN-NamMinhNeural"
    },
    "⚙️ Piper Vais1000 (Offline - Nữ Cơ Bản)": {
        "engine": "piper", 
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium"
    },
    "⚙️ Piper Vivos (Offline - Nam Cơ Bản)": {
        "engine": "piper", 
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vivos/x_low/vi_VN-vivos-x_low"
    }
}

# Tự động tải model offline nếu chưa có
with st.spinner("⏳ Đang kiểm tra hệ thống giọng đọc..."):
    for name, info in VOICES.items():
        if info["engine"] == "piper":
            safe_name = name.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "")
            onnx_path = os.path.join("models", f"{safe_name}.onnx")
            json_path = os.path.join("models", f"{safe_name}.onnx.json")
            info["model_path"] = onnx_path # Lưu đường dẫn để tí gọi
            
            if not os.path.exists(onnx_path):
                try:
                    urllib.request.urlretrieve(info["base_url"] + ".onnx", onnx_path)
                    urllib.request.urlretrieve(info["base_url"] + ".onnx.json", json_path)
                except Exception:
                    pass

if "chapters" not in st.session_state: st.session_state.chapters = {}
if "chapter_list" not in st.session_state: st.session_state.chapter_list = []

uploaded_file = st.file_uploader("Tải lên file Word (.docx)", type=["docx"])

if uploaded_file:
    if not st.session_state.chapters:
        with st.spinner("Đang phân tích file (Truyện dài có thể mất vài chục giây)..."):
            doc = docx.Document(uploaded_file)
            current_chapter = "Mở đầu"
            chapters_data = {current_chapter: []}
            chapter_regex = re.compile(r'^(Chương\s+\d+|Chương\s+[IVXLCDM]+|Chương\s+[A-Za-zĂăÂâĐđÊêÔôƠơƯư]+)', re.IGNORECASE)
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text: continue
                if chapter_regex.match(text):
                    current_chapter = text
                    chapters_data[current_chapter] = []
                else:
                    chapters_data[current_chapter].append(text)
            
            st.session_state.chapters = {k: "\n".join(v) for k, v in chapters_data.items() if v}
            st.session_state.chapter_list = list(st.session_state.chapters.keys())
            st.success(f"Đã tìm thấy {len(st.session_state.chapter_list)} chương!")

    if st.session_state.chapter_list:
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1: start_ch = st.selectbox("Từ chương:", st.session_state.chapter_list, index=0)
        with col2: 
            start_idx = st.session_state.chapter_list.index(start_ch)
            end_ch = st.selectbox("Đến chương:", st.session_state.chapter_list[start_idx:], index=min(9, len(st.session_state.chapter_list[start_idx:])-1))
        
        start_index, end_index = st.session_state.chapter_list.index(start_ch), st.session_state.chapter_list.index(end_ch)
        selected_run_chapters = st.session_state.chapter_list[start_index : end_index + 1]
        
        st.markdown("---")
        st.subheader("🗣️ Chọn giọng đọc & Tốc độ")
        
        col3, col4 = st.columns(2)
        with col3: 
            selected_voice_name = st.selectbox("Danh sách giọng:", list(VOICES.keys()))
            voice_info = VOICES[selected_voice_name]
            batch_size = st.number_input("Gộp X chương/file (Ví dụ: 10):", min_value=1, max_value=100, value=1)
            
        with col4: 
            # Đã chuẩn hóa thanh tốc độ cho dễ hiểu với cả 2 hệ thống
            st.info("💡 Tốc độ: 1.0 là Chuẩn. Nhỏ hơn 1 là CHẬM, Lớn hơn 1 là NHANH.")
            speed = st.slider("Điều chỉnh tốc độ:", min_value=0.5, max_value=2.0, value=1.0, step=0.1)
            
            st.write("")
            if st.button("🔊 Nghe thử giọng (Test)"):
                preview_text = "Xin chào, đây là câu nói thử nghiệm. Đạo hữu thấy tốc độ và âm sắc thế nào, đã vừa tai chưa?"
                preview_txt_path = "preview_temp.txt"
                ext = "mp3" if voice_info["engine"] == "edge" else "wav"
                preview_audio_path = f"output/preview.{ext}"
                
                with open(preview_txt_path, "w", encoding="utf-8") as f: f.write(preview_text)
                
                try:
                    with st.spinner("Đang tạo âm thanh mẫu..."):
                        if voice_info["engine"] == "edge":
                            rate_pct = int((speed - 1.0) * 100)
                            rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"
                            cmd = f'python -m edge_tts --voice {voice_info["id"]} --rate={rate_str} -f "{preview_txt_path}" --write-media "{preview_audio_path}"'
                        else: # piper
                            piper_speed = 1.0 / speed # Đảo ngược toán học để chuẩn hóa slider
                            cmd = f'piper --model "{voice_info["model_path"]}" --length_scale {piper_speed} --sentence_silence 0.2 --input_file "{preview_txt_path}" --output_file "{preview_audio_path}"'
                            
                        subprocess.run(cmd, shell=True, check=True)
                    st.audio(preview_audio_path)
                except Exception as e:
                    st.error(f"Lỗi khi nghe thử: {e}")
                finally:
                    if os.path.exists(preview_txt_path): os.remove(preview_txt_path)
        
        st.markdown("---")
        if st.button("🚀 Bắt Đầu Chuyển Thể Toàn Bộ", type="primary", use_container_width=True):
            batches = [selected_run_chapters[i:i + batch_size] for i in range(0, len(selected_run_chapters), batch_size)]
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, batch in enumerate(batches):
                ext = "mp3" if voice_info["engine"] == "edge" else "wav"
                batch_name = f"Chuong_{start_index + (idx*batch_size) + 1}_den_{min(start_index + ((idx+1)*batch_size), end_index + 1)}"
                output_file = os.path.join("output", f"{batch_name}.{ext}")
                status_text.text(f"Đang xử lý gói {idx+1}/{len(batches)}...")
                
                full_batch_text = "".join([f"\n{ch}\n" + st.session_state.chapters[ch] for ch in batch])
                temp_txt = "temp_batch.txt"
                with open(temp_txt, "w", encoding="utf-8") as f: f.write(full_batch_text)
                
                if voice_info["engine"] == "edge":
                    rate_pct = int((speed - 1.0) * 100)
                    rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"
                    cmd = f'python -m edge_tts --voice {voice_info["id"]} --rate={rate_str} -f "{temp_txt}" --write-media "{output_file}"'
                else: # piper
                    piper_speed = 1.0 / speed
                    cmd = f'piper --model "{voice_info["model_path"]}" --length_scale {piper_speed} --sentence_silence 0.2 --input_file "{temp_txt}" --output_file "{output_file}"'
                
                try:
                    subprocess.run(cmd, shell=True, check=True)
                    st.audio(output_file)
                    st.success(f"✅ Xong: {output_file}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")
                finally:
                    if os.path.exists(temp_txt): os.remove(temp_txt)
                        
                progress_bar.progress((idx + 1) / len(batches))
            status_text.text("🎉 Hoàn thành toàn bộ!")
