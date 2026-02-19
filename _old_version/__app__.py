from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os
from dotenv import load_dotenv
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
import openai  # 나중에 활성화

# 여기에 추가
try:
    from policy_matcher import EnhancedPolicyMatcher
    ENHANCED_MATCHER_AVAILABLE = True
except ImportError as e:
    print(f"Enhanced Policy Matcher를 import할 수 없습니다: {e}")
    ENHANCED_MATCHER_AVAILABLE = False

# 환경변수 로드
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-this')

# Flask-Login 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# OpenAI API 키 설정 (나중에 활성화)
openai.api_key = os.getenv('OPENAI_API_KEY')

# 전역 변수로 선언
enhanced_matcher = None

def initialize_enhanced_matcher():
    """앱 시작 시 정책 매칭 시스템 초기화"""
    global enhanced_matcher
    if not ENHANCED_MATCHER_AVAILABLE:
        print("Enhanced Policy Matcher 라이브러리를 사용할 수 없습니다.")
        return False
    try:
        enhanced_matcher = EnhancedPolicyMatcher()
        return True
    except Exception as e:
        print(f"Enhanced Policy Matcher 초기화 실패: {e}")
        return False

def get_user_profile(user_id):
    """사용자 프로필 정보 가져오기"""
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT housing_status, income_level, support_needs 
            FROM user_profiles WHERE user_id = ?
        ''', (user_id,))
        profile_data = cursor.fetchone()
        conn.close()
        
        if profile_data:
            return {
                'housing_status': profile_data[0],
                'income_level': profile_data[1], 
                'support_needs': json.loads(profile_data[2]) if profile_data[2] else []
            }
        return None
    except Exception as e:
        print(f"사용자 프로필 조회 실패: {e}")
        return None

def apply_keyword_filter(policies, search_query):
    """기존 키워드 필터링 (fallback용)"""
    return [
        policy for policy in policies
        if (search_query.lower() in str(policy.get('서비스명', '')).lower() or
            search_query.lower() in str(policy.get('기관명', '')).lower() or
            search_query.lower() in str(policy.get('지원내용', '')).lower() or
            search_query.lower() in str(policy.get('지원대상', '')).lower())
    ]

def apply_category_filter(policies, category_filter):
    """기존 카테고리 필터링 (fallback용)"""
    return [
        policy for policy in policies
        if policy.get('구분', '') == category_filter
    ]

class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data[0], user_data[1], user_data[2])
    return None

# 정부 정책 데이터 로드 함수
def load_government_policies():
    try:
        # 스크립트 파일 기준 상대 경로로 지정
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        excel_path = os.path.join(current_dir, '정부정책_임시DB.xlsx')
        
        # Excel 파일에서 정책 데이터 읽기
        df = pd.read_excel(excel_path, sheet_name='중앙부처')
        policies = df.to_dict('records')
        
        # 지자체 데이터도 추가
        df_local = pd.read_excel(excel_path, sheet_name='지자체')
        policies.extend(df_local.to_dict('records'))
        
        # 민간 데이터도 추가
        df_private = pd.read_excel(excel_path, sheet_name='민간')
        policies.extend(df_private.to_dict('records'))
        
        return policies
    except Exception as e:
        print(f"정책 데이터 로드 실패: {e}")
        return []

# 홈페이지
@app.route('/')
def home():
    return render_template('home.html')

# 회원가입 페이지
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    # POST 요청 처리
    data = request.form
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    # 프로필 정보
    housing_status = data.get('housing_status')
    income_level = data.get('income_level')
    support_needs = data.getlist('support_needs')  # 다중 선택
    
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 사용자 생성
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (name, email, password_hash) 
            VALUES (?, ?, ?)
        ''', (name, email, password_hash))
        
        user_id = cursor.lastrowid
        
        # 프로필 정보 저장
        cursor.execute('''
            INSERT INTO user_profiles 
            (user_id, housing_status, income_level, support_needs)
            VALUES (?, ?, ?, ?)
        ''', (user_id, housing_status, income_level, json.dumps(support_needs)))
        
        conn.commit()
        conn.close()
        
        flash('회원가입이 완료되었습니다!', 'success')
        return redirect(url_for('login'))
        
    except sqlite3.IntegrityError:
        flash('이미 존재하는 이메일입니다.', 'error')
        return render_template('register.html')

