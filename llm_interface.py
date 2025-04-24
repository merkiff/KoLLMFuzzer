import requests
import json
import logging # 로깅 추가
import config

# 로거 설정 (필요에 따라 조정)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ollama 서버 주소 (기본값)
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate" 
# 타임아웃 설정 (초 단위, 응답이 길어질 수 있으므로 넉넉하게 설정)
#REQUEST_TIMEOUT = 120 

def get_ollama_response(model_name: str, prompt: str, timeout: int) -> str | None:
    """
    Ollama API를 호출하여 지정된 모델로부터 프롬프트에 대한 응답을 받아옵니다.

    Args:
        model_name (str): 사용할 Ollama 모델 이름 (예: "cogito").
        prompt (str): LLM에게 전달할 프롬프트 텍스트.

    Returns:
        str | None: LLM의 응답 텍스트. 오류 발생 시 None 반환.
    """
    headers = {'Content-Type': 'application/json'}
    # Ollama /api/generate 요청 본문 구성
    data = {
        "model": model_name,
        "prompt": prompt,
        "stream": False, # 스트리밍 응답 대신 전체 응답을 한 번에 받음
        # "options": { # 필요시 추가 옵션 설정 가능
        #     "temperature": 0.7,
        #     "num_predict": 512 # 최대 생성 토큰 수 등
        # }
    }
    effective_timeout = timeout if timeout is not None else config.LLM_TIMEOUT

    logger.info(
        f"Ollama 모델에 요청 전송: {model_name} (Timeout: {effective_timeout}s)")
    logger.debug(f"프롬프트 (일부): {prompt[:80]}...")

    try:
        # Ollama API에 POST 요청 보내기
        response = requests.post(
            OLLAMA_ENDPOINT,
            headers=headers,
            data=json.dumps(data), # 데이터를 JSON 문자열로 변환
            timeout=effective_timeout 
        )
        
        # HTTP 오류 코드 확인 (4xx, 5xx)
        response.raise_for_status() 

    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timed out after {effective_timeout} seconds.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to Ollama server. Is Ollama running?")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred during the Ollama request: {e}")
        return None

    logger.info(f"Received response from Ollama (status code: {response.status_code})")

    try:
        # 응답 JSON 파싱
        result = response.json()
        
        # 응답 데이터 구조에서 실제 응답 텍스트 추출
        if 'response' in result:
            llm_answer = result['response'].strip()
            logger.debug(f"Ollama Response: {llm_answer[:100]}...") # 디버깅 시 응답 일부 로깅
            return llm_answer
        else:
            logger.error(f"Ollama response does not contain 'response' key: {result}")
            return None

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON response from Ollama: {response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred processing Ollama response: {e}")
        return None

# --- 모듈 테스트용 코드 ---
if __name__ == '__main__':
    test_prompt = "대한민국의 수도는 어디인가요?"
    model_to_test = "cogito" # 여기에 사용할 로컬 모델 이름 지정

    print(f"Testing Ollama interface with model '{model_to_test}'...")
    print(f"Prompt: {test_prompt}")
    
    ollama_response = get_ollama_response(model_to_test, test_prompt)

    if ollama_response:
        print("\nResponse from Ollama:")
        print(ollama_response)
    else:
        print("\nFailed to get response from Ollama.")