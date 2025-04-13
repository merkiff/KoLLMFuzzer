import random
import jamo
from konlpy.tag import Okt # 또는 from konlpy.tag import Mecab

class KoreanMutator:
    def __init__(self):
        """형태소 분석기를 초기화합니다."""
        try:
            # Okt 객체 생성 (Mecab 사용 시 Mecab())
            self.analyzer = Okt()
            print("Okt 형태소 분석기 초기화 완료.")
        except Exception as e:
            print(f"형태소 분석기 초기화 오류: {e}")
            print("KoNLPy 및 Okt(또는 Mecab)가 올바르게 설치되었는지 확인하세요.")
            self.analyzer = None
        
        # 자주 사용할 변형 규칙이나 목록 정의
        self.particles_to_mutate = {
            '은': ['는', '이', '가', ''], # ''는 삭제 의미
            '는': ['은', '이', '가', ''],
            '이': ['가', '은', '는', ''],
            '가': ['이', '은', '는', ''],
            '을': ['를', ''],
            '를': ['을', ''],
            # 필요시 다른 조사 추가 (예: 에/에서, 와/과)
        }
        self.endings_to_mutate = {
            '요.': ['다.', '죠?', 'ㅂ니다.'],
            '다.': ['요.', '나?', 'ㅂ니다.'],
            '까?': ['죠?', '다.'],
            'ㅂ니다.': ['요.', '다.'],
            # 필요시 다른 어미 추가
        }
        self.fillers = ["음 ", "그 ", "좀 ", "약간 ", "뭔가 ", "사실 ", "이제 "]
        # 간단한 오타 변형 규칙 (키보드 근접 문자 또는 발음 유사)
        self.typo_map = {
            'ㅏ': 'ㅑ', 'ㅓ': 'ㅕ', 'ㅗ': 'ㅛ', 'ㅜ': 'ㅠ',
            'ㅂ': 'ㅍ', 'ㅈ': 'ㅊ', 'ㄷ': 'ㅌ', 'ㄱ': 'ㅋ',
            'ㅆ': 'ㅅ', 'ㄲ': 'ㄱ', 'ㄳ': 'ㄱ', 'ㄵ':'ㄴ', # 받침 단순화
            # 필요시 추가
        }

    def _get_pos(self, text):
        """텍스트의 형태소 및 품사 태그를 반환합니다."""
        if not self.analyzer:
            return []
        try:
            return self.analyzer.pos(text, norm=True, stem=False) # 원형 복원 안 함(False)
        except Exception as e:
            print(f"형태소 분석 오류: {e}")
            return []

    # --- 각 변형 함수 구현 ---
    # (아래 2~5 단계에서 상세 구현)

    # --- 최종 변형 적용 함수 ---
    def mutate(self, text, probability=0.7):
        """입력 텍스트에 대해 정의된 변형들을 확률적으로 적용합니다."""
        if not self.analyzer or random.random() > probability:
            return text # 일정 확률로 변형을 적용하지 않음

        mutated_text = text
        
        # 적용할 변형 함수 목록 (더 추가 가능)
        mutation_functions = [
            self.mutate_particles,
            self.mutate_endings,
            self.mutate_spacing_typo,
            self.insert_korean_fillers,
            self.mutate_jamo,
            self.mutate_random_syllable
        ]
        
        # 함수 중 일부를 랜덤하게 선택하여 적용하거나, 순차적으로 확률 적용
        random.shuffle(mutation_functions) # 적용 순서 랜덤화

        for func in mutation_functions:
             # 각 함수는 내부적으로 적용 확률을 가질 수 있음
             # 또는 여기서 전체적으로 적용 여부 결정 가능
             if random.random() < 0.5: # 예: 각 변형이 50% 확률로 시도됨
                 mutated_text = func(mutated_text) # 각 함수는 확률 파라미터 가질 수 있음

        return mutated_text
    
    def mutate_particles(self, text, probability=0.15):
        """텍스트 내 조사를 확률적으로 변경하거나 삭제합니다."""
        pos_tags = self._get_pos(text)
        if not pos_tags:
            return text

        mutated_parts = []
        modified = False
        for word, tag in pos_tags:
            mutated_word = word
            # 조사를 식별하고 (Josa 태그 확인 - Okt 기준 'Josa')
            if tag == 'Josa' and word in self.particles_to_mutate:
                if random.random() < probability:
                    # 정의된 후보 중에서 랜덤 선택 (삭제 포함)
                    mutated_word = random.choice(self.particles_to_mutate[word])
                    if mutated_word != word:
                        modified = True
            mutated_parts.append(mutated_word)
        
        # 주의: KoNLPy는 때때로 형태소를 합쳐서 반환할 수 있으므로,
        # 단순히 join하면 원본과 달라질 수 있습니다.
        # 여기서는 간단하게 공백으로 합치지만, 더 정교한 재조합 로직이 필요할 수 있습니다.
        # 또는 원본 텍스트에서 직접 치환하는 방식을 고려할 수도 있습니다.
        if modified:
            # Okt의 경우, 원본 형태를 최대한 유지하며 join 시도 (완벽하지 않음)
            # return self.analyzer.morphs(''.join(mutated_parts)) # 이건 재분석이라 비효율적
            # 가장 간단한 방법 (띄어쓰기 문제 발생 가능):
             try:
                 # KoNLPy Okt의 join 기능 활용 시도 (제공 여부 확인 필요, 없으면 직접 구현)
                 # 여기서는 임시로 단순 join 사용
                 return " ".join(p for p in mutated_parts if p) # 빈 문자열 제거 후 join
             except Exception:
                 return text # 재조합 실패 시 원본 반환
        else:
            return text
        
    def mutate_endings(self, text, probability=0.15):
        """문장 끝의 어미를 확률적으로 변경합니다."""
        mutated_text = text
        # 정의된 어미-대체어 쌍에 대해 반복
        for ending, replacements in self.endings_to_mutate.items():
            # 문장이 해당 어미로 끝나는지 확인하고 확률적으로 변경
            if mutated_text.endswith(ending) and random.random() < probability:
                # 여러 대체 어미 중 하나를 랜덤 선택
                new_ending = random.choice(replacements)
                # 기존 어미를 새 어미로 교체 (문자열 끝 부분만)
                mutated_text = mutated_text[:-len(ending)] + new_ending
                # 한번 변경했으면 루프 종료 (중복 변경 방지)
                break 
        return mutated_text
    
    def mutate_spacing_typo(self, text, probability_space=0.05, probability_typo=0.05):
        """띄어쓰기 오류 및 간단한 오타를 확률적으로 발생시킵니다."""
        mutated_chars = []
        for i, char in enumerate(text):
            current_char = char
            
            # 오타 발생
            if random.random() < probability_typo:
                if char in self.typo_map:
                    current_char = self.typo_map[char] # 정의된 오타로 변경

            mutated_chars.append(current_char)

            # 띄어쓰기 오류 (단순화)
            # 확률적으로 띄어쓰기 삭제
            if char == ' ' and random.random() < probability_space:
                if mutated_chars and mutated_chars[-1] == ' ': # 방금 추가한게 공백이면 삭제
                     mutated_chars.pop()
            # 확률적으로 띄어쓰기 추가 (공백 아닌 문자 뒤)
            elif char != ' ' and random.random() < probability_space:
                 mutated_chars.append(' ')

        return "".join(mutated_chars)
    
    def insert_korean_fillers(self, text, probability=0.1):
        """텍스트의 어절 사이에 확률적으로 필러를 삽입합니다."""
        words = text.split(' ')
        if not words:
            return text

        mutated_words = [words[0]] # 첫 단어는 그대로
        for i in range(1, len(words)):
            # 현재 단어 앞에 확률적으로 필러 삽입
            if random.random() < probability:
                mutated_words.append(random.choice(self.fillers))
            mutated_words.append(words[i])

        return ' '.join(mutated_words)
    
    def mutate_jamo(self, text, probability=0.05):
        """
        텍스트 내 한글 음절의 자모(초성, 중성, 종성)를 확률적으로 변경합니다.
        """
        if not isinstance(text, str):
            print(f"오류: mutate_jamo 함수에 문자열이 아닌 입력: {type(text)}")
            return text

        mutated_text = ""
        # 가능한 중성 모음 목록 (자주 쓰이는 것 위주)
        possible_medials = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ',
                            'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
        # 가능한 종성 목록 (받침 없음 포함)
        possible_finals = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ',
                           'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ',
                           'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        # 가능한 초성 목록
        possible_initials = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ',
                             'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

        for char in text:
            # ★ 수정된 부분: 한글 음절 범위(AC00-D7A3)인지 직접 확인 ★
            if '가' <= char <= '힣' and random.random() < probability:
                try:
                    # 1. 음절을 초성, 중성, 종성으로 분해
                    decomposed = jamo.jamo_to_hcj(jamo.h2j(char))
                    initial = decomposed[0]
                    medial = decomposed[1]
                    # 종성은 없을 수도 있음 (길이 체크)
                    final = decomposed[2] if len(decomposed) > 2 else ''

                    # 2. 랜덤하게 자모 중 하나 또는 여러 개 변경 (예시: 중성 또는 종성 변경)
                    if random.random() < 0.5:  # 50% 확률로 중성 변경 시도
                        medial = random.choice(possible_medials)
                    if random.random() < 0.3:  # 30% 확률로 종성 변경 시도 (없앨 수도 있음)
                        final = random.choice(possible_finals)
                    # 필요시 초성 변경 로직 추가 가능
                    # if random.random() < 0.1: initial = random.choice(possible_initials)

                    # 3. 변경된 자모로 다시 음절 결합
                    # jamo.hcj_to_h는 초성, 중성, 종성 순서로 인자를 받음
                    mutated_char = jamo.hcj_to_h(initial, medial, final)
                    mutated_text += mutated_char

                except Exception as e:
                    # 분해/결합 중 예상 못한 오류 발생 시 원본 문자 사용
                    # print(f"Jamo mutation error for '{char}': {e}")
                    mutated_text += char
            else:
                # 한글 음절이 아니거나 확률 조건 미충족 시 원본 문자 사용
                mutated_text += char

        return mutated_text

    def mutate_random_syllable(self, text, probability=0.03):
        mutated_text = ""
        for char in text:
            # 한글 음절 범위 확인
            if '가' <= char <= '힣' and random.random() < probability:
                # AC00(가) 부터 D7A3(힣) 사이의 랜덤 코드 포인트 생성
                random_code = random.randint(0xAC00, 0xD7A3)
                mutated_text += chr(random_code)  # 랜덤 음절로 대체
            else:
                mutated_text += char
        return mutated_text
    