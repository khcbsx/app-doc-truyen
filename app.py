import streamlit as st
import docx
import re
import os
import subprocess
import urllib.request

st.set_page_config(page_title="Word to Audio TTS", layout="wide")
st.title("📚 Chuyển Đổi Truyện Chữ Sang Audio (Cloud)")

os.makedirs("models", exist_ok=True)
os.makedirs("output", exist_ok=True)

# ---------------------------------------------------------
# NÂNG CẤP: TỰ ĐỘNG TẢI NHIỀU GIỌNG VÀ ĐỔI TÊN CHO ĐẸP
# ---------------------------------------------------------
voice_library = {
    "Giong_Nu_Truyen_Cam_Vais1000": "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium",
    "Giong_Nam_Co_Ban_Vivos": "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vivos/mac_quoc_viet/low/vi_VN-vivos-mac_quoc_viet-low"
}

with st.spinner("⏳ Đang đồng bộ kho giọng nói (bạn đợi xíu nhé)..."):
    for friendly_name, base_url in voice_library.items():
        onnx_path = os.path.join("models", f"{friendly_name}.onnx")
        json_path = os.path.join("models", f"{friendly_name}.onnx.json")
        if not os.path.exists(onnx_path):
            try:
                urllib.request.urlretrieve(base_url + ".onnx", onnx_path)
                urllib.request.urlretrieve(base_url + ".onnx.json", json_path)
            except Exception as e:
                pass # Nếu link giọng nào hỏng, tự bỏ qua để không làm sập app
# ---------------------------------------------------------

available_models = [f for f in os.listdir("models") if f.endswith(".onnx")]

if "chapters" not in st.session_state:
    st.session_state.chapters = {}
if "chapter_list" not in st.session_state:
    st.session_state.chapter_list = []

uploaded_file = st.file_uploader("Tải lên file Word (.docx)", type=["docx"])

if uploaded_file:
    if not st.session_state.chapters:
        with st.spinner("Đang phân tích file..."):
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
        col1, col2, col3 = st.columns(3)
        with col1: start_ch = st.selectbox("Từ chương:", st.session_state.chapter_list, index=0)
        with col2: 
            start_idx = st.session_state.chapter_list.index(start_ch)
            end_ch = st.selectbox("Đến chương:", st.session_state.chapter_list[start_idx:], index=min(9, len(st.session_state.chapter_list[start_idx:])-1))
        
        start_index, end_index = st.session_state.chapter_list.index(start_ch), st.session_state.chapter_list.index(end_ch)
        selected_run_chapters = st.session_state.chapter_list[start_index : end_index + 1]
        
        with col3: batch_size = st.number_input("Gộp X chương/file:", min_value=1, max_value=100, value=1)

        if not available_models:
            st.error("Chưa tải được giọng đọc nào.")
        else:
            # Ảo thuật đổi tên hiển thị đẹp mắt cho người dùng
            selected_model_file = st.selectbox("Chọn giọng đọc:", available_models, format_func=lambda x: x.replace(".onnx", "").replace("_", " "))
            model_path = os.path.join("models", selected_model_file)
            
            batches = [selected_run_chapters[i:i + batch_size] for i in range(0, len(selected_run_chapters), batch_size)]
            
            if st.button("🚀 Bắt Đầu Chuyển Thể", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, batch in enumerate(batches):
                    batch_name = f"Chuong_{start_index + (idx*batch_size) + 1}_den_{min(start_index + ((idx+1)*batch_size), end_index + 1)}"
                    output_file = os.path.join("output", f"{batch_name}.wav")
                    status_text.text(f"Đang xử lý gói {idx+1}/{len(batches)}...")
                    
                    full_batch_text = "".join([f"\n{ch}\n" + st.session_state.chapters[ch] for ch in batch])
                    temp_txt = "temp_batch.txt"
                    with open(temp_txt, "w", encoding="utf-8") as f: f.write(full_batch_text)
                    
                    command = f'piper --model "{model_path}" --input_file "{temp_txt}" --output_file "{output_file}"'
                    
                    try:
                        subprocess.run(command, shell=True, check=True)
                        st.audio(output_file, format="audio/wav")
                        st.success(f"✅ Xong: {output_file} (Bấm dấu 3 chấm ⋮ bên phải thanh nhạc để Tải Về)")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")
                    finally:
                        if os.path.exists(temp_txt): os.remove(temp_txt)
                            
                    progress_bar.progress((idx + 1) / len(batches))
                status_text.text("🎉 Hoàn thành toàn bộ!")
