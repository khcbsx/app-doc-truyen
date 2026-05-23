```python
import streamlit as st
import docx
import re
import os
import subprocess
import platform

st.set_page_config(page_title="Word to Audio TTS", layout="wide")
st.title("📚 Chuyển Đổi Truyện Chữ Word Sang Audio (Mô hình Local ONNX)")

os.makedirs("models", exist_ok=True)
os.makedirs("output", exist_ok=True)
available_models = [f for f in os.listdir("models") if f.endswith(".onnx")]

if "chapters" not in st.session_state:
    st.session_state.chapters = {}
if "chapter_list" not in st.session_state:
    st.session_state.chapter_list = []

uploaded_file = st.file_uploader("Bước 1: Tải lên file Word truyện chữ (.docx)", type=["docx"])

if uploaded_file:
    if not st.session_state.chapters:
        with st.spinner("Đang phân tích cấu trúc file Word và tách chương..."):
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
            st.success(f"Tìm thấy tổng cộng {len(st.session_state.chapter_list)} chương trong file!")

    if st.session_state.chapter_list:
        st.subheader("⚙️ Cấu hình khoảng chương cần chuyển đổi")
        col1, col2, col3 = st.columns(3)
        with col1:
            start_ch = st.selectbox("Từ chương:", st.session_state.chapter_list, index=0)
        with col2:
            start_idx = st.session_state.chapter_list.index(start_ch)
            end_ch = st.selectbox("Đến chương:", st.session_state.chapter_list[start_idx:], index=min(9, len(st.session_state.chapter_list[start_idx:])-1))
            
        start_index = st.session_state.chapter_list.index(start_ch)
        end_index = st.session_state.chapter_list.index(end_ch)
        selected_run_chapters = st.session_state.chapter_list[start_index : end_index + 1]
        
        with col3:
            batch_size = st.number_input("Chia nhóm lưu file (mỗi file gộp X chương):", min_value=1, max_value=50, value=1)

        st.subheader("🗣️ Chọn giọng đọc mô hình Local")
        if not available_models:
            st.error("Chưa tìm thấy file .onnx nào. Hãy bỏ file vào thư mục 'models'.")
        else:
            selected_model = st.selectbox("Danh sách giọng đọc ONNX:", available_models)
            model_path = os.path.join("models", selected_model)
            batches = [selected_run_chapters[i:i + batch_size] for i in range(0, len(selected_run_chapters), batch_size)]
            
            if st.button("🚀 Bắt Đầu Chuyển Thể Audio Hàng Loạt", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Tìm file piper.exe trong thư mục piper nội bộ
                piper_exe = os.path.join("piper", "piper.exe") if platform.system() == "Windows" else os.path.join("piper", "piper")
                
                if not os.path.exists(piper_exe):
                    st.error(f"Không tìm thấy công cụ lõi tại {piper_exe}. Vui lòng kiểm tra lại Giai đoạn 3 Bước 2.")
                else:
                    for idx, batch in enumerate(batches):
                        batch_name = f"Chuong_{start_index + (idx*batch_size) + 1}_den_{min(start_index + ((idx+1)*batch_size), end_index + 1)}"
                        output_file = os.path.join("output", f"{batch_name}.wav")
                        status_text.text(f"Đang xử lý gói {idx+1}/{len(batches)}...")
                        
                        full_batch_text = "".join([f"\n{ch}\n" + st.session_state.chapters[ch] for ch in batch])
                        temp_txt = "temp_batch.txt"
                        with open(temp_txt, "w", encoding="utf-8") as f:
                            f.write(full_batch_text)
                        
                        command = f'"{piper_exe}" --model "{model_path}" --input_file "{temp_txt}" --output_file "{output_file}"'
                        
                        try:
                            subprocess.run(command, shell=True, check=True)
                            st.audio(output_file, format="audio/wav")
                            st.success(f"✅ Đã xuất xong file: {output_file}")
                        except Exception as e:
                            st.error(f"Lỗi: {e}")
                        finally:
                            if os.path.exists(temp_txt): os.remove(temp_txt)
                                
                        progress_bar.progress((idx + 1) / len(batches))
                    
                    status_text.text("🎉 Đã hoàn thành toàn bộ tiến trình!")
