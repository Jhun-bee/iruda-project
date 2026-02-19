# policy_matcher.py - 의미적 검색 시스템
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json
import os
import re
from datetime import datetime
import pandas as pd

class EnhancedPolicyMatcher:
    def __init__(self):
        print("정책 매칭 시스템 초기화 중...")
        
        # 한국어 특화 임베딩 모델 로드
        try:
            self.model = SentenceTransformer('klue/roberta-large')
            print("KLUE RoBERTa 모델 로드 완료")
        except Exception as e:
            print(f"KLUE 모델 로드 실패, 대체 모델 사용: {e}")
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # 정책 데이터 및 임베딩 초기화
        self.policies = []
        self.policy_embeddings = None
        self.policy_texts = []
        self.initialize_policy_embeddings()
        
        print(f"정책 매칭 시스템 준비 완료 ({len(self.policies)}개 정책)")
    
    def initialize_policy_embeddings(self):
        """정책 데이터를 벡터화하여 메모리에 저장"""
        try:
            # 정책 데이터 로드
            self.policies = self.load_government_policies()
            
            if not self.policies:
                print("경고: 정책 데이터가 없습니다.")
                return
            
            # 정책별 검색용 텍스트 생성
            self.policy_texts = []
            for policy in self.policies:
                combined_text = self.create_policy_search_text(policy)
                self.policy_texts.append(combined_text)
            
            # 일괄 벡터화 (배치 처리로 성능 향상)
            print("정책 데이터 벡터화 중...")
            self.policy_embeddings = self.model.encode(
                self.policy_texts, 
                show_progress_bar=True,
                batch_size=16,
                convert_to_numpy=True
            )
            
            print(f"정책 임베딩 생성 완료: {self.policy_embeddings.shape}")
            
        except Exception as e:
            print(f"정책 임베딩 초기화 실패: {e}")
            self.policies = []
            self.policy_embeddings = None
    
    def create_policy_search_text(self, policy):
        """정책 데이터를 검색에 최적화된 텍스트로 변환"""
        text_parts = []
        
        # 서비스명 (가중치 높음)
        if policy.get('서비스명'):
            text_parts.append(f"서비스: {policy['서비스명']}")
            text_parts.append(policy['서비스명'])  # 중복으로 가중치 증가
        
        # 지원대상 (중요)
        if policy.get('지원대상'):
            text_parts.append(f"대상: {policy['지원대상']}")
        
        # 지원내용 (핵심)
        if policy.get('지원내용'):
            text_parts.append(f"내용: {policy['지원내용']}")
        
        # 기관명
        if policy.get('기관명'):
            text_parts.append(f"기관: {policy['기관명']}")
        
        # 신청방법
        if policy.get('신청방법'):
            text_parts.append(f"신청: {policy['신청방법']}")
        
        # 구분 (중앙부처, 지자체, 민간)
        if policy.get('구분'):
            text_parts.append(f"분류: {policy['구분']}")
        
        return " ".join(text_parts)
    
    def semantic_search(self, query, user_profile=None, top_k=10):
        """의미적 유사도 기반 정책 검색"""
        if self.policy_embeddings is None:
            print("경고: 정책 임베딩이 없어 기존 방식 사용")
            return self.fallback_to_keyword_search(query)
        
        try:
            # 1단계: 사용자 쿼리 전처리 및 확장
            enhanced_query = self.enhance_search_query(query, user_profile)
            
            # 2단계: 쿼리 벡터화
            query_embedding = self.model.encode([enhanced_query])
            
            # 3단계: 코사인 유사도 계산
            similarities = cosine_similarity(query_embedding, self.policy_embeddings)[0]
            
            # 4단계: 상위 후보 선택 (더 많이 선택해서 규칙 기반 필터링)
            top_indices = np.argsort(similarities)[::-1][:top_k * 3]
            
            # 5단계: 후보 정책들에 대해 규칙 기반 검증 및 점수 계산
            candidates = []
            for idx in top_indices:
                if similarities[idx] < 0.1:  # 너무 낮은 유사도는 제외
                    continue
                    
                policy = self.policies[idx].copy()
                eligibility = self.check_eligibility(user_profile, policy) if user_profile else {'eligible': True, 'confidence': 0.5}
                
                # 종합 점수 계산
                combined_score = self.calculate_combined_score(
                    similarities[idx], 
                    eligibility,
                    query,
                    policy
                )
                
                candidates.append({
                    'policy': policy,
                    'semantic_score': float(similarities[idx]),
                    'eligibility': eligibility,
                    'combined_score': combined_score
                })
            
            # 6단계: 종합 점수로 재정렬
            candidates.sort(key=lambda x: x['combined_score'], reverse=True)
            
            # 7단계: 상위 결과만 반환 (매칭 정보 포함)
            final_results = []
            for candidate in candidates[:top_k]:
                policy = candidate['policy']
                policy['_match_info'] = {
                    'semantic_score': round(candidate['semantic_score'], 3),
                    'eligibility_score': round(candidate['eligibility']['confidence'], 3),
                    'eligible': candidate['eligibility']['eligible'],
                    'combined_score': round(candidate['combined_score'], 3)
                }
                final_results.append(policy)
            
            return final_results
            
        except Exception as e:
            print(f"의미적 검색 오류: {e}")
            return self.fallback_to_keyword_search(query)
    
    def enhance_search_query(self, query, user_profile):
        """사용자 프로필을 바탕으로 검색 쿼리 확장"""
        enhanced_parts = [query]
        
        if user_profile:
            # 지원 필요 영역 추가
            if user_profile.get('support_needs'):
                enhanced_parts.extend(user_profile['support_needs'])
            
            # 주거 상황 관련 키워드 추가
            if user_profile.get('housing_status'):
                if '자립준비청년' in user_profile['housing_status']:
                    enhanced_parts.append('자립준비청년 청소년')
            
            # 나이 관련 키워드 추가
            age = user_profile.get('age')
            if age and 18 <= age <= 39:
                enhanced_parts.append('청년')
        
        return ' '.join(enhanced_parts)
    
    def calculate_combined_score(self, semantic_score, eligibility, query, policy):
        """의미적 유사도, 자격요건, 추가 휴리스틱을 종합한 점수 계산"""
        base_score = semantic_score * 0.6  # 의미적 유사도 60%
        eligibility_score = eligibility['confidence'] * 0.3  # 자격 요건 30%
        
        # 키워드 매칭 보너스 10%
        keyword_bonus = self.calculate_keyword_bonus(query, policy) * 0.1
        
        return base_score + eligibility_score + keyword_bonus
    
    def calculate_keyword_bonus(self, query, policy):
        """직접적인 키워드 매칭에 대한 보너스 점수"""
        query_lower = query.lower()
        policy_text = (
            policy.get('서비스명', '') + ' ' + 
            policy.get('지원내용', '') + ' ' +
            policy.get('지원대상', '')
        ).lower()
        
        bonus = 0
        query_words = query_lower.split()
        
        for word in query_words:
            if len(word) > 1 and word in policy_text:
                bonus += 0.2
        
        return min(bonus, 1.0)  # 최대 1.0
    
    def check_eligibility(self, user_profile, policy):
        """사용자 프로필과 정책의 자격 요건 매칭"""
        if not user_profile:
            return {'eligible': True, 'confidence': 0.5, 'reasons': ['프로필 정보 부족']}
        
        checks = []
        total_weight = 0
        passed_weight = 0
        
        # 나이 조건 확인
        age_result = self.check_age_requirement(user_profile, policy)
        checks.append(('나이', age_result))
        total_weight += 0.3
        if age_result['passed']:
            passed_weight += 0.3
        
        # 소득 조건 확인  
        income_result = self.check_income_requirement(user_profile, policy)
        checks.append(('소득', income_result))
        total_weight += 0.4
        if income_result['passed']:
            passed_weight += 0.4
        
        # 특별 조건 확인 (자립준비청년 등)
        special_result = self.check_special_conditions(user_profile, policy)
        checks.append(('특별조건', special_result))
        total_weight += 0.3
        if special_result['passed']:
            passed_weight += 0.3
        
        confidence = passed_weight / total_weight if total_weight > 0 else 0.5
        eligible = confidence >= 0.7  # 70% 이상 통과해야 자격 있음
        
        return {
            'eligible': eligible,
            'confidence': confidence,
            'detailed_checks': checks,
            'reasons': [check[1]['reason'] for check in checks if not check[1]['passed']]
        }
    
    def check_age_requirement(self, user_profile, policy):
        """나이 조건 확인"""
        user_age = user_profile.get('age')
        if not user_age:
            return {'passed': True, 'reason': '나이 정보 없음'}
        
        target_text = policy.get('지원대상', '') + policy.get('서비스명', '')
        
        # 청년 대상 확인
        if '청년' in target_text:
            if 18 <= user_age <= 39:
                return {'passed': True, 'reason': '청년 대상 조건 충족'}
            else:
                return {'passed': False, 'reason': f'청년 대상 조건 불충족 (현재 {user_age}세)'}
        
        # 구체적 나이 범위 확인
        age_pattern = re.search(r'(\d+)세?\s*[~-이]\s*(\d+)세?', target_text)
        if age_pattern:
            min_age, max_age = map(int, age_pattern.groups())
            if min_age <= user_age <= max_age:
                return {'passed': True, 'reason': f'나이 조건 충족 ({min_age}-{max_age}세)'}
            else:
                return {'passed': False, 'reason': f'나이 조건 불충족 ({min_age}-{max_age}세 필요)'}
        
        return {'passed': True, 'reason': '나이 조건 명시되지 않음'}
    
    def check_income_requirement(self, user_profile, policy):
        """소득 조건 확인"""
        user_income = user_profile.get('income_level', '')
        if not user_income:
            return {'passed': True, 'reason': '소득 정보 없음'}
        
        target_text = policy.get('지원대상', '') + policy.get('지원내용', '')
        
        # 소득 관련 키워드 확인
        if any(word in target_text for word in ['기초생활수급', '차상위', '저소득']):
            if '50만원 이하' in user_income or '없음' in user_income:
                return {'passed': True, 'reason': '저소득층 대상 조건 충족'}
            else:
                return {'passed': False, 'reason': '저소득층 대상이나 소득 수준 불충족'}
        
        return {'passed': True, 'reason': '특별한 소득 조건 없음'}
    
    def check_special_conditions(self, user_profile, policy):
        """특별 조건 확인"""
        housing_status = user_profile.get('housing_status', '')
        support_needs = user_profile.get('support_needs', [])
        
        target_text = policy.get('지원대상', '') + policy.get('서비스명', '')
        
        # 자립준비청년 조건
        if '자립' in target_text and '자립준비청년' in housing_status:
            return {'passed': True, 'reason': '자립준비청년 조건 충족'}
        
        # 지원 영역 매칭
        policy_lower = target_text.lower()
        need_match = False
        
        for need in support_needs:
            if (need == '주거지원' and '주거' in policy_lower) or \
               (need == '취업지원' and '취업' in policy_lower) or \
               (need == '교육지원' and '교육' in policy_lower) or \
               (need == '경제지원' and ('생계' in policy_lower or '급여' in policy_lower)):
                need_match = True
                break
        
        if need_match:
            return {'passed': True, 'reason': '지원 필요 영역 일치'}
        
        return {'passed': True, 'reason': '특별 조건 없음 또는 불명확'}
    
    def fallback_to_keyword_search(self, query):
        """의미적 검색 실패 시 키워드 기반 검색으로 fallback"""
        try:
            filtered_policies = []
            query_lower = query.lower()
            
            for policy in self.policies:
                policy_text = (
                    policy.get('서비스명', '') + ' ' + 
                    policy.get('기관명', '') + ' ' +
                    policy.get('지원내용', '') + ' ' +
                    policy.get('지원대상', '')
                ).lower()
                
                if query_lower in policy_text:
                    filtered_policies.append(policy)
            
            return filtered_policies[:10]  # 상위 10개만 반환
            
        except Exception as e:
            print(f"Fallback 검색도 실패: {e}")
            return []
    
    def load_government_policies(self):
        """정부 정책 데이터 로드"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            excel_path = os.path.join(current_dir, '정부정책_임시DB.xlsx')
            
            if not os.path.exists(excel_path):
                print(f"정책 데이터 파일을 찾을 수 없습니다: {excel_path}")
                return []
            
            policies = []
            
            # Excel 파일에서 시트별로 데이터 읽기
            try:
                df_central = pd.read_excel(excel_path, sheet_name='중앙부처')
                policies.extend(df_central.to_dict('records'))
                print(f"중앙부처 정책 {len(df_central)}개 로드")
            except Exception as e:
                print(f"중앙부처 시트 읽기 실패: {e}")
            
            try:
                df_local = pd.read_excel(excel_path, sheet_name='지자체')
                policies.extend(df_local.to_dict('records'))
                print(f"지자체 정책 {len(df_local)}개 로드")
            except Exception as e:
                print(f"지자체 시트 읽기 실패: {e}")
            
            try:
                df_private = pd.read_excel(excel_path, sheet_name='민간')
                policies.extend(df_private.to_dict('records'))
                print(f"민간 정책 {len(df_private)}개 로드")
            except Exception as e:
                print(f"민간 시트 읽기 실패: {e}")
            
            # NaN 값들을 빈 문자열로 대체
            for policy in policies:
                for key, value in policy.items():
                    if pd.isna(value):
                        policy[key] = ''
            
            print(f"총 {len(policies)}개 정책 로드 완료")
            return policies
            
        except Exception as e:
            print(f"정책 데이터 로드 실패: {e}")
            return []

# 테스트 함수
def test_semantic_search():
    """의미적 검색 테스트"""
    try:
        matcher = EnhancedPolicyMatcher()
        
        test_queries = [
            "주거 지원이 필요해요",
            "취업 도움을 받고 싶습니다", 
            "생활비 지원 정책",
            "자립준비청년을 위한 도움"
        ]
        
        test_profile = {
            'age': 22,
            'housing_status': '자립준비청년',
            'income_level': '50만원 이하',
            'support_needs': ['주거지원', '경제지원']
        }
        
        for query in test_queries:
            print(f"\n🔍 검색어: {query}")
            results = matcher.semantic_search(query, test_profile, top_k=3)
            
            for i, policy in enumerate(results, 1):
                print(f"{i}. {policy.get('서비스명', 'N/A')}")
                if '_match_info' in policy:
                    match_info = policy['_match_info']
                    print(f"   유사도: {match_info['semantic_score']:.3f}")
                    print(f"   자격요건: {'✅' if match_info['eligible'] else '❌'}")
    
    except Exception as e:
        print(f"테스트 실패: {e}")

if __name__ == "__main__":
    test_semantic_search()