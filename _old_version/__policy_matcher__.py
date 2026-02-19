# policy_matcher.py
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json
import os
import re
from datetime import datetime

class EnhancedPolicyMatcher:
    def __init__(self):
        print("정책 매칭 시스템 초기화 중...")
        
        # 한국어 특화 임베딩 모델 로드
        self.model = SentenceTransformer('klue/roberta-large')
        
        # 정책 데이터 및 임베딩 초기화
        self.policies = []
        self.policy_embeddings = None
        self.initialize_policy_embeddings()
        
        print(f"정책 매칭 시스템 준비 완료 ({len(self.policies)}개 정책)")
    
    def initialize_policy_embeddings(self):
        """정책 데이터를 벡터화하여 메모리에 저장"""
        try:
            # 기존 load_government_policies() 함수 활용
            self.policies = load_government_policies()
            
            if not self.policies:
                print("경고: 정책 데이터가 없습니다.")
                return
            
            # 정책별 검색용 텍스트 생성
            policy_texts = []
            for policy in self.policies:
                combined_text = self.create_policy_search_text(policy)
                policy_texts.append(combined_text)
            
            # 일괄 벡터화
            self.policy_embeddings = self.model.encode(
                policy_texts, 
                show_progress_bar=True,
                batch_size=16
            )
            
            print(f"정책 임베딩 생성 완료: {self.policy_embeddings.shape}")
            
        except Exception as e:
            print(f"정책 임베딩 초기화 실패: {e}")
            self.policies = []
            self.policy_embeddings = None
            
    def semantic_search(self, query, user_profile, top_k=10):
        """의미적 유사도 기반 정책 검색"""
        if self.policy_embeddings is None:
            print("경고: 정책 임베딩이 없어 기존 방식 사용")
            return self.fallback_to_keyword_search(query)
        
        try:
            # 1단계: 사용자 쿼리 벡터화
            query_embedding = self.model.encode([query])
            
            # 2단계: 코사인 유사도 계산
            similarities = cosine_similarity(query_embedding, self.policy_embeddings)[0]
            
            # 3단계: 상위 후보 선택 (더 많이 선택해서 규칙 기반 필터링)
            top_indices = np.argsort(similarities)[::-1][:top_k * 3]
            
            # 4단계: 후보 정책들에 대해 규칙 기반 검증
            candidates = []
            for idx in top_indices:
                policy = self.policies[idx]
                eligibility = self.check_eligibility(user_profile, policy)
                
                candidates.append({
                    'policy': policy,
                    'semantic_score': similarities[idx],
                    'eligibility': eligibility,
                    'combined_score': self.calculate_combined_score(
                        similarities[idx], eligibility
                    )
                })
            
            # 5단계: 종합 점수로 재정렬
            candidates.sort(key=lambda x: x['combined_score'], reverse=True)
            
            # 6단계: 상위 결과만 반환
            final_results = []
            for candidate in candidates[:top_k]:
                policy = candidate['policy'].copy()
                policy['_match_info'] = {
                    'semantic_score': round(candidate['semantic_score'], 3),
                    'eligibility_score': round(candidate['eligibility']['confidence'], 3),
                    'eligible': candidate['eligibility']['eligible']
                }
                final_results.append(policy)
            
            return final_results
            
        except Exception as e:
            print(f"의미적 검색 오류: {e}")
            return self.fallback_to_keyword_search(query)
        
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