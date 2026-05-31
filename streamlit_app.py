import streamlit as st
import google.generativeai as genai
import pdfplumber
import os

# 웹페이지 기본 설정
st.set_page_config(page_title="수혈 가이드라인 챗봇", page_icon="🩸", layout="centered")

# 1. 웹사이트 제목 및 설명 설정
st.title("🩸 수혈 가이드라인 챗봇")
st.write("혈액은행")

# 2. 스트림릿 금고(Secrets)에서 구글 API 키 가져오기
if "GOOGLE_API_KEY" not in st.secrets:
    st.info("오른쪽 아래 'Manage app' -> 'Settings' -> 'Secrets'에 GOOGLE_API_KEY를 입력해 주세요.", icon="🔑")
    st.stop()

# 구글 제미나이 설정
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# [자동화] 폴더 내의 PDF 파일 자동으로 찾아내기
pdf_file = None
for file in os.listdir("."):
    if file.lower().endswith(".pdf"):
        pdf_file = file
        break

if not pdf_file:
    st.error("저장소에서 PDF 파일을 찾을 수 없습니다. 수혈 가이드라인 PDF 파일을 깃허브에 업로드해 주세요!")
    st.stop()

# 💡 [핵심 개선] 문서를 쪼개지 않고 통째로 읽어서 캐싱하는 함수
@st.cache_data
def load_full_pdf(file_path):
    with st.spinner("📚 가이드라인 전체 문서를 통째로 뇌에 기억시키고 있습니다. 최초 1회만 진행됩니다..."):
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

# 가이드라인 전체 텍스트 로드 (앱 시작할 때 딱 한 번만 실행됨)
full_guideline_text = load_full_pdf(pdf_file)

# 3. 대화 기록 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 내용을 화면에 그려주기
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 질문 입력창
if prompt := st.chat_input("수혈 지침에 대해 질문해 주세요! (예: 농축적혈구 투여 기준)"):
    # 유저 입력창에 표시 및 저장
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 답변 생성 프로세스
    with st.chat_message("assistant"):
        try:
            # 최신 제미나이 모델 호출
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            # AI에게 가이드라인 '전체 전문'을 프롬프트에 직접 주입
            full_prompt = (
                f"당신은 병원 수혈 지침 전문 챗봇입니다. 아래 제공된 [수혈 가이드라인 전문]의 내용을 완벽히 파악하여 사용자의 질문에 정확하게 답변하세요.\n"
                f"의료 지침이므로 정확성이 최우선입니다. 가이드라인에 명시된 구체적인 수치, 적응증, 예외 조항, 주의사항 등을 절대로 생략하거나 요약하지 말고 '매우 자세하고 친절하게' 서술하세요.\n"
                f"가독성을 위해 줄바꿈과 불릿 기호(* 등)를 적극적으로 활용하여 구조적으로 답변하세요.\n"
                f"만약 제공된 지침 내용만으로 절대 답변할 수 없는 질문이라면, 지침서에서 해당 내용을 찾을 수 없다고 정중히 안내하세요.\n\n"
                f"[수혈 가이드라인 전문]\n{full_guideline_text}\n\n"
                f"질문: {prompt}"
            )
            
            # 답변 생성 및 출력
            response = model.generate_content(full_prompt)
            st.markdown(response.text)
            
            # AI 답변 기록 저장
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error(f"답변을 생성하는 중에 문제가 발생했습니다: {e}")
