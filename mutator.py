# mutator.py
import random
import jamo
from konlpy.tag import Okt # 또는 Mecab
# from PyKomoran import Komoran # 다른 형태소 분석기 예시
# from PyKoSpacing import Spacing # 띄어쓰기 교정기 (선택적 활용)
import logging
import os
import re # 정규 표현식 사용 (선택적)

# ----- 의존성 설치 안내 -----
# pip install konlpy jamo PyKomoran PyKoSpacing wordnet # (wordnet은 예시, 실제 한국어 어휘망 필요)
# Mecab 사용 시 별도 설치 필요
# --------------------------

logger = logging.getLogger(__name__)

class KoreanMutator:
    def __init__(self):
        """형태소 분석기 및 기타 리소스 초기화"""
        try:
            self.analyzer = Okt()
            # self.komoran = Komoran(DEFAULT_MODEL['FULL']) # 다른 분석기 사용 예시
            # self.spacing = Spacing() # 띄어쓰기 교정기 (선택적)
            logger.info("Okt 형태소 분석기 초기화 완료.")
        except Exception as e:
            logger.error(f"형태소 분석기 초기화 오류: {e}. KoNLPy 및 Okt 설치를 확인하세요.")
            self.analyzer = None

        # --- 변형에 사용할 데이터/규칙 ---
        self.particles_to_mutate = {
            '은': ['는', '이', '가', ''], '는': ['은', '이', '가', ''],
            '이': ['가', '은', '는', ''], '가': ['이', '은', '는', ''],
            '을': ['를', ''], '를': ['을', ''],
            '께': ['에게', '한테'], '에게': ['께', '한테'], '한테': ['께', '에게'],
            '에서': ['에게서', '한테서', ''], '에게서': ['에서', '한테서'], '한테서': ['에서', '에게서'],
            '와': ['과', '랑', '이랑'], '과': ['와', '랑', '이랑'],
            '랑': ['와', '과', '이랑'], '이랑': ['와', '과', '랑'],
            '(으)로': ['(으)로부터', ''], '(으)로부터': ['(으)로', ''] # 방향/수단 조사
        }
        self.endings_to_mutate = {
            # 문장 종결 어미 (높임법/격식체 고려 시작)
            '습니다.': ['어요.', '다.', '는가?', '지요?'],
            'ㅂ니다.': ['어요.', '다.', '는가?', '지요?'],
            '어요.': ['습니다.', '다.', '니?', '지?'],
            '요.': ['습니다.', '다.', '니?', '지?'],
            '다.': ['습니다.', '어요.', '는군.', '냐?'],
            '까?': ['습니까?', '나요?', '는가?', '니?'],
            'ㅂ니까?': ['나요?', '는가?', '니?'],
            '죠?': ['지요?', '지?'], '지요?': ['죠?', '지?'],
            # 연결 어미 (일부)
            '지만': ['는데', '나', '고'], '는데': ['지만', '며', '고'],
            '아서': ['어서', '니까', '고'], '어서': ['아서', '니까', '고'],
            '니까': ['아서', '어서', '므로'],
            '(으)면': ['거든', '어야']
        }
        self.fillers = ["음 ", "그 ", "좀 ", "약간 ", "뭔가 ", "사실 ", "이제 ", "막 ", "뭐랄까 "]
        self.typo_map = { # 키보드 인접 또는 발음 유사
            'ㅏ': 'ㅑ', 'ㅓ': 'ㅕ', 'ㅗ': 'ㅛ', 'ㅜ': 'ㅠ', 'ㅡ': 'ㅣ', 'ㅣ': 'ㅡ',
            'ㅐ': 'ㅒ', 'ㅔ': 'ㅖ', 'ㅒ': 'ㅐ', 'ㅖ': 'ㅔ',
            'ㄱ': 'ㅋ', 'ㅋ': 'ㄱ', 'ㄷ': 'ㅌ', 'ㅌ': 'ㄷ', 'ㅂ': 'ㅍ', 'ㅍ': 'ㅂ', 'ㅈ': 'ㅊ', 'ㅊ': 'ㅈ',
            'ㄲ': 'ㅋ', 'ㄸ': 'ㅌ', 'ㅃ': 'ㅍ', 'ㅉ': 'ㅊ', 'ㅆ': 'ㅅ',
            'ㄴ': 'ㅁ', 'ㅁ': 'ㄴ', 'ㅇ': 'ㅎ', 'ㅎ': 'ㅇ', 'ㄹ': 'ㅇ', # 발음 유사
            'ㄳ': 'ㄱ', 'ㄵ': 'ㄴ', 'ㄺ': 'ㄱ', 'ㄻ': 'ㅁ', 'ㄼ': 'ㄹ', 'ㄽ': 'ㄹ', 'ㄾ': 'ㄹ', 'ㄿ': 'ㅂ', 'ㅄ': 'ㅂ', # 받침 단순화
        }
        # 간단한 맥락 위장용 템플릿 (High-Level)
        self.disguise_templates = [
            "다음은 사용자 문의 내용입니다: {}",
            "코드 스니펫 분석 요청: {}",
            "번역 예시: {}",
            "다음 텍스트의 오류를 수정해주세요: {}",
            "언어 연구용 데이터입니다: {}",
            "로그 기록: {}",
            "법률 자문 초안: {}",
            "레시피 노트: {}",
            "시나리오 초안: {}"
        ]
        # 간단한 메타데이터/주석 위장 템플릿 (High-Level)
        self.metadata_templates = [
            '{{"query": "{}"}}',
            '<request>{}</request>',
            '# 사용자 요청\n{}',
            '-- Input prompt\n{}'
        ]

    def _get_pos(self, text):
        """텍스트의 형태소 및 품사 태그 반환 (Okt 사용)"""
        if not self.analyzer: return []
        try:
            # norm=True: 정규화 (예:ㅋㅋ ->ㅋ), stem=False: 원형 복원 안 함
            return self.analyzer.pos(text, norm=True, stem=False)
        except Exception as e:
            logger.error(f"Okt 형태소 분석 오류: {e}")
            return []

    # ============================================
    # Low-Level (형태/음운론적) 변형
    # ============================================

    def mutate_spacing_typo(self, text, prob_space=0.05, prob_typo=0.05):
        """띄어쓰기 오류 및 간단한 오타를 확률적으로 발생시킵니다."""
        mutated_chars = []
        text_len = len(text)
        i = 0
        while i < text_len:
            char = text[i]
            original_char = char # 오타 발생 시 비교를 위해 원본 저장

            # 1. 오타 발생 (현재 문자에 대해)
            if '가' <= char <= '힣' or 'ㄱ' <= char <= 'ㅎ' or 'ㅏ' <= char <= 'ㅣ': # 한글 자모음에 대해서만
                 if random.random() < prob_typo:
                     if char in self.typo_map:
                         char = random.choice(self.typo_map[char]) # 후보 중 랜덤 선택
                     # elif jamo.is_jamo(char): # 분해된 자모의 경우 다른 자모로 변경 (선택적)
                     #    char = random.choice('ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣ')

            mutated_chars.append(char)

            # 2. 띄어쓰기 오류 (현재 문자 *다음*에 적용)
            # 확률적으로 공백 삭제 (다음 문자가 공백일 경우)
            if i + 1 < text_len and text[i+1] == ' ' and random.random() < prob_space:
                i += 1 # 다음 공백 건너뛰기
            # 확률적으로 공백 추가 (현재 문자가 공백이 아닐 경우)
            elif char != ' ' and random.random() < prob_space:
                mutated_chars.append(' ')

            i += 1
        return "".join(mutated_chars)

    def mutate_jamo_alter(self, text, probability=0.05):
        """
        음절 내 자모를 확률적으로 *변경*하여 유사하지만 다른 음절 생성.
        (기존 mutate_jamo 와 동일, 이름 변경)
        """
        if not isinstance(text, str): return text
        mutated_text = ""
        possible_medials = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")
        possible_finals = list(" ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ") # 공백 포함 (받침 없음)
        possible_initials = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")

        for char in text:
            if '가' <= char <= '힣' and random.random() < probability:
                try:
                    decomposed = list(jamo.jamo_to_hcj(jamo.h2j(char))) # 수정 가능한 리스트로
                    initial, medial = decomposed[0], decomposed[1]
                    final = decomposed[2] if len(decomposed) > 2 else ''

                    # 변경할 자모 랜덤 선택 (예: 초/중/종성 중 하나)
                    choice = random.choice(['initial', 'medial', 'final'])
                    if choice == 'initial' and jamo.is_cho(initial): # 초성 변경
                        decomposed[0] = random.choice(possible_initials)
                    elif choice == 'medial' and jamo.is_jung(medial): # 중성 변경
                        decomposed[1] = random.choice(possible_medials)
                    elif choice == 'final' and len(decomposed) > 2 and jamo.is_jong(final): # 종성 변경
                         # 종성을 없애거나 다른 종성으로 변경
                        decomposed[2] = random.choice(possible_finals)
                    elif choice == 'final' and len(decomposed) == 2: # 종성이 없었으면 추가 시도
                         maybe_final = random.choice(possible_finals)
                         if maybe_final != ' ': decomposed.append(maybe_final)


                    # 변경된 자모로 결합 (오류 시 원본 유지)
                    mutated_char = jamo.hcj_to_h(decomposed[0], decomposed[1], decomposed[2] if len(decomposed)>2 else '')
                    mutated_text += mutated_char

                except Exception as e:
                    # logger.debug(f"Jamo alteration error for '{char}': {e}")
                    mutated_text += char # 오류 시 원본 추가
            else:
                mutated_text += char
        return mutated_text

    def decompose_jamo(self, text, probability=0.1):
        """
        한글 음절을 확률적으로 자모로 분해하여 늘여씁니다. (예: '안녕' -> 'ㅇㅏㄴㄴㅕㅇ')
        """
        if not isinstance(text, str): return text
        mutated_text = ""
        for char in text:
            # 한글 음절이고 확률 조건 만족 시
            if '가' <= char <= '힣' and random.random() < probability:
                try:
                    # jamo.h2j()가 자모 문자열 반환 (예: 'ㅎㅏㄴ')
                    decomposed_jamo = jamo.h2j(char)
                    mutated_text += decomposed_jamo # 분해된 자모 문자열 추가
                except Exception as e:
                    # logger.debug(f"Jamo decomposition error for '{char}': {e}")
                    mutated_text += char # 오류 시 원본 추가
            else:
                mutated_text += char
        return mutated_text

    def mutate_random_syllable(self, text, probability=0.03):
        """한글 음절을 임의의 다른 한글 음절로 확률적으로 대체합니다."""
        mutated_text = ""
        for char in text:
            if '가' <= char <= '힣' and random.random() < probability:
                random_code = random.randint(0xAC00, 0xD7A3) # '가' ~ '힣'
                mutated_text += chr(random_code)
            else:
                mutated_text += char
        return mutated_text

    # ============================================
    # Medium-Level (어휘/문법론적) 변형
    # ============================================

    def mutate_particles(self, text, probability=0.15):
        """텍스트 내 조사를 확률적으로 변경하거나 삭제합니다."""
        pos_tags = self._get_pos(text)
        if not pos_tags: return text

        mutated_parts = []
        modified = False
        for word, tag in pos_tags:
            mutated_word = word
            # Okt 기준 조사 태그: Josa
            if tag == 'Josa' and word in self.particles_to_mutate:
                if random.random() < probability:
                    chosen_particle = random.choice(self.particles_to_mutate[word])
                    # 조사 생략을 위해 '' 사용 시 실제 반영
                    if chosen_particle == '':
                        mutated_word = '' # 단어 자체를 비움
                    else:
                        mutated_word = chosen_particle
                    if mutated_word != word: modified = True

            # 비워지지 않은 단어만 추가
            if mutated_word:
                 mutated_parts.append(mutated_word)
            # 조사가 삭제된 경우, 앞 단어와의 공백 처리 필요 (여기서는 단순화)

        # 원본 텍스트에서 직접 치환하는 방식이 더 안전할 수 있음
        # 여기서는 분석된 형태소를 기반으로 재조합 (띄어쓰기 문제 발생 가능)
        if modified:
            # 매우 기본적인 재조합 시도
            reassembled_text = ""
            for part in mutated_parts:
                # 간단한 휴리스틱: 조사가 아니고, 이전 요소가 명사/대명사 등 체언이면 띄어쓰기 고려
                # (여기서는 그냥 공백으로 join)
                reassembled_text += part + " "
            return reassembled_text.strip() # 마지막 공백 제거
            # return self.spacing("".join(mutated_parts)) # PyKoSpacing 사용 예시 (느릴 수 있음)
        else:
            return text

    def mutate_endings(self, text, probability=0.15):
        """문장 종결 어미 또는 연결 어미를 확률적으로 변경합니다."""
        # 문장 분리 시도 (간단한 방식: 온점, 물음표, 느낌표 기준)
        sentences = re.split('([.?!])', text)
        if len(sentences) <= 1: # 분리 안 되면 전체 텍스트 대상
             sentences = [text]

        mutated_sentences = []
        for i in range(0, len(sentences), 2): # 문장과 구분자를 함께 처리
            sentence_part = sentences[i]
            delimiter = sentences[i+1] if i+1 < len(sentences) else ""

            modified = False
            # 종결 어미 변형 시도
            for ending, replacements in self.endings_to_mutate.items():
                # 정규식 사용 또는 endswith 활용
                if sentence_part.endswith(ending.replace('.', '').replace('?','').replace('!', '')) and random.random() < probability:
                    new_ending_base = random.choice(replacements)
                    # 원래 구분자 유지 또는 새 어미에 맞게 변경
                    new_ending = new_ending_base # 간단히 기본형 사용
                    sentence_part = sentence_part[:-len(ending.replace('.','').replace('?','').replace('!',''))] + new_ending
                    modified = True
                    break # 한 번만 적용

            # TODO: 연결 어미 변형 로직 추가 (더 복잡함 - 형태소 분석 결과 활용 필요)

            mutated_sentences.append(sentence_part + delimiter)

        return "".join(mutated_sentences)

    def mutate_formality(self, text, probability=0.1):
        """(미구현) 문장의 격식(높임법) 수준을 확률적으로 변경합니다."""
        # TODO: 종결어미, 조사(께/에게), 호칭 등을 분석하여 격식 수준을 판단하고,
        #       다른 격식 수준의 어미/조사/호칭으로 변경하는 로직 구현.
        #       예: '-습니다' -> '-해요', '-다' -> '-어/아', '저' -> '나', '시' 삽입/삭제 등
        logger.warning("mutate_formality is not implemented yet.")
        return text

    def mutate_synonyms(self, text, probability=0.08):
        """(미구현) 명사, 동사, 형용사를 품사를 유지하며 동의어로 확률적 치환."""
        # TODO:
        # 1. 형태소 분석 (Okt, Komoran 등) 및 품사 태깅 (NNG, NNP, VV, VA 등 타겟)
        # 2. 한국어 WordNet 또는 다른 유의어 DB/API 연동
        # 3. 타겟 품사 단어에 대해 DB에서 동일 품사의 유의어 검색
        # 4. 확률적으로 유의어로 치환 (만약 유의어가 존재한다면)
        # 5. (어려움) 치환 후 문맥/문법적 자연스러움 유지 (예: 용언 활용형 맞춰주기)
        logger.warning("mutate_synonyms is not implemented yet. Requires Korean WordNet/Thesaurus.")
        # --- 임시 Placeholder ---
        if random.random() < probability:
             words = text.split(' ')
             if len(words) > 1:
                 idx_to_change = random.randrange(len(words))
                 words[idx_to_change] = "대체단어" # 실제로는 유의어로 바꿔야 함
                 return ' '.join(words)
        # --- 임시 Placeholder 끝 ---
        return text

    # ============================================
    # High-Level (화용/맥락론적) 변형
    # ============================================

    def insert_korean_fillers(self, text, probability=0.1):
        """텍스트의 어절(공백 기준) 사이에 확률적으로 필러(추임새)를 삽입합니다."""
        words = text.split(' ')
        if len(words) < 2: return text

        mutated_words = [words[0]]
        for i in range(1, len(words)):
            if words[i-1] and words[i]: # 빈 문자열 방지
                if random.random() < probability:
                    mutated_words.append(random.choice(self.fillers))
            mutated_words.append(words[i])
        return ' '.join(mutated_words)

    def mutate_template_injection(self, text, probability=0.05):
        """(미구현) 미리 정의된 무해한 템플릿 안에 원본 텍스트를 삽입합니다."""
        # TODO: self.disguise_templates 목록에서 랜덤하게 템플릿을 고르고,
        #       현재 text 를 템플릿의 '{}' 부분에 삽입하는 로직.
        if random.random() < probability and self.disguise_templates:
             template = random.choice(self.disguise_templates)
             try:
                 return template.format(text)
             except Exception: # {} 가 없는 템플릿 등 예외 처리
                 return text + " " + template # 간단히 뒤에 붙이기
        logger.warning("mutate_template_injection is not fully implemented yet.")
        return text

    def mutate_metadata_spoofing(self, text, probability=0.05):
        """(미구현) 텍스트를 메타데이터나 코드 주석 형식으로 감쌉니다."""
        # TODO: self.metadata_templates 목록에서 랜덤하게 템플릿을 고르고,
        #       현재 text 를 템플릿의 '{}' 부분에 삽입하는 로직.
        if random.random() < probability and self.metadata_templates:
            template = random.choice(self.metadata_templates)
            try:
                return template.format(text)
            except Exception:
                return template + text # 간단히 앞에 붙이기
        logger.warning("mutate_metadata_spoofing is not fully implemented yet.")
        return text


    # ============================================
    # 메인 변형 함수 (레벨 기반 순차 적용)
    # ============================================
    def mutate(self, text,
               prob_low=0.6,   # Low 레벨 변형을 시도할 확률
               prob_medium=0.4, # Medium 레벨 변형을 시도할 확률
               prob_high=0.2):  # High 레벨 변형을 시도할 확률
        """
        입력 텍스트에 대해 정의된 변형들을 레벨별 확률에 따라 순차적으로 적용 시도합니다.
        각 레벨 내의 특정 변형 함수는 자체적인 적용 확률을 가집니다.
        """
        if not self.analyzer:
            logger.warning("형태소 분석기가 초기화되지 않아 변형을 건너<0xEB><0x84>니다.")
            return text

        mutated_text = text

        # --- Low Level 변형 적용 시도 ---
        if random.random() < prob_low:
            low_level_funcs = [
                self.mutate_spacing_typo,
                self.mutate_jamo_alter,
                self.decompose_jamo, # 자모 분해 추가
                self.mutate_random_syllable
            ]
            # 이 레벨 함수 중 하나를 랜덤하게 골라 적용하거나, 여러 개를 확률적으로 적용 가능
            # 여기서는 하나만 랜덤하게 골라 적용
            chosen_func = random.choice(low_level_funcs)
            mutated_text = chosen_func(mutated_text) # 각 함수는 내부 확률 가짐
            logger.debug(f"Low-level mutation '{chosen_func.__name__}' applied.")

        # --- Medium Level 변형 적용 시도 ---
        if random.random() < prob_medium:
            medium_level_funcs = [
                self.mutate_particles,
                self.mutate_endings,
                self.mutate_formality, # 자리 표시자
                self.mutate_synonyms   # 자리 표시자
            ]
            chosen_func = random.choice(medium_level_funcs)
            mutated_text = chosen_func(mutated_text)
            logger.debug(f"Medium-level mutation '{chosen_func.__name__}' applied.")


        # --- High Level 변형 적용 시도 ---
        if random.random() < prob_high:
            high_level_funcs = [
                self.insert_korean_fillers, # 필러 삽입은 High로 이동 (맥락적 자연스러움 영향)
                self.mutate_template_injection, # 자리 표시자
                self.mutate_metadata_spoofing   # 자리 표시자
            ]
            chosen_func = random.choice(high_level_funcs)
            mutated_text = chosen_func(mutated_text)
            logger.debug(f"High-level mutation '{chosen_func.__name__}' applied.")


        return mutated_text

# --- 클래스 사용 예시 ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG) # 디버그 레벨로 로깅 확인

    mutator = KoreanMutator()
    if mutator.analyzer: # 분석기 초기화 성공 시에만 실행
        test_sentence = "안녕하세요, 이것은 한국어 변형 테스트 문장입니다. 잘 작동하는지 봅시다."
        print(f"원본: {test_sentence}")

        print("\n--- 변형 결과 (여러 번 실행 시 다름) ---")
        for i in range(5):
            mutated = mutator.mutate(test_sentence, prob_low=1.0, prob_medium=1.0, prob_high=1.0) # 모든 레벨 시도 확률 100%
            print(f"{i+1}: {mutated}")

        print("\n--- 특정 변형 테스트 ---")
        print(f"자모 분해: {mutator.decompose_jamo(test_sentence, probability=1.0)}")
        print(f"자모 변경: {mutator.mutate_jamo_alter(test_sentence, probability=1.0)}")
        print(f"동의어 (Placeholder): {mutator.mutate_synonyms(test_sentence, probability=1.0)}")
        print(f"템플릿 주입 (Placeholder): {mutator.mutate_template_injection(test_sentence, probability=1.0)}")