# 로그인 페이지
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    email = request.form.get('email')
    password = request.form.get('password')
    
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name, password_hash FROM users WHERE email = ?', (email,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data and check_password_hash(user_data[3], password):
        user = User(user_data[0], user_data[1], user_data[2])
        login_user(user)
        return redirect(url_for('dashboard'))
    else:
        flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
        return render_template('login.html')

# 대시보드 (개선된 버전)
@app.route('/dashboard')
@login_required
def dashboard():
    # 사용자 로드맵 조회
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, description, priority_areas, timeline 
        FROM roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
    ''', (current_user.id,))
    roadmap_data = cursor.fetchone()
    conn.close()
    
    roadmap = None
    if roadmap_data:
        roadmap = {
            'title': roadmap_data[0],
            'description': roadmap_data[1],
            'priority_areas': json.loads(roadmap_data[2]) if roadmap_data[2] else [],
            'timeline': json.loads(roadmap_data[3]) if roadmap_data[3] else {}
        }
    
    return render_template('dashboard.html', roadmap=roadmap)

# 대시보드 통계 API
@app.route('/dashboard-stats')
@login_required
def dashboard_stats():
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 활성 할일 개수
        cursor.execute('''
            SELECT COUNT(*) FROM progress_tracking 
            WHERE user_id = ? AND status IN ('pending', 'in_progress')
        ''', (current_user.id,))
        active_tasks = cursor.fetchone()[0]
        
        # 완료된 할일 개수
        cursor.execute('''
            SELECT COUNT(*) FROM progress_tracking 
            WHERE user_id = ? AND status = 'completed'
        ''', (current_user.id,))
        completed_tasks = cursor.fetchone()[0]
        
        # 추천 정책 개수 (임시로 3개)
        recommended_policies = 3
        
        conn.close()
        
        return jsonify({
            'success': True,
            'active_tasks': active_tasks,
            'completed_tasks': completed_tasks,
            'recommended_policies': recommended_policies
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 채팅 API (OpenAI 연동)
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        
        # OpenAI API 호출 (실제 구현 시)
        # if openai.api_key:
        #     response = openai.ChatCompletion.create(
        #         model="gpt-3.5-turbo",
        #         messages=[
        #             {"role": "system", "content": "당신은 자립준비청년을 도와주는 AI 상담사입니다. 친근하고 도움이 되는 조언을 해주세요."},
        #             {"role": "user", "content": message}
        #         ],
        #         temperature=0.7,
        #         max_tokens=500
        #     )
        #     ai_response = response.choices[0].message.content
        # else:
        
        # 임시 응답 생성 (OpenAI 없을 때)
        ai_response = generate_mock_response(message)
        suggestion = check_for_page_suggestion(message)
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'suggestion': suggestion
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def generate_mock_response(message):
    """OpenAI 대신 사용할 임시 응답 생성기"""
    message_lower = message.lower()
    
    if '로드맵' in message_lower or '계획' in message_lower:
        return "로드맵 생성을 도와드릴게요! 개인 맞춤형 자립 계획을 세워보시겠어요? 로드맵 페이지에서 자세한 계획을 확인하실 수 있습니다."
    
    elif '정책' in message_lower or '지원' in message_lower:
        return "지원정책 검색을 도와드릴게요! 현재 여러 정부 지원정책이 있는데, 어떤 분야의 지원을 원하시나요? 주거, 경제, 교육, 취업 중에서 선택해주세요."
    
    elif '할일' in message_lower or 'todo' in message_lower.replace(' ', ''):
        return "할 일 관리를 도와드릴게요! 로드맵에서 생성된 계획들을 할 일 목록으로 변환해서 체계적으로 관리할 수 있어요."
    
    elif '안녕' in message_lower or 'hello' in message_lower:
        return f"안녕하세요, {current_user.name}님! 오늘은 어떤 것을 도와드릴까요? 로드맵 작성, 정책 찾기, 또는 다른 궁금한 것이 있으시면 언제든 말씀해주세요! 😊"
    
    elif '도움' in message_lower or 'help' in message_lower:
        return "제가 도울 수 있는 것들이 많아요! 📋 개인화된 로드맵 생성, 💰 맞춤 지원정책 찾기, ✅ 할 일 관리, 📝 신청서 작성 도움 등이 있어요. 무엇부터 시작해볼까요?"
    
    else:
        return "흥미로운 질문이네요! 더 구체적으로 말씀해주시면 더 정확한 도움을 드릴 수 있어요. 로드맵이나 지원정책에 대해 궁금한 점이 있으시면 언제든 물어보세요!"

def check_for_page_suggestion(message):
    """메시지를 분석해서 페이지 이동 제안"""
    message_lower = message.lower()
    
    if '로드맵' in message_lower:
        return {
            'type': 'redirect',
            'url': '/roadmap',
            'message': '로드맵 페이지로 이동해서 자세한 계획을 확인해보시겠어요?'
        }
    elif '정책' in message_lower or '지원' in message_lower:
        return {
            'type': 'redirect',
            'url': '/policies',
            'message': '지원정책 페이지에서 맞춤 정책을 찾아보시겠어요?'
        }
    return None

# 로드맵 페이지
@app.route('/roadmap')
@login_required
def roadmap():
    # 사용자 로드맵 조회
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, description, priority_areas, timeline 
        FROM roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
    ''', (current_user.id,))
    roadmap_data = cursor.fetchone()
    
    roadmap = None
    progress_percentage = 0
    
    if roadmap_data:
        roadmap = {
            'title': roadmap_data[0],
            'description': roadmap_data[1],
            'priority_areas': json.loads(roadmap_data[2]) if roadmap_data[2] else [],
            'timeline': json.loads(roadmap_data[3]) if roadmap_data[3] else {}
        }
        
        # 진행률 계산
        cursor.execute('''
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM progress_tracking WHERE user_id = ?
        ''', (current_user.id,))
        progress_data = cursor.fetchone()
        if progress_data[0] > 0:
            progress_percentage = int((progress_data[1] / progress_data[0]) * 100)
    
    conn.close()
    return render_template('roadmap.html', roadmap=roadmap, progress_percentage=progress_percentage)

