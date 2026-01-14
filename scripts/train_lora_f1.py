"""
Fine-tuning LoRA (PEFT) pour le chatbot F1

Objectif:
- Adapter un modèle de base (ex: LLaMA 3.x) au style et aux connaissances locales
- Utiliser les conversations (memory/*.jsonl), réponses validées et extraits de KB
- Exporter l'adapter LoRA (sans merger) pour un chargement léger

Prérequis:
- Python >=3.10
- GPU CUDA recommandé (possible CPU mais très lent)
- Paquets: transformers, peft, datasets, accelerate

Usage (exemples):
python scripts/train_lora_f1.py --base_model meta-llama/Llama-3.2-1B-Instruct \
  --output_dir ./models/f1-lora \
  --epochs 1 --lr 2e-4 --per_device_train_batch_size 2

Notes:
- Sur Windows, bitsandbytes n'est pas requis; utilisez torch CUDA si dispo.
- Ce script produit un adapter LoRA utilisable dans Transformers; pour Ollama, il faudra merger et convertir en GGUF (pipeline séparé).
"""
import os
import json
import argparse
from pathlib import Path
from typing import List, Dict

from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model


def load_conversations(paths: List[Path]) -> List[Dict]:
    records = []
    for p in paths:
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    records.append(rec)
                except Exception:
                    # support for non-jsonl files
                    try:
                        data = json.load(f)
                        if isinstance(data, list):
                            records.extend(data)
                        else:
                            records.append(data)
                    except Exception:
                        pass
    return records


def build_instruction_dataset(workspace_root: Path) -> List[Dict]:
    """Construit un dataset d'instructions/réponses à partir de la mémoire et de la KB.
    Format simple type Alpaca: {"instruction", "input", "output"}
    """
    memory_dir = workspace_root / "memory"
    kb_dir = workspace_root / "knowledge_base"

    conv_paths = [
        memory_dir / "all_conversations.jsonl",
        workspace_root / "f1_conversations.json",
    ]
    conversations = load_conversations(conv_paths)

    samples = []
    # Conversations: prendre paires question/réponse récentes
    for rec in conversations:
        q = rec.get("user") or rec.get("question") or rec.get("prompt")
        a = rec.get("assistant") or rec.get("response") or rec.get("answer")
        if q and a and len(q) > 5 and len(a) > 20:
            samples.append({"instruction": q, "input": "", "output": a})

    # KB: créer des QA synthétiques courts (contexte -> résumé)
    kb_md = []
    for p in kb_dir.glob("*.md"):
        try:
            text = p.read_text(encoding="utf-8")
            if len(text) > 200:
                kb_md.append((p.name, text))
        except Exception:
            pass

    for name, text in kb_md:
        prompt = f"Résume fidèlement ce contenu F1 ({name}) en français, format concis avec sources si présentes."
        target = text[:1200]
        samples.append({"instruction": prompt, "input": "", "output": target})

    return samples


def format_sample(sample: Dict, tokenizer: AutoTokenizer) -> Dict:
    # Format type: [INST] instruction [/INST] output
    instr = sample["instruction"].strip()
    output = sample["output"].strip()
    prompt = f"<s>[INST] {instr} [/INST] {output}</s>"
    tokens = tokenizer(
        prompt,
        truncation=True,
        max_length=2048,
    )
    tokens["labels"] = tokens["input_ids"].copy()
    return tokens


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", type=str, required=True,
                        help="HF model id ex: meta-llama/Llama-3.2-1B-Instruct")
    parser.add_argument("--output_dir", type=str, default="./models/f1-lora")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--per_device_train_batch_size", type=int, default=2)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parents[1]
    samples = build_instruction_dataset(workspace_root)
    if not samples:
        raise RuntimeError("Aucun échantillon trouvé pour l'entraînement.")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    ds = Dataset.from_list(samples)
    tokenized = ds.map(lambda s: format_sample(s, tokenizer), remove_columns=list(ds.features))

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=None,
        device_map="auto",
    )

    lora_cfg = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        logging_steps=50,
        save_strategy="epoch",
        bf16=False,
        fp16=False,
        seed=args.seed,
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=collator,
    )

    trainer.train()
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    print(f"LoRA adapter sauvegardé dans: {args.output_dir}")
    print("\nÉtapes suivantes (Ollama):\n- Fusionner l'adapter dans le modèle base (script de merge PEFT)\n- Convertir en GGUF (llama.cpp)\n- Créer un modèle Ollama via 'ollama create'\n")


if __name__ == "__main__":
    main()
