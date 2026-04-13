#!/usr/bin/env python3
"""Download ASR/LLM models for MeetScribe.

Usage:
    python scripts/download_models.py --engine parakeet-vi
    python scripts/download_models.py --engine faster-whisper --size large-v3
    python scripts/download_models.py --engine vibevoice --quantization 4bit
    python scripts/download_models.py --engine phowhisper --size large
    python scripts/download_models.py --all
"""

import argparse
import os
import sys

MODELS = {
    "parakeet-vi": {
        "type": "nemo",
        "model_name": "nvidia/parakeet-ctc-0.6b-vi",
        "description": "NVIDIA Parakeet Vietnamese ASR (600M, ~2GB VRAM)",
    },
    "faster-whisper": {
        "type": "faster-whisper",
        "sizes": ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"],
        "default_size": "large-v3",
        "description": "CTranslate2 Whisper (English primary)",
    },
    "vibevoice": {
        "type": "huggingface",
        "model_name": "microsoft/VibeVoice-ASR",
        "quantizations": ["bf16", "8bit", "4bit"],
        "default_quantization": "4bit",
        "description": "Microsoft VibeVoice-ASR 7B (POST mode)",
    },
    "phowhisper": {
        "type": "huggingface",
        "sizes": ["tiny", "base", "small", "medium", "large"],
        "model_prefix": "vinai/PhoWhisper-",
        "default_size": "large",
        "description": "VinAI PhoWhisper Vietnamese (fallback)",
    },
    "diart": {
        "type": "huggingface",
        "models": ["pyannote/segmentation-3.0", "pyannote/embedding"],
        "description": "PyAnnote models for diart diarization",
    },
    "embeddings": {
        "type": "sentence-transformers",
        "model_name": "all-MiniLM-L6-v2",
        "description": "Sentence embeddings for semantic search",
    },
}


def download_nemo(model_name: str):
    print(f"Downloading NeMo model: {model_name}")
    import nemo.collections.asr as nemo_asr
    model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_name)
    print(f"✓ {model_name} downloaded and cached")
    del model


def download_faster_whisper(size: str):
    print(f"Downloading faster-whisper model: {size}")
    from faster_whisper import WhisperModel
    model = WhisperModel(size, device="cpu", compute_type="int8")
    print(f"✓ faster-whisper {size} downloaded and cached")
    del model


def download_huggingface(model_name: str, **kwargs):
    print(f"Downloading HuggingFace model: {model_name}")
    from huggingface_hub import snapshot_download
    path = snapshot_download(model_name)
    print(f"✓ {model_name} downloaded to {path}")


def download_sentence_transformers(model_name: str):
    print(f"Downloading sentence-transformers: {model_name}")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    print(f"✓ {model_name} downloaded and cached")
    del model


def main():
    parser = argparse.ArgumentParser(description="Download MeetScribe models")
    parser.add_argument("--engine", choices=list(MODELS.keys()), help="Engine to download")
    parser.add_argument("--size", help="Model size (for multi-size engines)")
    parser.add_argument("--quantization", help="Quantization (for VibeVoice: bf16/8bit/4bit)")
    parser.add_argument("--all", action="store_true", help="Download all models")
    parser.add_argument("--list", action="store_true", help="List available models")
    args = parser.parse_args()

    if args.list:
        for name, info in MODELS.items():
            print(f"  {name:20s} — {info['description']}")
        return

    if args.all:
        engines = list(MODELS.keys())
    elif args.engine:
        engines = [args.engine]
    else:
        parser.print_help()
        return

    for engine in engines:
        info = MODELS[engine]
        print(f"\n{'='*60}")
        print(f"Engine: {engine} — {info['description']}")
        print(f"{'='*60}")

        try:
            if info["type"] == "nemo":
                download_nemo(info["model_name"])
            elif info["type"] == "faster-whisper":
                size = args.size or info.get("default_size", "base")
                download_faster_whisper(size)
            elif info["type"] == "huggingface":
                if "models" in info:
                    for m in info["models"]:
                        download_huggingface(m)
                elif "model_prefix" in info:
                    size = args.size or info.get("default_size", "base")
                    download_huggingface(f"{info['model_prefix']}{size}")
                else:
                    download_huggingface(info["model_name"])
            elif info["type"] == "sentence-transformers":
                download_sentence_transformers(info["model_name"])
        except Exception as e:
            print(f"✗ Failed to download {engine}: {e}")
            continue

    print("\n✓ All downloads complete!")


if __name__ == "__main__":
    main()