# 로드맵 상세 계획 생성 API
@app.route('/roadmap/detail-plan', methods=['POST'])
@login_required
def roadmap_detail_plan():
    try:
        data = request.json
        period = data.get('period')
        goals = data.get('goals')
        
        # 상세 계획 생성 (실제로는 OpenAI API 사용)
        detail_plan = generate_detail_plan(period, goals)
        
        return jsonify({
            'success': True,
            'detail_plan': detail_plan
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def generate_detail_plan(period, goals):
    """상세 계획 생성 함수 (OpenAI 대신 임시 구현)"""
    detail_plan = []
    
    for i, goal in enumerate(goals):
        if '주거' in goal:
            detail_plan.append({
                'title': f"{goal} - 세부 계획",
                'tasks': [
                    "주거급여 신청 자격 요건 확인하기",
                    "필요 서류 준비 (소득증명서, 임대차계약서)",
                    "관할 주민센터에서 신청 접수하기",
                    "심사 결과 확인 및 후속 조치",
                    "월별 주거비 관리 시스템 구축하기"
                ],
                'estimated_time': '2-3주'
            })
        elif '취업' in goal or '구직' in goal:
            detail_plan.append({
                'title': f"{goal} - 세부 계획",
                'tasks': [
                    "이력서 및 자기소개서 작성하기",
                    "취업지원 프로그램 신청하기",
                    "직업훈련 과정 알아보기",
                    "구인구직 사이트 활용법 익히기",
                    "면접 준비 및 연습하기"
                ],
                'estimated_time': '3-4주'
            })
        elif '생활비' in goal or '경제' in goal:
            detail_plan.append({
                'title': f"{goal} - 세부 계획",
                'tasks': [
                    "월별 수입/지출 현황 파악하기",
                    "생계급여 지원 신청하기",
                    "가계부 작성 습관 만들기",
                    "비상자금 적립 계획 세우기",
                    "금융 교육 프로그램 수강하기"
                ],
                'estimated_time': '1-2주'
            })
        else:
            detail_plan.append({
                'title': f"{goal} - 세부 계획",
                'tasks': [
                    f"{goal} 관련 정보 수집하기",
                    "전문가 상담 받기",
                    "단계별 실행 계획 수립하기",
                    "필요한 지원 프로그램 찾기",
                    "정기적인 점검 및 조정하기"
                ],
                'estimated_time': '2주'
            })
    
    return detail_plan

# Todo 변환 API
@app.route('/roadmap/convert-to-todos', methods=['POST'])
@login_required
def convert_to_todos():
    try:
        data = request.json
        period = data.get('period')
        goals = data.get('goals')
        
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 로드맵 ID 가져오기
        cursor.execute('''
            SELECT id FROM roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
        ''', (current_user.id,))
        roadmap_id = cursor.fetchone()[0]
        
        # 각 목표를 Todo로 변환
        for goal in goals:
            cursor.execute('''
                INSERT INTO progress_tracking 
                (user_id, roadmap_id, task_name, task_category, status, priority)
                VALUES (?, ?, ?, ?, 'pending', 3)
            ''', (current_user.id, roadmap_id, goal, period))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# AI 로드맵 생성 (기존 함수 개선)
@app.route('/generate-roadmap', methods=['POST'])
@login_required
def generate_roadmap():
    try:
        # 사용자 프로필 정보 가져오기
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT housing_status, income_level, support_needs 
            FROM user_profiles WHERE user_id = ?
        ''', (current_user.id,))
        profile_data = cursor.fetchone()
        
        if not profile_data:
            return jsonify({'success': False, 'error': '프로필 정보가 없습니다.'})
        
        # OpenAI 대신 샘플 데이터 사용
        support_needs = json.loads(profile_data[2]) if profile_data[2] else []
        roadmap = {
            "title": f"{current_user.name}님의 맞춤형 자립 로드맵",
            "description": "체계적인 자립을 위한 단계별 계획입니다.",
            "priority_areas": ["주거 안정", "경제적 자립", "사회적 네트워크 구축"],
            "timeline": {
                "1개월": ["주거급여 신청", "구직활동 시작", "자립지원센터 상담"],
                "3개월": ["안정적 일자리 확보", "생활비 관리 시스템 구축", "멘토 찾기"],
                "6개월": ["주거 독립 준비", "비상자금 마련", "사회보험 가입"]
            }
        }
        
        # 로드맵을 데이터베이스에 저장
        cursor.execute('''
            INSERT INTO roadmaps (user_id, title, description, priority_areas, timeline)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            current_user.id,
            roadmap['title'],
            roadmap['description'],
            json.dumps(roadmap['priority_areas']),
            json.dumps(roadmap['timeline'])
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'roadmap': roadmap})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 정책 검색 페이지
@app.route('/policies')
@login_required
def policies():
    # 검색 파라미터 가져오기
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    recommended = request.args.get('recommended', False)
    
    # Enhanced Matcher가 사용 가능하고 의미있는 검색어가 있을 때
    if enhanced_matcher and search_query and len(search_query) > 2:
        try:
            user_profile = get_user_profile(current_user.id)
            filtered_policies = enhanced_matcher.semantic_search(
                query=search_query,
                user_profile=user_profile,
                top_k=20
            )
        except Exception as e:
            print(f"의미적 검색 실패, 기존 방식 사용: {e}")
            # 기존 방식으로 fallback
            all_policies = load_government_policies()
            filtered_policies = all_policies.copy()
            if search_query:
                filtered_policies = apply_keyword_filter(filtered_policies, search_query)
    else:
        # 기존 검색 방식 유지
        all_policies = load_government_policies()
        filtered_policies = all_policies.copy()
        
        if search_query:
            filtered_policies = apply_keyword_filter(filtered_policies, search_query)
        
        if category_filter:
            filtered_policies = apply_category_filter(filtered_policies, category_filter)
        
        if recommended:
            filtered_policies = get_recommended_policies(filtered_policies)
    
    return render_template('policies.html', policies=filtered_policies)

