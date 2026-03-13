# config 로드 + 스모크 테스트용 스켈레톤
"""
KoBART training entrypoint.

what/inputs/outputs/how to run.
- config.yaml 로드
- JSONL 데이터 로드(datasets)
- tokenizer로 전처리(map)
- Seq2SeqTrainer 구성 + 학습 실행
- best checkpoint 영구 보존 + best 기록 파일 생성

실행:
    python ml/kobart/train.py --config ml/kobart/config.yaml

재개(resume):
    python ml/kobart/train.py --config ml/kobart/config.yaml --resume_from outputs/exp_001/run_YYYYmmdd_HHMMSS/checkpoints/checkpoint-XXXX
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from datasets import DatasetDict, load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    TrainerCallback,
    TrainerState,
    TrainerControl,
    TrainingArguments,
)


def parse_args() -> argparse.Namespace:
    """
    CLI 인자를 파싱합니다.
    """
    parser = argparse.ArgumentParser(description="KoBART training")

    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="학습 설정 YAML 경로 (예: ml/kobart/config.yaml)"
    )

    parser.add_argument(
        "--run_dir",
        type=str,
        default=None,
        help="실험 결과 루트 디렉토리. 예: outputs/exp_001 (미지정 시 config.project.output_dir 사용)"
    )

    parser.add_argument(
        "--resume_from",
        type=str,
        default=None,
        help="Resume from a checkpoint dir (e.g., outputs/exp_001/run_001/checkpoints/checkpoint-2800)"
    )

    return parser.parse_args()


def load_yaml(path: Path) -> Dict[str, Any]:
    """
    YAML 파일을 로드합니다.
    """
    if not path.exists():
        raise FileNotFoundError(f"config 파일을 찾을 수 없습니다: {path}")

    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        raise ValueError("config 최상위 구조는 dict 여야 합니다.")

    return cfg


def require(cfg: Dict[str, Any], dotted_key: str) -> Any:
    """
    점 표기 키(예: 'model.pretrained_name')로 값을 가져옵니다.
    누락 시 KeyError를 발생시킵니다.
    """
    cur: Any = cfg
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(f"필수 설정이 누락되었습니다: {dotted_key}")
        cur = cur[part]
    return cur


def resolve_data_paths(project_root: Path, cfg: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    """
    config에 정의된 데이터 경로를 절대경로로 정규화합니다.
    """
    train_path = (project_root / require(cfg, "data.train_path")).resolve()
    val_path = (project_root / require(cfg, "data.val_path")).resolve()
    test_path = (project_root / require(cfg, "data.test_path")).resolve()
    return train_path, val_path, test_path


def load_jsonl_splits(train_path: Path, val_path: Path, test_path: Path) -> DatasetDict:
    """
    JSONL split 파일을 datasets로 로드합니다.
    """
    for p in (train_path, val_path, test_path):
        if not p.exists():
            raise FileNotFoundError(f"데이터 파일이 없습니다: {p}")

    ds = load_dataset(
        "json",
        data_files={
            "train": str(train_path),
            "validation": str(val_path),
            "test": str(test_path),
        },
    )
    return ds


def build_preprocess_fn(cfg: Dict[str, Any], tokenizer: AutoTokenizer):
    """
    토크나이즈 전처리 함수를 생성합니다.
    """
    text_col = require(cfg, "data.text_col")
    label_col = require(cfg, "data.label_col")

    max_src = int(require(cfg, "model.max_source_length"))
    max_tgt = int(require(cfg, "model.max_target_length"))

    truncation = bool(require(cfg, "model.truncation"))
    padding = require(cfg, "model.padding")

    pad_id = tokenizer.pad_token_id

    def preprocess(examples: Dict[str, Any]) -> Dict[str, Any]:
        """
        src/tgt 컬럼을 받아 model input/label로 변환합니다.
        labels pad는 -100으로 마스킹하여 loss에서 제외합니다.
        """
        src_texts = examples[text_col]
        tgt_texts = examples[label_col]

        model_inputs = tokenizer(
            src_texts,
            max_length=max_src,
            truncation=truncation,
            padding=padding
        )

        # (구버전 tokenizer 호환) as_target_tokenizer 사용
        with tokenizer.as_target_tokenizer():
            labels = tokenizer(
                tgt_texts,
                max_length=max_tgt,
                truncation=truncation,
                padding=padding
            )

        label_ids = labels["input_ids"]
        label_ids = [
            [(t if t != pad_id else -100) for t in seq]
            for seq in label_ids
        ]
        model_inputs["labels"] = label_ids
        return model_inputs

    return preprocess


class BestCheckpointKeeperCallback(TrainerCallback):
    """
    best_model_checkpoint가 갱신될 때마다 해당 checkpoint 폴더를 run_dir/best로 복사해서
    save_total_limit 회전 삭제로부터 영구 보존합니다.
    best 기록은 best/best_checkpoint.json에 저장합니다.
    """

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.best_dir = self.run_dir / "best"
        self.best_dir.mkdir(parents=True, exist_ok=True)
        self._last_best_src: str | None = None

    def _persist_best(self, state: TrainerState) -> None:
        best_src = getattr(state, "best_model_checkpoint", None)
        if not best_src:
            return
        if best_src == self._last_best_src:
            return

        src = Path(best_src)
        if not src.exists():
            return

        # best는 1개만 유지 (원하면 여러 개 유지로 변경 가능)
        for p in self.best_dir.glob("checkpoint-*"):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)

        dst = self.best_dir / src.name
        shutil.copytree(src, dst)

        record = {
            "best_model_checkpoint": str(dst),
            "original_checkpoint": str(src),
            "global_step": int(state.global_step),
            "best_metric": state.best_metric,
        }
        (self.best_dir / "best_checkpoint.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._last_best_src = best_src

    def on_evaluate(self, args: TrainingArguments, state: TrainerState, control: TrainerControl, **kwargs):
        self._persist_best(state)

    def on_save(self, args: TrainingArguments, state: TrainerState, control: TrainerControl, **kwargs):
        # evaluate 없이 저장만 발생하는 흐름에서도 best 보존 방어
        self._persist_best(state)


def build_trainer(cfg: Dict[str, Any], ds: DatasetDict, run_dir: Path) -> Seq2SeqTrainer:
    """
    Trainer를 구성합니다.
    """
    model_name = require(cfg, "model.pretrained_name")
    tokenizer_name = require(cfg, "model.tokenizer_name")

    ckpt_dir = run_dir / "checkpoints"
    log_dir = run_dir / "logs"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    epochs = int(require(cfg, "train.epochs"))
    train_bs = int(require(cfg, "train.train_batch_size"))
    eval_bs = int(require(cfg, "train.eval_batch_size"))
    lr = float(require(cfg, "train.learning_rate"))
    weight_decay = float(require(cfg, "train.weight_decay"))
    warmup_ratio = float(require(cfg, "train.warmup_ratio"))
    grad_acc = int(require(cfg, "train.gradient_accumulation_steps"))
    max_grad_norm = float(require(cfg, "train.max_grad_norm"))
    fp16 = bool(require(cfg, "train.fp16"))

    eval_strategy = require(cfg, "eval.eval_strategy").strip().lower()
    if eval_strategy not in {"no", "steps", "epoch"}:
        raise ValueError(f"Invalid eval_strategy: {eval_strategy}")

    eval_steps = int(require(cfg, "eval.eval_steps"))

    save_strategy = require(cfg, "eval.save_strategy").strip().lower()
    if save_strategy not in {"no", "steps", "epoch"}:
        raise ValueError(f"Invalid save_strategy: {save_strategy}")

    save_steps = int(require(cfg, "eval.save_steps"))
    save_total_limit = int(require(cfg, "eval.save_total_limit"))

    predict_with_generate = require(cfg, "eval.predict_with_generate")
    if not isinstance(predict_with_generate, bool):
        raise ValueError("eval.predict_with_generate must be a boolean")

    gen_max_len = int(require(cfg, "eval.generation_max_length"))
    num_beams = int(require(cfg, "eval.generation_num_beams"))

    metric_for_best_model = str(require(cfg, "eval.metric_for_best_model"))
    greater_is_better = bool(require(cfg, "eval.greater_is_better"))
    # 권장: loss면 eval_loss로 정규화
    if metric_for_best_model == "loss":
        metric_for_best_model = "eval_loss"

    report_to = require(cfg, "runtime.report_to")
    num_workers = int(require(cfg, "runtime.num_workers"))

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    preprocess = build_preprocess_fn(cfg, tokenizer)

    remove_cols = list(ds["train"].column_names)
    tokenized = ds.map(
        preprocess,
        batched=True,
        remove_columns=remove_cols,
        desc="Tokenizing"
    )

    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)

    smoke_cfg = cfg.get("smoke", {} if isinstance(cfg.get("smoke", {}), dict) else {})
    limit_steps = smoke_cfg.get("limit_steps")

    args = Seq2SeqTrainingArguments(
        output_dir=str(ckpt_dir),
        logging_dir=str(log_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=train_bs,
        per_device_eval_batch_size=eval_bs,
        learning_rate=lr,
        weight_decay=weight_decay,
        warmup_ratio=warmup_ratio,
        gradient_accumulation_steps=grad_acc,
        max_grad_norm=max_grad_norm,
        max_steps=int(limit_steps) if limit_steps else -1,
        fp16=fp16,

        evaluation_strategy=eval_strategy,
        eval_steps=eval_steps if eval_strategy == "steps" else None,

        save_strategy=save_strategy,
        save_steps=save_steps if save_strategy == "steps" else None,
        save_total_limit=save_total_limit,

        load_best_model_at_end=(eval_strategy != "no"),
        metric_for_best_model=metric_for_best_model,
        greater_is_better=greater_is_better,

        predict_with_generate=predict_with_generate,
        report_to=[] if report_to == "none" else [report_to],
        dataloader_num_workers=num_workers,
    )

    # --- FORCE OVERRIDE (sanity 안정화) ---
    args.evaluation_strategy = eval_strategy
    args.save_strategy = save_strategy
    if eval_strategy == "steps":
        args.eval_steps = eval_steps
    if save_strategy == "steps":
        args.save_steps = save_steps

    print(
        f"[ARGS] evaluation_strategy={args.evaluation_strategy}, eval_steps={args.eval_steps}, "
        f"save_strategy={args.save_strategy}, save_steps={args.save_steps}, "
        f"load_best_model_at_end={args.load_best_model_at_end}, metric_for_best_model={args.metric_for_best_model}"
    )

    max_train = smoke_cfg.get("max_train_samples")
    max_valid = smoke_cfg.get("max_valid_samples")

    train_ds = tokenized["train"]
    valid_ds = tokenized["validation"]

    if max_train:
        train_ds = train_ds.select(range(min(int(max_train), len(train_ds))))
    if max_valid:
        valid_ds = valid_ds.select(range(min(int(max_valid), len(valid_ds))))

    trainer = Seq2SeqTrainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=valid_ds,
        tokenizer=tokenizer,
        data_collator=data_collator,
        callbacks=[BestCheckpointKeeperCallback(run_dir)],
    )

    # generation 파라미터(평가 시 generate)
    trainer.args.generation_max_length = gen_max_len
    trainer.args.generation_num_beams = num_beams

    return trainer


def run_train(cfg: Dict[str, Any], project_root: Path, run_dir: Path):
    """
    Run a single training job based on config.
    """
    train_path, val_path, test_path = resolve_data_paths(project_root, cfg)
    ds = load_jsonl_splits(train_path, val_path, test_path)

    trainer = build_trainer(cfg, ds, run_dir)

    print("[INFO] Trainer is ready.")
    print(f"[INFO] run_dir = {run_dir}")
    print(f"[INFO] train size = {len(trainer.train_dataset)}")
    print(f"[INFO] valid size = {len(trainer.eval_dataset)}")

    return trainer, run_dir


def main() -> None:
    """
    메인 함수입니다.
    """
    args = parse_args()

    root_dir = Path(__file__).resolve().parent
    project_root = root_dir.parent.parent

    cfg_arg = Path(args.config)
    config_path = (
        (project_root / cfg_arg).resolve()
        if not cfg_arg.is_absolute()
        else cfg_arg.resolve()
    )

    cfg = load_yaml(config_path)

    # run_root = 실험 루트(결과 저장 폴더: exp_001 같은 상위)
    default_run_root = (project_root / require(cfg, "project.output_dir")).resolve()
    run_root = (project_root / args.run_dir).resolve() if args.run_dir else default_run_root
    run_root.mkdir(parents=True, exist_ok=True)

    # run_dir = 이번 실행(1회) 결과 폴더 (run_YYYYmmdd_HHMMSS)
    # resume_from이 있으면 해당 체크포인트가 속한 run_dir로 고정
    if args.resume_from:
        ckpt_path = Path(args.resume_from).resolve()
        run_dir = ckpt_path.parent.parent  # .../run_xxx/checkpoints/checkpoint-####
    else:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = run_root / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=False)

    print(f"[run_dir] {run_dir}")

    trainer, _ = run_train(cfg, project_root, run_dir)

    trainer.train(resume_from_checkpoint=args.resume_from)

    export_dir = run_dir / "export_best_model"
    export_dir.mkdir(parents=True, exist_ok=True)

    trainer.save_model(str(export_dir))
    trainer.save_state()
    print(f"[INFO] export_best_model = {export_dir}")

    # best 기록 확인 출력
    best_record = run_dir / "best" / "best_checkpoint.json"
    if best_record.exists():
        print(f"[INFO] best record saved: {best_record}")
        print(best_record.read_text(encoding="utf-8"))
    else:
        print("[WARN] best record not found. (No evaluation happened or best was not set.)")


if __name__ == "__main__":
    main()
