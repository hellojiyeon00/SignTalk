"""모델 로더 - 서버 시작 시 1회 로드"""
import csv
import logging

import torch
import torch.nn as nn

from model_app.core.config import settings

logger = logging.getLogger("model-loader")
logging.basicConfig(level=logging.INFO)

# ── 디바이스 설정 ──────────────────────────────────────────────
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── GlossLSTM 모델 정의 ──────────
class GlossLSTM(nn.Module):
    """Bidirectional LSTM + Attention pooling 분류기"""

    def __init__(self, input_dim, hidden_size, num_layers, num_classes, dropout=0.3):
        super().__init__()
        self.input_norm = nn.BatchNorm1d(input_dim)
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        lstm_out_dim = hidden_size * 2
        self.attn = nn.Sequential(
            nn.Linear(lstm_out_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 1)
        )
        self.classifier = nn.Sequential(
            nn.Linear(lstm_out_dim, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, num_classes)
        )

    def forward(self, x):
        batch, seq_len, feat = x.shape
        x = self.input_norm(x.reshape(-1, feat)).reshape(batch, seq_len, feat)
        out, _ = self.lstm(x)
        scores  = self.attn(out).squeeze(-1)
        weights = torch.softmax(scores, dim=-1)
        context = (weights.unsqueeze(-1) * out).sum(dim=1)
        return self.classifier(context)

class ModelLoader:
    """전역 모델 저장소

    모든 ML 모델을 중앙에서 관리
    - LSTM: 수어 → 글로스
    - LLM API: 글로스 → 텍스트
    """

    # ===== 모델 =====
    lstm_model = None

    # ===== 레이블 =====
    le_classes = []
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

            # ── 체크포인트 로드 ──────────────────────────────────
            ckpt = torch.load(
                settings.LSTM_MODEL_PATH,
                map_location=DEVICE,
                weights_only=False   # label_encoder_classes(list) 포함 저장본 호환
            )

            # ── 모델 구성 (저장된 하이퍼파라미터 사용) ───────────
            cls.lstm_model = GlossLSTM(
                input_dim=ckpt["input_dim"],
                hidden_size=ckpt["hidden_size"],
                num_layers=ckpt["num_layers"],
                num_classes=ckpt["num_classes"],
                dropout=ckpt["dropout"]
            ).to(DEVICE)

            cls.lstm_model.load_state_dict(ckpt["model_state"])
            cls.lstm_model.eval()

            cls.le_classes = list(ckpt["label_encoder_classes"])
            cls._model_status['lstm'] = True

            logger.info(f"✅ [LSTM] 모델 로드 완료")
            logger.info(f"   input_dim   : {ckpt['input_dim']}")
            logger.info(f"   hidden_size : {ckpt['hidden_size']}")
            logger.info(f"   num_classes : {ckpt['num_classes']}")
            logger.info(f"   le_classes  : {len(cls.le_classes)}개 (예: {cls.le_classes[:3]}...)")
            logger.info(f"   device      : {DEVICE}")

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

            with open(settings.GLOSS_LABEL_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    label = row["label"]
                    gloss = row["gloss"]
                    cls.label_list.append(label)
                    cls.gloss_dict[label] = gloss

            logger.info(f"✅ [LSTM] 레이블 로드 완료: {len(cls.label_list)}개 클래스")

        except Exception as e:
            logger.error(f"❌ [LSTM] 레이블 로드 실패: {e}")
            raise

    # ===== 전체 초기화 =====
    @classmethod
    def initialize_all(cls, load_optional: bool = True):
        """모든 모델 초기화"""
        logger.info("=" * 70)
        logger.info("🔧 모델 로딩 시작...")
        logger.info("=" * 70)

        cls.load_lstm_model()  # le_classes 도 여기서 로드됨
        cls.load_labels()      # gloss_dict 구성

        logger.info("📊 모델 로딩 결과:")
        logger.info(f"  - LSTM      : {'✅ 로드됨' if cls._model_status.get('lstm') else '❌ 로드 실패'}")
        logger.info(f"  - le_classes: {'✅' if cls.le_classes else '❌'} ({len(cls.le_classes)}개)")
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