def get_recommended_policies(policies):
    """사용자 프로필 기반 정책 추천"""
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT housing_status, income_level, support_needs 
            FROM user_profiles WHERE user_id = ?
        ''', (current_user.id,))
        profile_data = cursor.fetchone()
        conn.close()
        
        if not profile_data:
            return policies[:10]  # 프로필 없으면 상위 10개 반환
        
        support_needs = json.loads(profile_data[2]) if profile_data[2] else []
        
        recommended = []
        for policy in policies:
            score = 0
            policy_text = (policy.get('서비스명', '') + ' ' + 
                          policy.get('지원내용', '') + ' ' + 
                          policy.get('지원대상', '')).lower()
            
            # 지원 요구사항 매칭
            for need in support_needs:
                if need == '주거지원' and ('주거' in policy_text or '임대' in policy_text):
                    score += 3
                elif need == '경제지원' and ('생계' in policy_text or '급여' in policy_text):
                    score += 3
                elif need == '취업지원' and ('취업' in policy_text or '일자리' in policy_text):
                    score += 3
                elif need == '교육지원' and ('교육' in policy_text or '학비' in policy_text):
                    score += 3
                elif need == '심리지원' and ('상담' in policy_text or '심리' in policy_text):
                    score += 2
            
            # 자립준비청년 대상 정책 우선
            if '자립' in policy_text or '청소년' in policy_text:
                score += 2
            
            if score > 0:
                recommended.append((policy, score))
        
        # 점수 순으로 정렬하고 상위 20개 반환
        recommended.sort(key=lambda x: x[1], reverse=True)
        return [policy for policy, score in recommended[:20]]
        
    except Exception as e:
        print(f"추천 정책 생성 오류: {e}")
        return policies[:10]

# 정책 추천 API
@app.route('/policies/recommend', methods=['POST'])
@login_required
def recommend_policies():
    try:
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# MyPage 라우트들
@app.route('/mypage')
@login_required
def mypage():
    # 사용자 정보와 프로필 가져오기
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, email, age FROM users WHERE id = ?', (current_user.id,))
    user_data = cursor.fetchone()
    
    cursor.execute('''
        SELECT housing_status, income_level, education_level, employment_status, support_needs
        FROM user_profiles WHERE user_id = ?
    ''', (current_user.id,))
    profile_data = cursor.fetchone()
    
    conn.close()
    
    user = {
        'id': user_data[0],
        'name': user_data[1],
        'email': user_data[2],
        'age': user_data[3]
    }
    
    profile = {}
    if profile_data:
        profile = {
            'housing_status': profile_data[0],
            'income_level': profile_data[1],
            'education_level': profile_data[2],
            'employment_status': profile_data[3],
            'support_needs': json.loads(profile_data[4]) if profile_data[4] else []
        }
    
    return render_template('mypage.html', user=user, profile=profile)

@app.route('/mypage', methods=['POST'])
@login_required
def update_mypage():
    try:
        # 폼 데이터 가져오기
        name = request.form.get('name')
        email = request.form.get('email')
        age = request.form.get('age')
        
        # 프로필 정보
        housing_status = request.form.get('housing_status')
        income_level = request.form.get('income_level')
        support_needs = request.form.getlist('support_needs')
        
        # 비밀번호 변경 (선택사항)
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 사용자 기본 정보 업데이트
        cursor.execute('''
            UPDATE users SET name = ?, email = ?, age = ? WHERE id = ?
        ''', (name, email, age, current_user.id))
        
        # 프로필 정보 업데이트
        cursor.execute('''
            UPDATE user_profiles 
            SET housing_status = ?, income_level = ?, support_needs = ?
            WHERE user_id = ?
        ''', (housing_status, income_level, json.dumps(support_needs), current_user.id))
        
        # 비밀번호 변경 처리
        if current_password and new_password:
            cursor.execute('SELECT password_hash FROM users WHERE id = ?', (current_user.id,))
            stored_hash = cursor.fetchone()[0]
            
            if check_password_hash(stored_hash, current_password):
                new_hash = generate_password_hash(new_password)
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                             (new_hash, current_user.id))
                flash('비밀번호가 변경되었습니다.', 'success')
            else:
                flash('현재 비밀번호가 올바르지 않습니다.', 'error')
                conn.close()
                return redirect(url_for('mypage'))
        
        conn.commit()
        conn.close()
        
        flash('정보가 성공적으로 업데이트되었습니다.', 'success')
        return redirect(url_for('mypage'))
        
    except Exception as e:
        flash(f'업데이트 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('mypage'))

# @app.route('/mypage/roadmaps')
# @login_required
# def mypage_roadmaps():
#     return render_template('mypage_roadmaps.html')

# @app.route('/mypage/todos')
# @login_required
# def mypage_todos():
#     return render_template('mypage_todos.html')

# # 신청양식 생성 페이지
# @app.route('/application-form')
# @login_required
# def application_form():
#     policy_name = request.args.get('policy', '')
#     return render_template('application_form.html', policy_name=policy_name)

# 누락된 템플릿용 임시 라우트들
@app.route('/application-form')
def application_form_page():
    policy_name = request.args.get('policy', '')
    # 임시 HTML 반환 (나중에 템플릿 생성)
    return f'''
    <html>
    <head><title>신청양식 생성</title></head>
    <body style="padding: 50px; font-family: Arial;">
        <h1>신청양식 생성 페이지</h1>
        <p>정책: {policy_name}</p>
        <p>이 기능은 곧 구현 예정입니다.</p>
        <a href="/policies">← 정책 페이지로 돌아가기</a>
    </body>
    </html>
    '''

@app.route('/mypage/roadmaps')
@login_required
def mypage_roadmaps():
    # 임시 HTML 반환
    return '''
    <html>
    <head><title>내 로드맵 관리</title></head>
    <body style="padding: 50px; font-family: Arial;">
        <h1>내 로드맵 관리</h1>
        <p>이 기능은 곧 구현 예정입니다.</p>
        <a href="/dashboard">← 대시보드로 돌아가기</a>
    </body>
    </html>
    '''

@app.route('/mypage/todos')
@login_required
def mypage_todos():
    # 임시 HTML 반환
    return '''
    <html>
    <head><title>할 일 관리</title></head>
    <body style="padding: 50px; font-family: Arial;">
        <h1>할 일 관리</h1>
        <p>이 기능은 곧 구현 예정입니다.</p>
        <a href="/dashboard">← 대시보드로 돌아가기</a>
    </body>
    </html>
    '''

# 로그아웃
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    # 데이터베이스 초기화
    from database.init_db import init_database
    init_database()
    
    # 개선된 정책 매칭 시스템 초기화
    print("이루다 시스템 초기화 중...")
    if initialize_enhanced_matcher():
        print("✅ Enhanced Policy Matcher 준비 완료!")
    else:
        print("⚠️  기본 시스템으로 시작 (Enhanced Matcher 비활성)")
    
    # 앱 실행
    print("🚀 이루다 서비스 시작!")
    app.run(debug=True, host='0.0.0.0', port=5000)