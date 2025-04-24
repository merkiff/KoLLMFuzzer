# main.py
import random
import logging
import time
import json
from datetime import datetime
import os

# 설정 및 모듈 임포트
import config
from seed_manager import SeedManager
from mutator import KoreanMutator
from llm_interface import get_ollama_response
from judge import simple_judge  # 수정된 judge 임포트

# 로깅 설정
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger("FuzzerMain")  # 로거 이름 지정

# --- 결과 저장 함수 정의 ---


def save_log_entry(log_filepath, entry_data):
    """로그 항목을 가독성 좋게 JSON 형식으로 파일에 추가합니다."""
    try:
        with open(log_filepath, 'a', encoding='utf-8') as f:
            # 수정: indent=4 옵션 추가하여 가독성 높임
            log_string = json.dumps(entry_data, ensure_ascii=False, indent=4)
            f.write(log_string + '\n')  # 각 JSON 항목 뒤에 줄바꿈 추가
    except IOError as e:
        logger.error(f"로그 저장 실패 {log_filepath}: {e}")
    except TypeError as e:
        # JSON 직렬화 불가능한 타입이 entry_data에 포함된 경우 처리
        logger.error(f"로그 데이터 직렬화 오류: {e}")
        logger.error(f"오류 데이터 (일부): {str(entry_data)[:200]}...")
        # 오류 발생 시에도 기록 시도 (repr 사용 등)
        try:
            import reprlib
            f.write(reprlib.repr(entry_data) + '\n')
        except:
            pass  # 기록 실패 시 무시


def save_successful_results(results_filepath, successful_prompts):
    if not successful_prompts:
        logger.info("저장할 성공 로그 없음.")
        return
    try:
        with open(results_filepath, 'w', encoding='utf-8') as f:
            json.dump(successful_prompts, f, ensure_ascii=False, indent=4)
        logger.info(
            f"성공 로그 {len(successful_prompts)}건 저장 완료: {results_filepath}")
    except IOError as e:
        logger.error(f"성공 로그 저장 실패 {results_filepath}: {e}")

# --- 메인 퍼징 함수 ---


def main_fuzz_loop():
    logger.info("===== 퍼저 초기화 시작 =====")
    os.makedirs(config.RESULTS_DIR, exist_ok=True)  # 결과 디렉토리 생성

    # 파일명 타임스탬프
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_log_filepath = os.path.join(
        config.RESULTS_DIR, f"all_log_{config.TARGET_MODEL}_{timestamp}.jsonl")
    success_log_filepath = os.path.join(
        config.RESULTS_DIR, f"success_log_{config.TARGET_MODEL}_{timestamp}.json")

    logger.info(f"모든 시도 로그 파일: {all_log_filepath}")
    logger.info(f"성공 시도 로그 파일: {success_log_filepath}")

    # 컴포넌트 초기화
    mutator = KoreanMutator()
    seed_manager = SeedManager(config.SEED_FILE)
    if not seed_manager.seed_pool:
        logger.critical("시드 풀 초기화 실패. 퍼징을 종료합니다.")
        return

    successful_prompts = []  # 성공 로그 저장 리스트

    logger.info(
        f"===== 퍼징 시작 (모델: {config.TARGET_MODEL}, 반복: {config.MAX_ITERATIONS}) =====")
    for i in range(config.MAX_ITERATIONS):
        iteration_start_time = time.time()
        logger.info(f"--- 반복 {i+1}/{config.MAX_ITERATIONS} ---")

        # 1. 시드 선택
        selected_seed_info = seed_manager.select_seed()
        if selected_seed_info is None:
            break  # 시드 없으면 종료
        selected_seed_id = selected_seed_info['id']
        original_seed_text = selected_seed_info['seed']
        logger.info(
            f"선택 시드 ID: {selected_seed_id} (현재 가중치: {selected_seed_info['weight']:.2f})")
        logger.debug(f"원본 시드: {original_seed_text[:80]}...")

        # 2. 변형 (단계 1 변형 적용)
        mutated_prompt = mutator.mutate(original_seed_text)
        mutated_prompt, applied_mutation_names = mutator.mutate(
            original_seed_text)
        logger.debug(f"변형 프롬프트: {mutated_prompt[:80]}...")
        if original_seed_text == mutated_prompt:
            logger.info("변형이 적용되지 않았습니다.")

        # 3. LLM 실행
        logger.info("LLM에 요청 전송...")
        llm_start_time = time.time()
        llm_response = get_ollama_response(
            config.TARGET_MODEL, mutated_prompt, timeout=config.LLM_TIMEOUT)
        llm_duration = time.time() - llm_start_time
        logger.info(f"LLM 응답 수신 완료 ({llm_duration:.2f}초)")
        logger.debug(f"LLM 응답 (일부): {str(llm_response)[:100]}...")

        # 4. 평가
        judgment_result = simple_judge(original_seed_text, llm_response)
        is_success = "SUCCESS" in judgment_result
        logger.info(f"평가 결과: {judgment_result}")

        # 5. 시드 가중치 업데이트
        seed_manager.update_weight(selected_seed_id, is_success)

        # 6. 로깅
        iteration_duration = time.time() - iteration_start_time
        log_entry = {
            "iteration": i + 1,
            "timestamp": datetime.now().isoformat(),
            "seed_id": selected_seed_id,
            "original_seed": original_seed_text,
            "mutated_prompt": mutated_prompt,
            "applied_mutations": applied_mutation_names,
            "llm_response": llm_response if llm_response else "N/A",
            "judgment": judgment_result,
            "llm_duration_sec": round(llm_duration, 2),
            "iteration_duration_sec": round(iteration_duration, 2),
            "model_name": config.TARGET_MODEL,
            # ID 유효성 체크
            "seed_weight_after": round(seed_manager.seed_pool[selected_seed_id]['weight'], 2) if selected_seed_id < len(seed_manager.seed_pool) else 'N/A'
        }

        # 모든 시도 로그 저장
        save_log_entry(all_log_filepath, log_entry)

        if is_success:
            logger.warning(
                f"★★★ 잠재적 탈옥 발견! (반복 {i+1}, 시드 ID {selected_seed_id}) ★★★")
            successful_prompts.append(log_entry)  # 성공 로그 리스트에 추가

        # 주기적 상태 출력 (선택적)
        if (i + 1) % 10 == 0:
            logger.info(
                f"진행: {i+1}/{config.MAX_ITERATIONS}, 현재 성공 건수: {len(successful_prompts)}")
            # logger.debug(f"현재 가중치 상태: {seed_manager.get_current_weights()}")

        # 짧은 대기 (API 제한 등 고려)
        # time.sleep(0.1)

    logger.info("===== 퍼징 종료 =====")
    # 최종 성공 목록 저장
    save_successful_results(success_log_filepath, successful_prompts)
    logger.info(f"총 {len(successful_prompts)}건의 잠재적 탈옥 발견.")
    logger.info(f"전체 로그는 '{all_log_filepath}' 파일에 저장되었습니다.")
    logger.info(f"성공 로그는 '{success_log_filepath}' 파일에 저장되었습니다.")


if __name__ == "__main__":
    main_fuzz_loop()
