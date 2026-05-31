import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import os
import math

# 웹페이지 기본 설정 (브라우저 탭 제목 및 아이콘)
st.set_page_config(page_title="수혈 가이드라인 챗봇", page_icon="🩸", layout="centered")

# 1. 웹사이트 제목 및 설명 설정
st.title("🩸 수혈 가이드라인 커뮤니티 챗봇")
st.write("본 챗봇은 문서 내용을 기반으로 답변하는 교육용 챗봇이므로 참고하십시오.")

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

# 💡 긴 문서를 쪼개는 함수
def chunk_text(text, chunk_size=1000, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

# 💡 질문과 본문의 연관성을 계산하는 수학 함수
def cosine_similarity(v1, v2):
    dot_product = sum(x * y for x, y in zip(v1, v2))
    magnitude1 = math.sqrt(sum(x * x for x in v1))
    magnitude2 = math.sqrt(sum(x * x for x in v2))
    if not magnitude1 or not magnitude2:
        return 0
    return dot_product / (magnitude1 * magnitude2)

# 3. PDF를 조각내고 벡터 데이터로 미리 학습(Embedding)시켜두는 함수 (최초 1회만 실행됨)
@st.cache_data
def prepare_knowledge_base(file_path):
    with st.spinner("📚 가이드라인 문서를 스마트하게 분석하고 있습니다. 잠시만 기다려 주세요..."):
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        # 텍스트 조각내기
        chunks = chunk_text(text)
        
        # 각 조각을 구글 벡터 엔진(text-embedding-004)으로 변환
        embeddings = []
        for chunk in chunks:
            response = genai.embed_content(
                model="models/text-embedding-004",
                content=chunk,
                task_type="retrieval_document"
            )
            embeddings.append(response['embedding'])
            
        return chunks, embeddings

# 지식 베이스(족보) 로드
chunks, embeddings = prepare_knowledge_base(pdf_file)

# 4. 대화 기록 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 내용을 화면에 그려주기
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 질문 입력창
if prompt := st.chat_input("수혈 지침에 대해 질문해 주세요! (예: 농축적혈구 투여 기준)"):
    # 1) 유저 입력창에 표시 및 저장
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2) 관련 답변 찾기 및 생성 프로세스
    with st.chat_message("assistant"):
        try:
            # 유저의 질문도 벡터 데이터로 변환
            query_embedding_response = genai.embed_content(
                model="models/text-embedding-004",
                content=prompt,
                task_type="retrieval_query"
            )
            query_embedding = query_embedding_response['embedding']
            
            # 모든 조각들과의 유사도 점수 계산
            scores = [cosine_similarity(query_embedding, emb) for emb in embeddings]
            
            # 가장 연관성이 높은 상위 4개 조각을 선택 (풍부한 답변을 위해 4개로 확장)
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:4]
            relevant_contexts = [chunks[i] for i in top_indices]
            context_text = "\n\n---\n\n".join(relevant_contexts)
            
            # 최신 제미나이 모델 호출
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            # AI에게 내리는 가이드라인 명령어 (풍부한 서술 유도)
            full_prompt = (
                f"당신은 병원 수혈 지침 전문 챗봇입니다. 아래 제공된 [참고 지침]의 핵심 내용을 기반으로 사용자의 질문에 답변하세요.\n"
                f"사용자가 신뢰할 수 있도록 관련된 구체적인 수치, 적응증, 주의사항 등을 절대로 생략하지 말고 '매우 자세하고 친절하게' 풀어서 설명해 주세요.\n"
                f"가독성을 위해 줄바꿈과 불릿 기호(* 등)를 적극적으로 활용하여 구조적으로 답변하세요.\n"
                f"만약 제공된 지침 내용만으로 절대 답변할 수 없는 질문이라면, 지침서에서 해당 내용을 찾을 수 없다고 정중히 안내하세요.\n\n"
                f"[참고 지침 내용]\n{context_text}\n\n"
                f"질문: {prompt}"
            )
            
            response = model.generate_content(full_prompt)
            st.markdown(response.text)
            
            # AI 답변 기록 저장
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error(f"답변을 생성하는 중에 문제가 발생했습니다: {e}")
