# mutator.py (수정 버전)
import random
import unicodedata # 난독화 위해 추가
import logging
import re
import os
import pickle
import traceback

# 'jamo' 라이브러리 시도 및 확인
try:
    import jamo
    JAMO_AVAILABLE = True
except ImportError:
    JAMO_AVAILABLE = False
    print("경고: 'jamo' 라이브러리를 찾을 수 없습니다. 일부 자모 관련 기능이 제한됩니다.")
    print("설치 명령어: pip install jamo")

# konlpy 임포트 시도 및 확인
try:
    from konlpy.tag import Okt
    KONLPY_AVAILABLE = True
except ImportError:
    KONLPY_AVAILABLE = False
    print("경고: 'konlpy' 라이브러리를 찾을 수 없습니다. 형태소 분석 기반 변형이 제한됩니다.")
    print("설치 명령어: pip install konlpy") # 또는 JPype1, JDK 설치 필요 명시

import config  # config 임포트

logger = logging.getLogger(__name__)


class KoreanMutator:
    """
    한국어 텍스트에 다양한 변형(Mutation/Obfuscation)을 적용하는 클래스.
    Low, Medium, High 레벨 및 난독화 기법을 포함.
    """

    # --- 클래스 변수로 설정값 정의 ---
    # 유사 문자 (Homoglyphs)
    KOR_TO_HOMOGLYPHS = {
        'ㅇ': ['o', 'O', '0'], 'ㄷ': ['c', 'C', 'ᄃ'], 'ㅈ': ['z', 'Z', 'ᄌ'],
        'ㅂ': ['u', 'U', 'b', 'B', 'ᄇ'], 'ㅁ': ['a', 'A', 'ㅁ'], 'ㄱ': ['r', '7', 'ㄱ'],
        'ㄴ': ['L', 'ㄴ'], 'ㅅ': ['人', '^', 'ㅅ'], 'ㅎ': ['ō', 'ㅎ'], 'ㅣ': ['l', 'I', '1', '|', 'ᅵ'],
        'ㅡ': ['-', '_', 'ᅳ'], 'ㅗ': ['ㅗ'], 'ㅜ': ['ㅜ'],
    }
    # 보이지 않는 문자 (Invisible Characters)
    INVISIBLE_CHARS = [
        '\u200B', '\u200C', '\u200D', '\uFEFF', '\u180E',
    ]
    # 전각 문자 (Full-width Characters)
    ASCII_TO_FULLWIDTH = {chr(i): chr(i + 0xFEE0) for i in range(33, 127)}
    ASCII_TO_FULLWIDTH[' '] = '\u3000' # 전각 공백

    # 기타 변형 규칙 (기존 코드에서 가져옴)
    particles_to_mutate = {
        '은': ['는', '이', '가', ''], '는': ['은', '이', '가', ''], '이': ['가', '은', '는', ''], '가': ['이', '은', '는', ''],
        '을': ['를', ''], '를': ['을', ''], '께': ['에게', '한테'], '에게': ['께', '한테'], '한테': ['께', '에게'],
        '에서': ['에게서', '한테서', ''], '에게서': ['에서', '한테서'], '한테서': ['에서', '에게서'],
        '와': ['과', '랑', '이랑'], '과': ['와', '랑', '이랑'], '랑': ['와', '과', '이랑'], '이랑': ['와', '과', '랑'],
        '(으)로': ['(으)로부터', ''], '(으)로부터': ['(으)로', '']
    }
    endings_to_mutate = {
        '습니다.': ['어요.', '다.', '는가?', '지요?'], 'ㅂ니다.': ['어요.', '다.', '는가?', '지요?'],
        '어요.': ['습니다.', '다.', '니?', '지?'], '요.': ['습니다.', '다.', '니?', '지?'],
        '다.': ['습니다.', '어요.', '는군.', '냐?'], '까?': ['습니까?', '나요?', '는가?', '니?'],
        'ㅂ니까?': ['나요?', '는가?', '니?'], '죠?': ['지요?', '지?'], '지요?': ['죠?', '지?'],
        '지만': ['는데', '나', '고'], '는데': ['지만', '며', '고'], '아서': ['어서', '니까', '고'],
        '어서': ['아서', '니까', '고'], '니까': ['아서', '어서', '므로'], '(으)면': ['거든', '어야']
    }
    fillers = ["음 ", "그 ", "좀 ", "약간 ", "뭔가 ", "사실 ", "이제 ", "막 ", "뭐랄까 "]
    typo_map = {
        'ㅏ': 'ㅑ', 'ㅓ': 'ㅕ', 'ㅗ': 'ㅛ', 'ㅜ': 'ㅠ', 'ㅡ': 'ㅣ', 'ㅣ': 'ㅡ', 'ㅐ': 'ㅒ', 'ㅔ': 'ㅖ', 'ㅒ': 'ㅐ', 'ㅖ': 'ㅔ',
        'ㄱ': 'ㅋ', 'ㅋ': 'ㄱ', 'ㄷ': 'ㅌ', 'ㅌ': 'ㄷ', 'ㅂ': 'ㅍ', 'ㅍ': 'ㅂ', 'ㅈ': 'ㅊ', 'ㅊ': 'ㅈ', 'ㄲ': 'ㅋ', 'ㄸ': 'ㅌ',
        'ㅃ': 'ㅍ', 'ㅉ': 'ㅊ', 'ㅆ': 'ㅅ', 'ㄴ': 'ㅁ', 'ㅁ': 'ㄴ', 'ㅇ': 'ㅎ', 'ㅎ': 'ㅇ', 'ㄹ': 'ㅇ', 'ㄳ': 'ㄱ', 'ㄵ': 'ㄴ',
        'ㄺ': 'ㄱ', 'ㄻ': 'ㅁ', 'ㄼ': 'ㄹ', 'ㄽ': 'ㄹ', 'ㄾ': 'ㄹ', 'ㄿ': 'ㅂ', 'ㅄ': 'ㅂ',
    }
    similar_initials = {
        'ㄱ': ['ㅋ', 'ㄲ'], 'ㅋ': ['ㄱ', 'ㄲ'], 'ㄲ': ['ㄱ', 'ㅋ'],
        'ㄷ': ['ㅌ', 'ㄸ', 'ㄴ', 'ㅅ', 'ㅈ'], 'ㅌ': ['ㄷ', 'ㄸ', 'ㅊ'], 'ㄸ': ['ㄷ', 'ㅌ'],
        'ㅂ': ['ㅍ', 'ㅃ', 'ㅁ'], 'ㅍ': ['ㅂ', 'ㅃ'], 'ㅃ': ['ㅂ', 'ㅍ'],
        'ㅅ': ['ㅆ', 'ㄷ', 'ㅈ'], 'ㅆ': ['ㅅ', 'ㅊ'],
        'ㅈ': ['ㅊ', 'ㅉ', 'ㄷ', 'ㅅ'], 'ㅊ': ['ㅈ', 'ㅉ', 'ㅌ', 'ㅆ'], 'ㅉ': ['ㅈ', 'ㅊ'],
        'ㄴ': ['ㄷ', 'ㅁ', 'ㄹ'], 'ㄹ': ['ㄴ', 'ㅇ'], 'ㅁ': ['ㅂ', 'ㄴ'], 'ㅇ': ['ㅎ', 'ㄹ'], 'ㅎ': ['ㅇ']
    }
    similar_medials = {
        'ㅏ': ['ㅑ', 'ㅐ', 'ㅓ'], 'ㅑ': ['ㅏ', 'ㅕ', 'ㅒ'], 'ㅐ': ['ㅒ', 'ㅏ', 'ㅔ'], 'ㅒ': ['ㅐ', 'ㅑ'],
        'ㅓ': ['ㅕ', 'ㅔ', 'ㅏ'], 'ㅕ': ['ㅓ', 'ㅑ', 'ㅖ'], 'ㅔ': ['ㅖ', 'ㅓ', 'ㅐ'], 'ㅖ': ['ㅔ', 'ㅕ'],
        'ㅗ': ['ㅛ', 'ㅜ', 'ㅚ', 'ㅘ'], 'ㅛ': ['ㅗ', 'ㅠ'], 'ㅜ': ['ㅠ', 'ㅗ', 'ㅡ', 'ㅝ'], 'ㅠ': ['ㅜ', 'ㅛ'],
        'ㅡ': ['ㅜ', 'ㅣ'], 'ㅣ': ['ㅡ', 'ㅐ', 'ㅔ'],
        'ㅘ': ['ㅗ', 'ᅪ'], 'ㅙ': ['ㅐ', 'ㅞ'], 'ㅚ': ['ㅗ', 'ㅣ', 'ㅙ', 'ㅞ'], 'ㅝ': ['ㅜ', 'ㅓ', 'ㅞ'],
        'ㅞ': ['ㅔ', 'ㅜ', 'ㅝ', 'ㅙ'], 'ㅟ': ['ㅜ', 'ㅣ'], 'ㅢ': ['ㅡ', 'ㅣ']
    }
    similar_finals = {
        'ㄱ': ['ㅋ', 'ㄲ', 'ㄳ', 'ㄺ'], 'ㅋ': ['ㄱ', 'ㄲ'], 'ㄲ': ['ㄱ', 'ㅋ'], 'ㄳ': ['ㄱ', 'ㅅ'],
        'ㄴ': ['ㄵ', 'ㄶ', 'ㄷ', 'ㅁ'], 'ㄵ': ['ㄴ', 'ㅈ'], 'ㄶ': ['ㄴ', 'ㅎ'],
        'ㄷ': ['ㅌ', 'ㅅ', 'ㅆ', 'ㅈ', 'ㅊ', 'ㅎ'], 'ㅌ': ['ㄷ', 'ㅊ'],
        'ㄹ': ['ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㄴ'], 'ㄺ': ['ㄱ', 'ㄹ'], 'ㄻ': ['ㄹ', 'ㅁ'],
        'ㅁ': ['ㄻ', 'ㄴ'], 'ㅂ': ['ㅍ', 'ㄿ', 'ㅄ'], 'ㅍ': ['ㅂ'], 'ㅄ': ['ㅂ', 'ㅅ'],
        'ㅅ': ['ㅆ', 'ㄷ', 'ㅈ', 'ㅊ', 'ㅌ', 'ㅎ'], 'ㅆ': ['ㅅ', 'ㄷ'], 'ㅇ': [],
        'ㅈ': ['ㅊ', 'ㄷ', 'ㅅ'], 'ㅊ': ['ㅈ', 'ㅌ', 'ㅎ'], 'ㅌ': ['ㄷ', 'ㅊ', 'ㅅ'], 'ㅎ': ['ㄶ', 'ㅀ', 'ㄷ']
    }
    finals_for_addition = list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ") # 'ㅇ' 제외? 필요시 포함


    def __init__(self):
        """형태소 분석기 초기화"""
        self.analyzer = None
        if KONLPY_AVAILABLE:
            try:
                self.analyzer = Okt()
                logger.info("Okt 형태소 분석기 초기화 완료.")
            except Exception as e:
                logger.error(f"Okt 형태소 분석기 초기화 오류: {e}. 형태소 기반 변형 비활성화.")
        else:
             logger.warning("Konlpy/Okt 미설치. 형태소 기반 변형 비활성화.")

        # ★★★ 유의어 사전 로드 ★★★
        self.korean_thesaurus = self.load_korean_thesaurus()

        # --- 변형 함수 목록 정의 ---
        self.low_level_funcs = [
            self.mutate_spacing_typo,
            self.mutate_jamo_alter,
            self.decompose_jamo,
            # === 새로운 난독화 함수 추가 ===
            self.apply_homoglyphs,
            self.insert_invisible_chars,
            self.apply_fullwidth,
            self.mix_scripts_randomly,
            self.mutate_syllable_order
        ]
        self.medium_level_funcs = [
            self.mutate_particles,
            self.mutate_endings,
            self.mutate_synonyms,
            self.mutate_word_order
        ]
        self.high_level_funcs = [
            self.insert_korean_fillers,
        ]

    def load_korean_thesaurus(self):
        """전처리된 유의어 사전 파일(.pkl)을 로드합니다."""
        thesaurus_path = getattr(
            config, 'THESAURUS_PATH', 'korean_thesaurus.pkl')
        if os.path.exists(thesaurus_path):
            try:
                with open(thesaurus_path, 'rb') as f:
                    thesaurus_data = pickle.load(f)
                logger.info(
                    f"유의어 사전 로드 완료: {thesaurus_path} ({len(thesaurus_data)} 단어)")
                return thesaurus_data
            except Exception as e:
                logger.error(f"유의어 사전 로드 실패 ({thesaurus_path}): {e}")
                return {}  # 로드 실패 시 빈 딕셔너리 반환
        else:
            logger.warning(
                f"유의어 사전 파일을 찾을 수 없습니다: {thesaurus_path}. 유의어 변형 비활성화.")
            return {}  # 파일 없으면 빈 딕셔너리 반환

    def get_related_words(self, word, pos_tag):
        """
        통합 사전에서 주어진 단어/품사에 대한 관련 단어(유의어, 상위어, 하위어) 리스트를 반환합니다.
        """
        related_words = set() # 중복 제거용 세트
        if not self.korean_thesaurus:
            return []

        # 사전 구조: thesaurus[word][pos_tag] = {'synonyms': [], 'hypernym': str|None, 'hyponyms': []}
        if word in self.korean_thesaurus and pos_tag in self.korean_thesaurus[word]:
            entry = self.korean_thesaurus[word][pos_tag]

            # 1. 유의어 추가 (synonyms 키 확인)
            synonyms = entry.get('synonyms')
            if synonyms and isinstance(synonyms, (list, set)):
                related_words.update(s for s in synonyms if isinstance(s, str)) # 문자열만 추가

            # 2. 상위어 추가 (hypernym 키 확인)
            hypernym = entry.get('hypernym')
            if hypernym and isinstance(hypernym, str):
                related_words.add(hypernym)

            # 3. 하위어 추가 (hyponyms 키 확인)
            hyponyms = entry.get('hyponyms')
            if hyponyms and isinstance(hyponyms, (list, set)):
                related_words.update(h for h in hyponyms if isinstance(h, str)) # 문자열만 추가

        # 원본 단어는 치환 대상에서 제외
        related_words.discard(word)

        # 최종적으로 리스트로 변환하여 반환
        return list(related_words)
        
    def _get_pos(self, text):
        """텍스트의 형태소 및 품사 태그 반환 (Okt 사용)"""
        if not self.analyzer:
            return []
        try:
            # norm=True 옵션은 '사랑햌ㅋㅋ' -> '사랑하다ㅋㅋ' 와 같이 정규화
            # stem=False 옵션은 '그렇다' -> '그렇다' (원형 복원 안함)
            return self.analyzer.pos(text, norm=True, stem=False)
        except Exception as e:
            logger.error(f"Okt 형태소 분석 오류: {e}")
            return []

    # --- 기존 Low-Level 변형 함수들 (mutate_random_syllable 제외) ---
    # ★★★★★ 신규 변형 함수 1: 단어 순서 변경 ★★★★★
    def mutate_word_order(self, text, probability=config.DEFAULT_PROB_WORD_ORDER):
        """문장 내 인접한 단어의 순서를 확률적으로 변경합니다."""
        if not isinstance(text, str) or len(text.strip()) == 0:
            return text

        # 간단하게 공백 기준으로 단어 분리 (더 정교하게 하려면 형태소 분석기 사용 가능)
        words = text.split(' ')
        if len(words) < 2:  # 단어가 2개 미만이면 순서 변경 불가
            return text

        mutated_words = list(words)  # 수정 가능한 리스트로 복사
        num_swapped = 0

        for i in range(len(mutated_words) - 1):
            # 현재 단어와 다음 단어 모두 비어있지 않을 때만 시도
            if mutated_words[i] and mutated_words[i+1] and random.random() < probability:
                # 인접한 두 단어의 순서를 바꿈
                mutated_words[i], mutated_words[i +
                                                1] = mutated_words[i+1], mutated_words[i]
                num_swapped += 1
                # 한 번 바꾼 후에는 다음 인덱스로 건너뛰어 중복 스왑 방지 (선택적)
                # i += 1 # 이 줄을 활성화하면 연속된 스왑은 일어나지 않음

        if num_swapped > 0:
            logger.debug(
                f"Word order mutation applied: swapped {num_swapped} pairs.")
            return ' '.join(mutated_words)  # 재조합
        else:
            return text  # 변경 없으면 원본 반환

    # ★★★★★ 신규 변형 함수 2: 음절 순서 변경 ★★★★★
    def mutate_syllable_order(self, text, probability=config.DEFAULT_PROB_SYLLABLE_ORDER):
        """단어 내 음절(글자)의 순서를 확률적으로 섞습니다."""
        if not isinstance(text, str) or len(text.strip()) == 0:
            return text

        words = text.split(' ')
        mutated_words = []
        modified = False

        for word in words:
            if not word:  # 빈 문자열은 그대로 추가
                mutated_words.append(word)
                continue

            # 단어 내 모든 글자가 한글 음절 범위인지 확인 (간단한 체크)
            is_korean_word = all('가' <= char <= '힣' for char in word)

            if is_korean_word and len(word) > 1 and random.random() < probability:
                syllables = list(word)  # 단어를 글자(음절) 리스트로 변환
                random.shuffle(syllables)  # 음절 순서 섞기
                mutated_word = "".join(syllables)
                if mutated_word != word:
                    mutated_words.append(mutated_word)
                    modified = True
                    logger.debug(
                        f"Syllable order mutation applied: '{word}' -> '{mutated_word}'")
                else:
                    mutated_words.append(word)  # 섞었지만 결과가 같으면 원본 추가
            else:
                mutated_words.append(word)  # 한글 단어가 아니거나 확률 미달 시 원본 추가

        if modified:
            return ' '.join(mutated_words)
        else:
            return text
        
    def mutate_spacing_typo(self, text, prob_space=config.DEFAULT_PROB_SPACING, prob_typo=config.DEFAULT_PROB_TYPO):
        """띄어쓰기 오류 및 간단한 오타를 확률적으로 발생시킵니다."""
        mutated_chars = []
        text_len = len(text)
        i = 0
        while i < text_len:
            char = text[i]
            # 오타 적용
            if '가' <= char <= '힣' or 'ㄱ' <= char <= 'ㅎ' or 'ㅏ' <= char <= 'ㅣ':
                if random.random() < prob_typo and char in self.typo_map:
                    # typo_map 값 처리 (문자열 또는 리스트 가능)
                    replacement_options = self.typo_map[char]
                    if isinstance(replacement_options, str) and len(replacement_options) > 0:
                        char = random.choice(replacement_options)
                    elif isinstance(replacement_options, list) and replacement_options:
                        char = random.choice(replacement_options)
                    # else: char 유지 (매핑 값 없거나 비어있으면)

            mutated_chars.append(char)

            # 띄어쓰기 오류 적용
            # 1. 다음 문자가 공백인데 확률적으로 붙이기
            if i + 1 < text_len and text[i+1] == ' ' and random.random() < prob_space:
                # mutated_chars.append(char) # 현재 문자 추가
                i += 1 # 다음 공백 건너뛰기
            # 2. 현재 문자가 공백이 아닌데 확률적으로 공백 추가
            elif char != ' ' and random.random() < prob_space:
                 mutated_chars.append(' ')

            i += 1
        return "".join(mutated_chars)

    def mutate_jamo_alter(self, text, probability=config.DEFAULT_PROB_JAMO_ALTER):
        """음절 내 자모를 확률적으로 *유사한* 자모로 변경 (오타와 유사하지만 더 의미론적)"""
        if not JAMO_AVAILABLE or not isinstance(text, str):
            return text
        mutated_text = ""
        for char in text:
            if '가' <= char <= '힣' and random.random() < probability:
                try:
                    decomposed = list(jamo.jamo_to_hcj(jamo.h2j(char))) # 초성, 중성, 종성 분리
                    initial, medial = decomposed[0], decomposed[1]
                    final = decomposed[2] if len(decomposed) > 2 else ''
                    mutated = False

                    part_to_mutate = random.choice(['initial', 'medial', 'final'])

                    if part_to_mutate == 'initial' and initial in self.similar_initials and self.similar_initials[initial]:
                        replacement = random.choice(self.similar_initials[initial])
                        if replacement != initial: decomposed[0] = replacement; mutated = True
                    elif part_to_mutate == 'medial' and medial in self.similar_medials and self.similar_medials[medial]:
                        replacement = random.choice(self.similar_medials[medial])
                        if replacement != medial: decomposed[1] = replacement; mutated = True
                    elif part_to_mutate == 'final':
                        if final and final in self.similar_finals: # 기존 종성 변경/삭제
                            if random.random() < 0.3: # 종성 삭제 확률
                                if len(decomposed) > 2: decomposed.pop(); mutated = True
                            elif self.similar_finals[final]: # 유사 종성 변경
                                replacement = random.choice(self.similar_finals[final])
                                if replacement != final: decomposed[2] = replacement; mutated = True
                        elif not final and random.random() < 0.3: # 종성 추가 확률
                            new_final = random.choice(self.finals_for_addition)
                            decomposed.append(new_final); mutated = True

                    if mutated:
                        try:
                            mutated_char = jamo.j2h(decomposed[0], decomposed[1], decomposed[2] if len(decomposed) > 2 else None)
                            mutated_text += mutated_char
                        except (ValueError, KeyError): # 잘못된 조합 예외 처리
                            mutated_text += char # 조합 실패 시 원본 유지
                    else:
                        mutated_text += char # 변경 안됐으면 원본 유지
                except Exception as e:
                    logger.debug(f"Jamo alteration error for '{char}': {e}")
                    mutated_text += char # 오류 시 원본 유지
            else:
                mutated_text += char
        return mutated_text

    def decompose_jamo(self, text, probability=config.DEFAULT_PROB_JAMO_DECOMPOSE):
        """텍스트 내 한글 음절을 자모로 분해합니다."""
        if not JAMO_AVAILABLE or not isinstance(text, str):
            return text
        mutated_text = ""
        for char in text:
            if '가' <= char <= '힣' and random.random() < probability:
                try:
                    mutated_text += jamo.j2hcj(jamo.h2j(char)) # 예: '한' -> 'ㅎㅏㄴ'
                except Exception:
                    mutated_text += char # 오류 시 원본 유지
            else:
                mutated_text += char
        return mutated_text

    # === mutate_random_syllable 함수는 여기서 제거됨 ===

    # --- 새로운 난독화 함수들 (클래스 메소드로 통합) ---
    def apply_homoglyphs(self, text, probability=config.DEFAULT_PROB_HOMOGLYPH):
        """주어진 확률에 따라 텍스트 내 한국어 문자를 유사 문자로 치환합니다."""
        new_text_list = list(text)
        for i, char in enumerate(new_text_list):
            if char in self.KOR_TO_HOMOGLYPHS and random.random() < probability:
                replacement = random.choice(self.KOR_TO_HOMOGLYPHS[char])
                new_text_list[i] = replacement
        return "".join(new_text_list)

    def insert_invisible_chars(self, text, probability=config.DEFAULT_PROB_INVISIBLE):
        """주어진 확률에 따라 텍스트 곳곳에 보이지 않는 문자를 삽입합니다."""
        new_text = ""
        for char in text:
            new_text += char
            if random.random() < probability:
                new_text += random.choice(self.INVISIBLE_CHARS)
        if random.random() < probability * 0.5: # 가끔 시작 부분에도 추가
            new_text = random.choice(self.INVISIBLE_CHARS) + new_text
        return new_text



    def apply_fullwidth(self, text, probability=config.DEFAULT_PROB_FULLWIDTH):
        """주어진 확률에 따라 텍스트 내 ASCII 문자를 전각 문자로 변환합니다."""
        new_text_list = list(text)
        for i, char in enumerate(new_text_list):
            if char in self.ASCII_TO_FULLWIDTH and random.random() < probability:
                new_text_list[i] = self.ASCII_TO_FULLWIDTH[char]
        return "".join(new_text_list)

    def mix_scripts_randomly(self, text, probability=config.DEFAULT_PROB_MIX_SCRIPTS):
         """주어진 확률에 따라 한국어 텍스트 중간에 다른 스크립트 문자를 삽입/치환합니다."""
         new_text_list = list(text)
         # 좀 더 다양한 방해 문자 사용 가능
         distractors = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>/?"
         # 한글 문자 위치만 대상으로 삼도록 수정 가능 (선택적)
         indices_to_modify = [i for i, char in enumerate(text) if '가' <= char <= '힣']

         num_to_modify = int(len(indices_to_modify) * probability)
         # 중복 없이 실제 수정할 인덱스 선택
         indices_chosen = random.sample(indices_to_modify, min(num_to_modify, len(indices_to_modify)))

         for i in indices_chosen:
             # 삽입/치환 액션 랜덤 결정
             action = random.choice(['insert_before', 'insert_after', 'replace'])
             distractor = random.choice(distractors)
             original_char = new_text_list[i] # 원본 문자 저장 (삽입 시 사용)

             if action == 'insert_before':
                 # 문자열 리스트에서는 직접 삽입보다 값 변경이 나음
                 new_text_list[i] = distractor + original_char
             elif action == 'insert_after':
                 new_text_list[i] = original_char + distractor
             else: # replace
                 new_text_list[i] = distractor # 바로 치환

         return "".join(new_text_list) # 최종 문자열로 결합


    # --- 기존 Medium-Level 변형 함수들 ---
    def mutate_particles(self, text, probability=config.DEFAULT_PROB_PARTICLES):
        """텍스트 내 조사를 확률적으로 변경하거나 삭제합니다."""
        if not self.analyzer: return text # 형태소 분석기 없으면 실행 불가
        pos_tags = self._get_pos(text)
        if not pos_tags: return text

        mutated_parts = []
        modified = False
        original_text_index = 0 # 원본 텍스트 인덱스 추적

        for word, tag in pos_tags:
            mutated_word = word
            # 형태소 분석 결과와 원본 텍스트 동기화 시도
            try:
                # 현재 단어가 원본 텍스트의 해당 위치에 있는지 확인
                start_index = text.index(word, original_text_index)
                original_text_index = start_index + len(word) # 다음 검색 시작 위치 업데이트
            except ValueError:
                 # 동기화 실패 (형태소 분석기가 단어를 변경했거나, 중복 단어 문제 등)
                 # 이 경우, 일단 분석된 단어를 그대로 사용하거나, 복잡한 복구 로직 필요
                 logger.debug(f"Particle mutation sync failed for word: {word}")
                 # return text # 동기화 실패 시 안전하게 원본 반환하는 옵션
                 pass # 일단 계속 진행

            if tag == 'Josa' and word in self.particles_to_mutate:
                if random.random() < probability:
                    chosen_particle = random.choice(self.particles_to_mutate[word])
                    mutated_word = chosen_particle # 삭제는 '' 로 처리됨
                    if mutated_word != word: modified = True

            mutated_parts.append(mutated_word)

        if modified:
            # 재조합 로직 개선 필요: 현재는 단순 join이며 띄어쓰기 보장 안됨
            reassembled = " ".join(filter(None, mutated_parts)) # 빈 문자열 제거 후 join
            reassembled = re.sub(r'\s+', ' ', reassembled).strip() # 연속 공백 정리
            return reassembled
        else:
            return text

    def mutate_endings(self, text, probability=config.DEFAULT_PROB_ENDINGS):
        """문장 끝의 어미를 확률적으로 변경합니다."""
        if not self.analyzer: return text # 형태소 분석기 없으면 실행 어려움
        # 문장 분리 개선 (마침표, 물음표, 느낌표 기준)
        sentences = re.split('([.?!])\s*', text) # 구분자 포함 분리 및 뒤 공백 제거
        if not sentences: return text

        mutated_output = ""
        possible_endings = sorted(self.endings_to_mutate.keys(), key=len, reverse=True)

        i = 0
        while i < len(sentences):
            sentence_part = sentences[i].strip()
            delimiter = sentences[i+1] if i + 1 < len(sentences) else "" # 구분자
            i += 2 # 다음 문장 부분으로 이동

            if not sentence_part: continue # 빈 부분은 건너뛰기

            original_sentence = sentence_part + delimiter # 원본 문장 복원 (어미 비교용)
            modified = False

            if random.random() < probability: # 해당 문장에 변형 적용할지 결정
                for ending in possible_endings:
                    if original_sentence.endswith(ending):
                        replacements = self.endings_to_mutate[ending]
                        if replacements:
                            new_ending = random.choice(replacements)
                            # 기존 어미 제거 후 새 어미 추가
                            base_len = len(original_sentence) - len(ending)
                            sentence_part = original_sentence[:base_len] + new_ending
                            modified = True
                            break # 한 문장에 한 번만 변경

            mutated_output += sentence_part + " " # 결과에 추가하고 공백 삽입

        return mutated_output.strip() # 마지막 공백 제거

        # ★★★ 유의어 치환 함수 수정 (유해 키워드 체크 제거) ★★★
    # 기존 유의어 확률 재사용 또는 별도 설정
    def mutate_synonyms(self, text, probability=config.DEFAULT_PROB_SYNONYM):
        """(통합됨) 내용어를 관련된 단어(유의어, 상위어, 하위어) 중 하나로 확률적으로 치환합니다."""
        if not self.analyzer or not self.korean_thesaurus:
            # Okt 분석기 또는 사전 없으면 실행 불가
            return text

        pos_tags = self._get_pos(text)
        if not pos_tags:
            return text

        candidate_indices = []
        # 교체 가능한 품사 목록 (명사, 동사, 형용사, 부사 등)
        replaceable_pos = ['Noun', 'Verb', 'Adjective', 'Adverb']

        for i, (word, tag) in enumerate(pos_tags):
            if tag in replaceable_pos:
                # ★ 해당 단어/품사에 대한 관련 단어가 있는지 확인 (get_related_words 활용) ★
                # 성능을 위해 여기서 미리 체크하거나, 나중에 한 번에 체크 가능
                # 여기서는 일단 인덱스만 저장
                if word in self.korean_thesaurus and tag in self.korean_thesaurus[word]:
                    candidate_indices.append(i)

        if not candidate_indices:
            # logger.debug("Related word mutation: No replaceable candidates found in thesaurus.")
            return text  # 교체 후보 없으면 원본 반환

        original_word, original_tag = "", ""  # except 블록에서 사용 위해 미리 선언
        try:
            if random.random() < probability:  # 확률 체크
                idx_to_replace = random.choice(candidate_indices)
                original_word, original_tag = pos_tags[idx_to_replace]

                # ★ 새로운 헬퍼 함수 호출하여 관련 단어 목록 가져오기 ★
                related_words = self.get_related_words(
                    original_word, original_tag)

                if related_words:  # 관련 단어가 하나라도 있으면
                    chosen_word = random.choice(related_words)

                    # 안전장치: 선택된 단어가 문자열인지 재확인 (get_related_words에서 처리했어야 함)
                    if not isinstance(chosen_word, str):
                        logger.warning(
                            f"Chosen related word is not a string: {chosen_word} (type: {type(chosen_word)}) for word '{original_word}'. Skipping.")
                        return text

                    logger.debug(
                        f"Related word mutation: Replacing '{original_word}'({original_tag}) with '{chosen_word}'")

                    # --- 텍스트 재구성 (기존 방식 유지) ---
                    mutated_parts = []
                    for i, (word, tag) in enumerate(pos_tags):
                        if i == idx_to_replace:
                            mutated_parts.append(chosen_word)
                        else:
                            mutated_parts.append(word)

                    reassembled_text = " ".join(filter(None, mutated_parts))
                    reassembled_text = re.sub(
                        r'\s+', ' ', reassembled_text).strip()
                    # !!! 한계점: 조사/어미 자동 변경 안됨은 여전함 !!!

                    logger.info(
                        f"Related Word Applied: Replaced '{original_word}' with '{chosen_word}'")
                    return reassembled_text
                else:
                    # logger.debug(f"No related words found for '{original_word}'({original_tag})")
                    return text  # 관련 단어 없으면 원본 반환
            else:
                return text  # 확률 미달
        except Exception as e:
            logger.error(
                f"Error during related word replacement/reconstruction: Type={type(e)}, Error={e}")
            logger.error(traceback.format_exc())
            # 오류 발생 시점의 변수 값 확인
            logger.error(
                f"Context: original_word='{original_word}', original_tag='{original_tag}'")
            return text  # 오류 발생 시 원본 반환




    # --- 기존 High-Level 변형 함수 ---
    def insert_korean_fillers(self, text, probability=config.DEFAULT_PROB_FILLERS):
        """텍스트의 어절 사이에 확률적으로 필러를 삽입합니다."""
        words = text.split(' ')
        if len(words) < 2: return text

        mutated_words = [words[0]] # 첫 단어는 유지
        for i in range(1, len(words)):
            # 이전 단어와 현재 단어 사이에 필러 삽입
            if words[i-1] and words[i] and random.random() < probability:
                mutated_words.append(random.choice(self.fillers).strip()) # 필러 앞뒤 공백 제거
            mutated_words.append(words[i])

        # 재조합 시 연속 공백 방지
        return re.sub(r'\s+', ' ', ' '.join(filter(None, mutated_words))).strip()

    # --- 메인 변형 함수 ---
    def mutate(self, text):
        """
        다양한 변형을 적용하되, 유의어 변형은 별도로 더 자주 시도하고,
        최종적으로 적용된 변형 목록을 함께 반환합니다.
        """
        original_text_for_run = text  # 초기 텍스트 저장
        mutated_text = text
        applied_mutations = []  # 실제로 적용된 변형 함수 이름 기록

        # 1. 일반 변형 적용 (Low/Medium/High 풀에서 랜덤 선택)
        available_mutation_pool = []
        # 유의어 변형은 아래에서 별도 처리하므로 여기서는 제외 가능 (선택적)
        general_medium_funcs = [
            f for f in self.medium_level_funcs if f != self.mutate_synonyms]

        if self.analyzer:
            available_mutation_pool.extend(general_medium_funcs)
            available_mutation_pool.extend(self.high_level_funcs)
        available_mutation_pool.extend(self.low_level_funcs)

        if available_mutation_pool:
            random.shuffle(available_mutation_pool)
            # 적용할 일반 변형 개수 (1~2개 정도로 유지)
            num_general_mutations_to_apply = random.randint(1, 2)
            funcs_to_apply = random.sample(available_mutation_pool, min(
                num_general_mutations_to_apply, len(available_mutation_pool)))

            logger.debug(
                f"Applying {len(funcs_to_apply)} general mutations: {[f.__name__ for f in funcs_to_apply]}")

            for func in funcs_to_apply:
                original_text_before_func = mutated_text
                try:
                    mutated_text = func(mutated_text)
                    if mutated_text != original_text_before_func:
                        level = "L" if func in self.low_level_funcs else (
                            "M" if func in general_medium_funcs else "H")
                        applied_mutations.append(f"{level}:{func.__name__}")
                except Exception as e:
                    logger.error(
                        f"General mutation function {func.__name__} failed: {e}")
                    mutated_text = original_text_before_func  # 오류 시 복구

        # 2. ★★★ 유의어 변형 별도 시도 (더 높은 내부 확률 적용) ★★★
        if self.analyzer and self.korean_thesaurus:  # 사전 로드 확인
            original_text_before_synonym = mutated_text
            try:
                # mutate_synonyms 함수를 직접 호출 (내부 확률은 config 값 사용 - 이미 높여둠)
                mutated_text = self.mutate_synonyms(
                    mutated_text)  # probability 인자는 config 기본값 사용
                if mutated_text != original_text_before_synonym:
                    # 성공적으로 적용되었으면 목록에 추가
                    applied_mutations.append(
                        f"M:mutate_synonyms")  # Medium 레벨로 가정
            except Exception as e:
                logger.error(f"Synonym mutation function failed: {e}")
                mutated_text = original_text_before_synonym  # 오류 시 복구

        # 최종 로깅
        if applied_mutations:
            logger.info(f"Applied mutations: {', '.join(applied_mutations)}")
        else:
            # 유의어 변형만 시도되었지만 확률적으로 실패한 경우도 있으므로 로그 조정
            if not available_mutation_pool and (self.analyzer and self.korean_thesaurus):
                logger.debug(
                    "Only synonym mutation was attempted but did not apply due to probability.")
            else:
                logger.debug(
                    "No effective mutations applied in this iteration.")

        # ★★★ 변형된 텍스트와 함께 적용된 변형 목록 반환 ★★★
        return mutated_text, applied_mutations

# --- 모듈 테스트용 코드 (선택적) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format=config.LOG_FORMAT)
    mutator = KoreanMutator()

    test_texts = [
        "안녕하세요. 만나서 반갑습니다.",
        "이것은 테스트 문장입니다. 잘 작동하는지 확인해봅시다.",
        "저는 밥을 먹었습니다.",
        "빨리 와 주세요!",
        "대한민국의 수도는 서울이다.",
    ]

    for text in test_texts:
        print(f"\n원본: {text}")
        mutated = mutator.mutate(text)
        print(f"변형: {mutated}")