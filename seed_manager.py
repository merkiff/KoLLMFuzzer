# seed_manager.py
import random
import logging
import os  # os 모듈 임포트 추가

logger = logging.getLogger(__name__)


class SeedManager:
    """
    시드 파일을 로드하고, 가중치 기반 랜덤 선택 및 가중치 업데이트를 관리하는 클래스.
    """
    # --- 가중치 업데이트 설정 ---
    INITIAL_WEIGHT = 1.0
    WEIGHT_INCREASE = 0.1  # 성공 시 가중치 증가량
    WEIGHT_DECREASE = 0.05  # 실패 시 가중치 감소량 (성공보다 작게 설정 가능)
    MIN_WEIGHT = 0.1       # 최소 가중치
    MAX_WEIGHT = 10.0      # 최대 가중치

    def __init__(self, seed_file_path):
        """
        시드 파일을 로드하고 각 시드에 초기 가중치를 할당합니다.

        Args:
            seed_file_path (str): 시드 프롬프트가 한 줄씩 포함된 파일 경로.
        """
        self.seed_pool = []
        self.seed_file_path = seed_file_path
        self.load_seeds()

    def load_seeds(self):
        """시드 파일에서 시드를 로드하고 초기화합니다."""
        if not os.path.exists(self.seed_file_path):
            logger.error(f"시드 파일을 찾을 수 없습니다: {self.seed_file_path}")
            return

        try:
            with open(self.seed_file_path, 'r', encoding='utf-8') as f:
                seeds = [line.strip()
                         for line in f if line.strip()]  # 비어있지 않은 줄만 로드

            if not seeds:
                logger.error(f"시드 파일에 유효한 시드가 없습니다: {self.seed_file_path}")
                return

            # 각 시드를 딕셔너리 형태로 저장 (시드 텍스트, 초기 가중치, 인덱스)
            self.seed_pool = [
                {'id': i, 'seed': seed_text, 'weight': self.INITIAL_WEIGHT}
                for i, seed_text in enumerate(seeds)
            ]
            logger.info(f"총 {len(self.seed_pool)}개의 시드를 로드했습니다.")

        except Exception as e:
            logger.error(f"시드 파일 로드 중 오류 발생: {e}")
            self.seed_pool = []

    def select_seed(self):
        """
        현재 가중치에 따라 시드 풀에서 시드 하나를 랜덤하게 선택합니다.

        Returns:
            dict | None: 선택된 시드 정보 ({'id': int, 'seed': str, 'weight': float}) 또는 시드 풀이 비어있으면 None.
        """
        if not self.seed_pool:
            logger.warning("시드 풀이 비어 있어 시드를 선택할 수 없습니다.")
            return None

        # 현재 모든 시드의 가중치 리스트 생성
        weights = [item['weight'] for item in self.seed_pool]
        total_weight = sum(weights)

        if total_weight <= 0:
            # 모든 가중치가 0 이하인 경우 (예: 계속 실패하여 최소 가중치 도달)
            # 균등 확률로 선택하거나, 특정 전략(예: 초기화) 사용 가능
            logger.warning("모든 시드 가중치가 0 이하입니다. 균등 확률로 선택합니다.")
            selected_item = random.choice(self.seed_pool)
        else:
            # 가중치 기반 랜덤 선택 (random.choices 사용)
            # choices는 k=1일 때 아이템 하나를 포함하는 리스트를 반환하므로 [0]으로 접근
            selected_item = random.choices(
                self.seed_pool, weights=weights, k=1)[0]

        logger.debug(
            f"선택된 시드 ID: {selected_item['id']}, 가중치: {selected_item['weight']:.2f}")
        return selected_item

    def update_weight(self, selected_seed_id, success):
        """
        선택된 시드의 ID와 성공 여부에 따라 해당 시드의 가중치를 업데이트합니다.

        Args:
            selected_seed_id (int): 가중치를 업데이트할 시드의 ID.
            success (bool): 해당 시드로부터 변형된 프롬프트가 탈옥에 성공했는지 여부.
        """
        # ID를 사용하여 해당 시드 찾기 (더 안전한 방식)
        seed_item = next(
            (item for item in self.seed_pool if item['id'] == selected_seed_id), None)

        if seed_item:
            current_weight = seed_item['weight']
            if success:
                new_weight = min(
                    self.MAX_WEIGHT, current_weight + self.WEIGHT_INCREASE)
                logger.debug(
                    f"시드 ID {selected_seed_id} 가중치 증가: {current_weight:.2f} -> {new_weight:.2f}")
            else:
                new_weight = max(
                    self.MIN_WEIGHT, current_weight - self.WEIGHT_DECREASE)
                logger.debug(
                    f"시드 ID {selected_seed_id} 가중치 감소: {current_weight:.2f} -> {new_weight:.2f}")

            seed_item['weight'] = new_weight
        else:
            logger.warning(
                f"가중치 업데이트 실패: 시드 ID {selected_seed_id}를 찾을 수 없습니다.")

    def get_seed_by_id(self, seed_id):
        """ID로 시드 텍스트를 조회합니다."""
        seed_item = next(
            (item for item in self.seed_pool if item['id'] == seed_id), None)
        return seed_item['seed'] if seed_item else None

    def get_current_weights(self):
        """디버깅 또는 로깅을 위해 현재 모든 시드의 가중치를 반환합니다."""
        return {item['id']: round(item['weight'], 2) for item in self.seed_pool}
