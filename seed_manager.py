# seed_manager.py
import random
import logging
import os
import config  # config 임포트

logger = logging.getLogger(__name__)


class SeedManager:
    """시드 파일을 로드하고, 가중치 기반 랜덤 선택 및 가중치 업데이트를 관리."""

    def __init__(self, seed_file_path):
        """
        Args:
            seed_file_path (str): 시드 프롬프트 파일 경로 (config에서 가져옴).
        """
        self.seed_pool = []
        self.seed_file_path = seed_file_path
        # config에서 설정값 가져오기
        self.initial_weight = config.INITIAL_WEIGHT
        self.weight_increase = config.WEIGHT_INCREASE
        self.weight_decrease = config.WEIGHT_DECREASE
        self.min_weight = config.MIN_WEIGHT
        self.max_weight = config.MAX_WEIGHT
        self.load_seeds()

    def load_seeds(self):
        """시드 파일에서 시드를 로드하고 초기화."""
        if not os.path.exists(self.seed_file_path):
            logger.error(f"시드 파일을 찾을 수 없습니다: {self.seed_file_path}")
            return
        try:
            with open(self.seed_file_path, 'r', encoding='utf-8') as f:
                seeds = [line.strip() for line in f if line.strip()]
            if not seeds:
                logger.error(f"시드 파일에 유효한 시드가 없습니다: {self.seed_file_path}")
                return

            self.seed_pool = [
                {'id': i, 'seed': seed_text, 'weight': self.initial_weight}
                for i, seed_text in enumerate(seeds)
            ]
            logger.info(
                f"총 {len(self.seed_pool)}개의 시드를 '{self.seed_file_path}'에서 로드했습니다.")
        except Exception as e:
            logger.error(f"시드 파일 로드 중 오류 발생: {e}")
            self.seed_pool = []

    def select_seed(self):
        """가중치에 따라 시드 하나를 랜덤하게 선택."""
        if not self.seed_pool:
            logger.warning("시드 풀이 비어 있어 시드를 선택할 수 없습니다.")
            return None

        weights = [item['weight'] for item in self.seed_pool]
        total_weight = sum(weights)

        if total_weight <= 0:
            logger.warning("모든 시드 가중치가 0 이하입니다. 균등 확률로 선택합니다.")
            selected_item = random.choice(self.seed_pool)
        else:
            selected_item = random.choices(
                self.seed_pool, weights=weights, k=1)[0]

        logger.debug(
            f"선택된 시드 ID: {selected_item['id']}, 가중치: {selected_item['weight']:.2f}")
        return selected_item.copy()  # 원본 수정을 방지하기 위해 복사본 반환

    def update_weight(self, selected_seed_id, success):
        """선택된 시드의 가중치를 성공 여부에 따라 업데이트."""
        seed_item = next(
            (item for item in self.seed_pool if item['id'] == selected_seed_id), None)
        if seed_item:
            current_weight = seed_item['weight']
            if success:
                new_weight = min(
                    self.max_weight, current_weight + self.weight_increase)
                logger.debug(
                    f"시드 ID {selected_seed_id} 가중치 증가: {current_weight:.2f} -> {new_weight:.2f}")
            else:
                new_weight = max(
                    self.min_weight, current_weight - self.weight_decrease)
                logger.debug(
                    f"시드 ID {selected_seed_id} 가중치 감소: {current_weight:.2f} -> {new_weight:.2f}")
            seed_item['weight'] = new_weight
        else:
            logger.warning(
                f"가중치 업데이트 실패: 시드 ID {selected_seed_id}를 찾을 수 없습니다.")

    def get_seed_by_id(self, seed_id):
        """ID로 시드 텍스트 조회."""
        seed_item = next(
            (item for item in self.seed_pool if item['id'] == seed_id), None)
        return seed_item['seed'] if seed_item else None

    def get_current_weights(self):
        """디버깅용 현재 가중치 반환."""
        return {item['id']: round(item['weight'], 2) for item in self.seed_pool}
