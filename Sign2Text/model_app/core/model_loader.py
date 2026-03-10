"""모델 로더 - 서버 시작 시 1회 로드"""
import csv
import logging
import os
import tensorflow as tf

from model_app.core.config import settings

logger = logging.getLogger("model-loader")
logging.basicConfig(level=logging.INFO)

class ModelLoader:
    """전역 모델 저장소

    모든 ML 모델을 중앙에서 관리
    - LSTM: 수어 → 글로스
    - LLM API: 글로스 → 텍스트
    """

    # ===== 모델 =====
    lstm_model = None

    # ===== 레이블 =====
    label_list = []
    gloss_dict = {}

    # ===== 상태 =====
    _model_status = {}

    # ===== LSTM 모델 =====
    @classmethod
    def load_lstm_model(cls):
        """LSTM 모델 로드"""
        if cls.lstm_model is not None:
            logger.warning("⚠️ [LSTM] 모델이 이미 로드됨")
            return

        try:
            logger.info(f"📦 [LSTM] 모델 로딩 시작: {settings.LSTM_MODEL_PATH}")

            # ── 모델 로드 ──────────────────────────────────
            cls.lstm_model = tf.keras.models.load_model(
                settings.LSTM_MODEL_PATH
            )

            cls._model_status['lstm'] = True
            logger.info(f"✅ [LSTM] 모델 로드 완료")

        except FileNotFoundError:
            logger.error(f"❌ [LSTM] 모델 파일을 찾을 수 없음: {settings.LSTM_MODEL_PATH}")
            cls._model_status['lstm'] = False
        except Exception as e:
            logger.error(f"❌ [LSTM] 모델 로드 실패: {e}")
            cls._model_status['lstm'] = False
            raise

    # ===== 레이블 로드 =====
    @classmethod
    def load_labels(cls):
        """label.csv에서 레이블 로드"""
        if cls.label_list:
            logger.warning("⚠️ [LSTM] 레이블이 이미 로드됨")
            return

        try:
            logger.info(f"📦 [LSTM] 레이블 로딩 시작: {settings.GLOSS_LABEL_PATH}")

            with open(settings.GLOSS_LABEL_PATH, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    label = row["label"]
                    gloss = row["title"]
                    cls.label_list.append(label)
                    cls.gloss_dict[label] = gloss

            logger.info(f"✅ [LSTM] 레이블 로드 완료: {len(cls.label_list)}개 클래스")

        except Exception as e:
            logger.error(f"❌ [LSTM] 레이블 로드 실패: {e}")
            raise

    # ===== 전체 초기화 =====
    @classmethod
    def initialize_all(cls):
        """모든 모델 초기화"""
        logger.info("=" * 70)
        logger.info("🔧 모델 로딩 시작...")
        logger.info("=" * 70)

        cls.load_lstm_model()  # le_classes 도 여기서 로드됨
        cls.load_labels()      # gloss_dict 구성

        logger.info("📊 모델 로딩 결과:")
        logger.info(f"  - LSTM      : {'✅ 로드됨' if cls._model_status.get('lstm') else '❌ 로드 실패'}")
        logger.info(f"  - label_list: {'✅' if cls.label_list else '❌'} ({len(cls.label_list)}개)")
        logger.info(f"  - gloss_dict: {'✅' if cls.gloss_dict else '❌'} ({len(cls.gloss_dict)}개)")

        if not cls._model_status.get('lstm'):
            raise RuntimeError("LSTM 로드 실패")

        logger.info("=" * 70)
        logger.info("✅ 모델 로딩 완료")
        logger.info("=" * 70)

    # ===== 상태 조회 =====
    @classmethod
    def get_model_status(cls):
        return {"lstm": cls.lstm_model is not None}

    # ===== 모델 언로드 =====
    @classmethod
    def unload_all(cls):
        if cls.lstm_model is not None:
            del cls.lstm_model
            cls.lstm_model = None
            cls._model_status['lstm'] = False
            logger.info("🗑️ [LSTM] 모델 언로드됨")
        logger.info("✅ 모든 모델 언로드 완료")