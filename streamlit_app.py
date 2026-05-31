import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import os

# 1. 웹사이트 제목 및 설명 설정
st.title("🩸 수혈 가이드라인 챗봇")
st.write("문서 내용을 기반으로 답변합니다.")

# 2. 스트림릿 금고(Secrets)에서 구글 API 키 가져오기
if "GOOGLE_API_KEY" not in st.secrets:
    st.info("오른쪽 아래 'Manage app' -> 'Settings' -> 'Secrets'에 GOOGLE_API_KEY를 입력해 주세요.", icon="🔑")
    st.stop()

# 구글 제미나이 설정
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# 💡 [자동화] 이름 문제 해결을 위해 폴더 내의 PDF 파일을 자동으로 찾아내는 로직
pdf_file = None
for file in os.listdir("."):
    if file.lower().endswith(".pdf"):
        pdf_file = file
        break

if not pdf_file:
    st.error("저장소에서 PDF 파일을 찾을 수 없습니다. 수혈 가이드라인 PDF 파일을 업로드해 주세요!")
    st.stop()

# 3. PDF 파일에서 텍스트 추출하는 함수 (속도를 위해 캐싱 처리)
@st.cache_resource
def load_pdf(file_path):
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"PDF 파일을 읽는 중 오류가 발생했습니다: {e}")
        return None

# 자동으로 찾아낸 PDF 파일 읽기
pdf_text = load_pdf(pdf_file)

if pdf_text:
    # 대화 기록을 저장할 세션 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 이전 대화 내용 화면에 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 사용자 질문 입력창
    if prompt := st.chat_input("수혈 가이드라인에 대해 궁금한 점을 물어보세요!"):
        # 1) 사용자 메시지 화면에 표시 및 저장
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2) 제미나이 모델을 사용하여 PDF 기반 답변 생성
        with st.chat_message("assistant"):
            try:
                model = genai.GenerativeModel("gemini-2.5-flash")
                
                # AI에게 가이드라인 문서와 대화 맥락을 함께 전달
                full_prompt = (
                    f"당신은 병원 수혈 지침 전문 챗봇입니다. 아래 제공된 [지침 문서]의 내용을 기반으로만 사용자의 질문에 정확하고 친절하게 답변하세요.\n\n"
                    f"[지침 문서 내용]\n{pdf_text}\n\n"
                    f"질문: {prompt}"
                )
                
                response = model.generate_content(full_prompt)
                st.markdown(response.text)
                
                # AI 답변 저장
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"답변을 생성하는 중에 문제가 발생했습니다: {e}")
