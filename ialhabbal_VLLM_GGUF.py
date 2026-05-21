# ialhabbal_VLLM (GGUF)
# GGUF nodes powered by llama.cpp for Qwen-VL models, including Qwen3-VL and Qwen2.5-VL.
# Provides vision-capable GGUF inference and prompt execution.
#
# Models are loaded via llama-cpp-python and configured through gguf_models.json.
# This integration script follows GPL-3.0 License.
# When using or modifying this code, please respect both the original model licenses
# and this integration's license terms.
#
# Source: https://github.com/ialhabbal/ComfyUI-ialhabbal

import base64
import gc
import io
import inspect
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from huggingface_hub import hf_hub_download
from PIL import Image

import folder_paths
from OutputCleaner import OutputCleanConfig, clean_model_output

NODE_DIR = Path(__file__).parent
CONFIG_PATH = NODE_DIR / "hf_models.json"
SYSTEM_PROMPTS_PATH = NODE_DIR / "System_Prompts.json"
GGUF_CONFIG_PATH = NODE_DIR / "gguf_models.json"


def _load_prompt_config():
    preset_prompts = ["🖼️ Detailed Description"]
    system_prompts: dict[str, str] = {}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
        preset_prompts = data.get("_preset_prompts") or preset_prompts
        system_prompts = data.get("_system_prompts") or system_prompts
    except Exception as exc:
        print(f"[ialhabbal_VLLM] Config load failed: {exc}")

    try:
        with open(SYSTEM_PROMPTS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
        ialhabbal_vllm_prompts = data.get("ialhabbal_vllm") or {}
        preset_override = data.get("_preset_prompts") or []
        if isinstance(ialhabbal_vllm_prompts, dict) and ialhabbal_vllm_prompts:
            system_prompts = ialhabbal_vllm_prompts
        if isinstance(preset_override, list) and preset_override:
            preset_prompts = preset_override
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"[ialhabbal_VLLM] System prompts load failed: {exc}")

    return preset_prompts, system_prompts


PRESET_PROMPTS, SYSTEM_PROMPTS = _load_prompt_config()


@dataclass(frozen=True)
class GGUFVLResolved:
    display_name: str
    repo_id: str | None
    alt_repo_ids: list[str]
    author: str | None
    repo_dirname: str
    model_filename: str
    mmproj_filename: str | None
    context_length: int
    image_max_tokens: int
    n_batch: int
    gpu_layers: int
    top_k: int
    pool_size: int


def _resolve_base_dir(base_dir_value: str) -> Path:
    base_dir = Path(base_dir_value)
    if base_dir.is_absolute():
        return base_dir
    return Path(folder_paths.models_dir) / base_dir


def _safe_dirname(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "unknown"
    return "".join(ch for ch in value if ch.isalnum() or ch in "._- ").strip() or "unknown"


def _model_name_to_filename_candidates(model_name: str) -> set[str]:
    raw = (model_name or "").strip()
    if not raw:
        return set()
    candidates = {raw, f"{raw}.gguf"}
    if " / " in raw:
        tail = raw.split(" / ", 1)[1].strip()
        candidates.update({tail, f"{tail}.gguf"})
    if "/" in raw:
        tail = raw.rsplit("/", 1)[-1].strip()
        candidates.update({tail, f"{tail}.gguf"})
    return candidates


def _load_gguf_vl_catalog():
    if not GGUF_CONFIG_PATH.exists():
        return {"base_dir": "LLM/GGUF", "models": {}}
    try:
        with open(GGUF_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
    except Exception as exc:
        print(f"[ialhabbal_VLLM] gguf_models.json load failed: {exc}")
        return {"base_dir": "LLM/GGUF", "models": {}}

    base_dir = data.get("base_dir") or "LLM/GGUF"

    flattened: dict[str, dict] = {}

    # Support multiple possible keys and legacy/case variants so different
    # `gguf_models.json` formats (including third-party examples) are accepted.
    repos: dict = {}
    for key in ("ialhabbal_VLLM_model", "Qwen_model", "qwen_model", "vl_repos", "repos", "models"):
        val = data.get(key)
        if isinstance(val, dict):
            repos.update(val)

    seen_display_names: set[str] = set()
    for repo_key, repo in repos.items():
        if not isinstance(repo, dict):
            continue
        author = repo.get("author") or repo.get("publisher")
        repo_name = repo.get("repo_name") or repo.get("repo_name_override") or repo_key
        repo_id = repo.get("repo_id") or (f"{author}/{repo_name}" if author and repo_name else None)
        alt_repo_ids = repo.get("alt_repo_ids") or []

        defaults = repo.get("defaults") or {}
        mmproj_file = repo.get("mmproj_file")
        model_files = repo.get("model_files") or []

        for model_file in model_files:
            display = Path(model_file).name
            if display in seen_display_names:
                display = f"{display} ({repo_key})"
            seen_display_names.add(display)
            flattened[display] = {
                **defaults,
                "author": author,
                "repo_dirname": repo_name,
                "repo_id": repo_id,
                "alt_repo_ids": alt_repo_ids,
                "filename": model_file,
                "mmproj_filename": mmproj_file,
            }

    legacy_models = data.get("models") or {}
    for name, entry in legacy_models.items():
        if isinstance(entry, dict):
            flattened[name] = entry

    return {"base_dir": base_dir, "models": flattened}


GGUF_VL_CATALOG = _load_gguf_vl_catalog()


def _filter_kwargs_for_callable(fn, kwargs: dict) -> dict:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return dict(kwargs)

    params = list(sig.parameters.values())
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
        return dict(kwargs)

    allowed: set[str] = set()
    for p in params:
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            allowed.add(p.name)
    return {k: v for k, v in kwargs.items() if k in allowed}


def _tensor_to_base64_png(tensor) -> str | None:
    if tensor is None:
        return None
    if tensor.ndim == 4:
        tensor = tensor[0]
    array = (tensor * 255).clamp(0, 255).to(torch.uint8).cpu().numpy()
    pil_img = Image.fromarray(array, mode="RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _sample_video_frames(video, frame_count: int):
    if video is None:
        return []
    if video.ndim != 4:
        return [video]
    total = int(video.shape[0])
    frame_count = max(int(frame_count), 1)
    if total <= frame_count:
        return [video[i] for i in range(total)]
    idx = np.linspace(0, total - 1, frame_count, dtype=int)
    return [video[i] for i in idx]


def _pick_device(device_choice: str) -> str:
    if device_choice == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    if device_choice.startswith("cuda") and torch.cuda.is_available():
        return "cuda"
    if device_choice == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _download_single_file(repo_ids: list[str], filename: str, target_path: Path):
    if target_path.exists():
        print(f"[ialhabbal_VLLM] Using cached file: {target_path}")
        return
    raise FileNotFoundError(f"[ialhabbal_VLLM] GGUF model not found locally and download disabled: {target_path}")


def _resolve_model_entry(model_name: str) -> GGUFVLResolved:
    all_models = GGUF_VL_CATALOG.get("models") or {}
    entry = all_models.get(model_name) or {}
    if not entry:
        wanted = _model_name_to_filename_candidates(model_name)
        for candidate in all_models.values():
            filename = candidate.get("filename")
            if filename and Path(filename).name in wanted:
                entry = candidate
                break

    repo_id = entry.get("repo_id")
    alt_repo_ids = entry.get("alt_repo_ids") or []

    author = entry.get("author") or entry.get("publisher")
    repo_dirname = entry.get("repo_dirname") or (repo_id.split("/")[-1] if isinstance(repo_id, str) and "/" in repo_id else model_name)

    model_filename = entry.get("filename")
    mmproj_filename = entry.get("mmproj_filename")

    if not model_filename:
        raise ValueError(f"[ialhabbal_VLLM] gguf_vl_models.json entry missing 'filename' for: {model_name}")

    def _int(name: str, default: int) -> int:
        value = entry.get(name, default)
        try:
            return int(value)
        except Exception:
            return default

    return GGUFVLResolved(
        display_name=model_name,
        repo_id=repo_id,
        alt_repo_ids=[str(x) for x in alt_repo_ids if x],
        author=str(author) if author else None,
        repo_dirname=_safe_dirname(str(repo_dirname)),
        model_filename=str(model_filename),
        mmproj_filename=str(mmproj_filename) if mmproj_filename else None,
        context_length=_int("context_length", 8192),
        image_max_tokens=_int("image_max_tokens", 4096),
        n_batch=_int("n_batch", 512),
        gpu_layers=_int("gpu_layers", -1),
        top_k=_int("top_k", 0),
        pool_size=_int("pool_size", 4194304),
    )


class ialhabbal_VLLMGGUFBase:
    def __init__(self):
        self.llm = None
        self.chat_handler = None
        self.current_signature = None

    def clear(self):
        self.llm = None
        self.chat_handler = None
        self.current_signature = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _load_backend(self):
        try:
            from llama_cpp import Llama  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                "[ialhabbal_VLLM] llama_cpp is not available. Install the GGUF vision dependency first. See docs/GGUF_MANUAL_INSTALL.md"
            ) from exc

    def _load_model(
        self,
        model_name: str,
        device: str,
        ctx: int | None,
        n_batch: int | None,
        gpu_layers: int | None,
        image_max_tokens: int | None,
        top_k: int | None,
        pool_size: int | None,
    ):
        self._load_backend()

        resolved = _resolve_model_entry(model_name)
        is_gemma = "gemma" in model_name.lower() or (resolved.author and "google" in resolved.author.lower())
        self.is_gemma = is_gemma
        base_dir = _resolve_base_dir(GGUF_VL_CATALOG.get("base_dir") or "llm/GGUF")

        author_dir = _safe_dirname(resolved.author or "")
        repo_dir = _safe_dirname(resolved.repo_dirname)
        target_dir = base_dir / author_dir / repo_dir

        model_path = target_dir / Path(resolved.model_filename).name
        mmproj_path = target_dir / Path(resolved.mmproj_filename).name if resolved.mmproj_filename else None

        # Fall back to path without author subdirectory if not found under author subfolder
        if not model_path.exists() and author_dir and author_dir != "unknown":
            no_author_target_dir = base_dir / repo_dir
            no_author_model_path = no_author_target_dir / Path(resolved.model_filename).name
            if no_author_model_path.exists():
                target_dir = no_author_target_dir
                model_path = no_author_model_path
                mmproj_path = target_dir / Path(resolved.mmproj_filename).name if resolved.mmproj_filename else None

        # Final fallback: search the base_dir recursively for the model filename
        if not model_path.exists():
            fname = Path(resolved.model_filename).name
            print(f"[ialhabbal_VLLM] Model not found at expected path: {model_path}")
            print(f"[ialhabbal_VLLM] Searching for '{fname}' under base_dir: {base_dir}")
            try:
                matches = list(base_dir.rglob(fname))
            except Exception:
                matches = []
            # Also search the top-level models_dir if base_dir is relative and the first search failed
            if not matches:
                try:
                    top_models_dir = Path(folder_paths.models_dir)
                    if top_models_dir.exists() and top_models_dir != base_dir:
                        print(f"[ialhabbal_VLLM] Also searching top-level models_dir: {top_models_dir}")
                        matches = list(top_models_dir.rglob(fname))
                except Exception:
                    pass
            if matches:
                model_path = matches[0]
                target_dir = model_path.parent
                print(f"[ialhabbal_VLLM] Found model at: {model_path}")
                if resolved.mmproj_filename:
                    mmproj_candidate = target_dir / Path(resolved.mmproj_filename).name
                    if mmproj_candidate.exists():
                        mmproj_path = mmproj_candidate
                        print(f"[ialhabbal_VLLM] Found mmproj at: {mmproj_path}")

        repo_ids: list[str] = []
        if resolved.repo_id:
            repo_ids.append(resolved.repo_id)
        repo_ids.extend(resolved.alt_repo_ids)

        if not model_path.exists():
            if not repo_ids:
                raise FileNotFoundError(f"[ialhabbal_VLLM] GGUF model not found locally and no repo_id provided: {model_path}")
            _download_single_file(repo_ids, resolved.model_filename, model_path)

        if mmproj_path is not None and not mmproj_path.exists():
            if not repo_ids:
                raise FileNotFoundError(f"[ialhabbal_VLLM] mmproj not found locally and no repo_id provided: {mmproj_path}")
            _download_single_file(repo_ids, resolved.mmproj_filename, mmproj_path)

        device_kind = _pick_device(device)

        n_ctx = int(ctx) if ctx is not None else resolved.context_length
        n_batch_val = int(n_batch) if n_batch is not None else resolved.n_batch
        top_k_val = int(top_k) if top_k is not None else resolved.top_k
        pool_size_val = int(pool_size) if pool_size is not None else resolved.pool_size

        if device_kind == "cuda":
            n_gpu_layers = int(gpu_layers) if gpu_layers is not None else resolved.gpu_layers
        else:
            n_gpu_layers = 0

        img_max = int(image_max_tokens) if image_max_tokens is not None else resolved.image_max_tokens

        has_mmproj = mmproj_path is not None and mmproj_path.exists()

        signature = (
            str(model_path),
            str(mmproj_path) if has_mmproj else "",
            n_ctx,
            n_batch_val,
            n_gpu_layers,
            img_max,
            top_k_val,
            pool_size_val,
        )
        if self.llm is not None and self.current_signature == signature:
            return

        self.clear()

        from llama_cpp import Llama

        self.chat_handler = None
        if has_mmproj:
            handler_cls = None
            if is_gemma:
                # Try Gemma 4/3/Pali/Nano ChatHandlers
                if "gemma-4" in model_name.lower() or "gemma4" in model_name.lower():
                    try:
                        from llama_cpp.llama_chat_format import Gemma4ChatHandler
                        handler_cls = Gemma4ChatHandler
                    except ImportError:
                        try:
                            from llama_cpp.llama_chat_format import Gemma4VLChatHandler
                            handler_cls = Gemma4VLChatHandler
                        except ImportError:
                            pass
                if handler_cls is None:
                    try:
                        from llama_cpp.llama_chat_format import Gemma3ChatHandler
                        handler_cls = Gemma3ChatHandler
                    except ImportError:
                        try:
                            from llama_cpp.llama_chat_format import Gemma3VLChatHandler
                            handler_cls = Gemma3VLChatHandler
                        except ImportError:
                            try:
                                from llama_cpp.llama_chat_format import NanoGemmaChatHandler
                                handler_cls = NanoGemmaChatHandler
                            except ImportError:
                                try:
                                    from llama_cpp.llama_chat_format import PaliGemmaChatHandler
                                    handler_cls = PaliGemmaChatHandler
                                except ImportError:
                                    pass
                if handler_cls is None:
                    print(
                        "[ialhabbal_VLLM] Info: Gemma model selected but no Gemma-specific ChatHandler found in llama_cpp. "
                        "Using fallback Qwen/VL chat handler for multimodal support."
                    )

            if handler_cls is None:
                try:
                    from llama_cpp.llama_chat_format import Qwen3VLChatHandler

                    handler_cls = Qwen3VLChatHandler
                except ImportError:
                    try:
                        from llama_cpp.llama_chat_format import Qwen25VLChatHandler

                        handler_cls = Qwen25VLChatHandler
                    except ImportError:
                        raise RuntimeError(
                            "[ialhabbal_VLLM] Missing chat handler in llama_cpp. Install the correct fork/wheel supporting Gemma/Qwen VL. See docs/GGUF_MANUAL_INSTALL.md"
                        )

            mmproj_kwargs = {
                "clip_model_path": str(mmproj_path),
                "image_max_tokens": img_max,
                "force_reasoning": False,
                "verbose": False,
            }

            # Try to filter kwargs by signature. If the signature indicates
            # VAR_KEYWORD we still use a conservative whitelist to avoid passing
            # unsupported args to handlers that validate kwargs internally.
            try:
                sig = inspect.signature(getattr(handler_cls, "__init__", handler_cls))
            except Exception:
                sig = None

            if sig is None:
                filtered = {k: v for k, v in mmproj_kwargs.items()}
            else:
                params = list(sig.parameters.values())
                if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
                    # conservative whitelist
                    whitelist = {"clip_model_path", "image_max_tokens", "verbose", "force_reasoning"}
                    filtered = {k: v for k, v in mmproj_kwargs.items() if k in whitelist}
                else:
                    filtered = _filter_kwargs_for_callable(getattr(handler_cls, "__init__", handler_cls), mmproj_kwargs)

            if "image_max_tokens" not in filtered:
                print(
                    "[ialhabbal_VLLM] Warning: installed llama_cpp chat handler does not support image_max_tokens; "
                    "image token budget will be controlled by ctx only."
                )

            # Try instantiation; if TypeError arises about unexpected kwargs,
            # strip those keys and retry once.
            try:
                self.chat_handler = handler_cls(**filtered)
            except TypeError as te:
                msg = str(te)
                # detect unexpected keyword(s) and remove them
                bad_keys = []
                try:
                    # simple parse: look for occurrences like "'force_reasoning'"
                    for key in list(filtered.keys()):
                        if f"'{key}'" in msg or f'"{key}"' in msg or key in msg:
                            bad_keys.append(key)
                except Exception:
                    bad_keys = []

                if bad_keys:
                    for k in bad_keys:
                        filtered.pop(k, None)
                    try:
                        self.chat_handler = handler_cls(**filtered)
                    except Exception:
                        raise
                else:
                    raise

        llm_kwargs = {
            "model_path": str(model_path),
            "n_ctx": n_ctx,
            "n_gpu_layers": n_gpu_layers,
            "n_batch": n_batch_val,
            "swa_full": True,
            "verbose": False,
            "pool_size": pool_size_val,
            "top_k": top_k_val,
        }
        if has_mmproj and self.chat_handler is not None:
            llm_kwargs["chat_handler"] = self.chat_handler
            llm_kwargs["image_min_tokens"] = 1024
            llm_kwargs["image_max_tokens"] = img_max

        print(f"[ialhabbal_VLLM] Loading GGUF: {model_path.name} (device={device_kind}, gpu_layers={n_gpu_layers}, ctx={n_ctx})")
        llm_kwargs_filtered = _filter_kwargs_for_callable(getattr(Llama, "__init__", Llama), llm_kwargs)
        if has_mmproj and self.chat_handler is not None and "chat_handler" not in llm_kwargs_filtered:
            print(
                "[ialhabbal_VLLM] Warning: installed llama_cpp Llama() does not accept chat_handler; images will be ignored. "
                "Update llama-cpp-python to a multimodal-capable build."
            )
        if device_kind == "cuda" and n_gpu_layers == 0:
            print("[ialhabbal_VLLM] Warning: device=cuda selected but n_gpu_layers=0; model will run on CPU.")

        # Pre-flight diagnostics for model file
        try:
            stat = model_path.stat()
            size = stat.st_size
        except Exception as exc:
            print(f"[ialhabbal_VLLM] Error accessing model file: {model_path} -> {exc}")
            raise

        if size == 0:
            raise ValueError(f"[ialhabbal_VLLM] Model file is empty: {model_path}")

        header_bytes = b""
        try:
            with open(model_path, "rb") as fh:
                header_bytes = fh.read(64)
        except Exception as exc:
            print(f"[ialhabbal_VLLM] Unable to read model file header: {exc}")

        if header_bytes and not header_bytes.startswith(b"GGUF"):
            print(f"[ialhabbal_VLLM] Warning: model file header does not start with 'GGUF' (first bytes: {header_bytes[:8]!r})")

        # Attempt to instantiate Llama and capture detailed errors
        def _try_instantiate(kwargs, allow_fallback: bool = True):
            try:
                self.llm = Llama(**kwargs)
                self.current_signature = signature
                return True
            except Exception as exc:
                print(f"[ialhabbal_VLLM] Llama() failed with kwargs: {list(kwargs.keys())}")
                print(f"[ialhabbal_VLLM] Llama() raised: {exc}")
                if allow_fallback and "chat_handler" in kwargs:
                    print("[ialhabbal_VLLM] Retrying without chat_handler/image args to allow model-only load.")
                    fallback_kwargs = {k: v for k, v in kwargs.items() if k not in {"chat_handler", "image_min_tokens", "image_max_tokens"}}
                    self.chat_handler = None
                    return _try_instantiate(fallback_kwargs, allow_fallback=False)
                return False

        if not _try_instantiate(llm_kwargs_filtered, allow_fallback=True):
            print(f"[ialhabbal_VLLM] Failed to instantiate Llama for model: {model_path}")
            try:
                import importlib.metadata as _md
                ver = _md.version("llama-cpp-python")
            except Exception:
                try:
                    import llama_cpp as _lc
                    ver = getattr(_lc, "__version__", "(unknown)")
                except Exception:
                    ver = "(unknown)"
            print(f"[ialhabbal_VLLM] llama-cpp-python version: {ver}")
            print(f"[ialhabbal_VLLM] Model file size: {size} bytes")
            if header_bytes:
                hex_preview = header_bytes[:64].hex()
                print(f"[ialhabbal_VLLM] Model file header (hex): {hex_preview}")
            raise

    def _invoke(
        self,
        system_prompt: str,
        user_prompt: str,
        images_b64: list[str],
        max_tokens: int,
        temperature: float,
        top_p: float,
        repetition_penalty: float,
        seed: int,
    ) -> str:
        if images_b64:
            content = [{"type": "text", "text": user_prompt}]
            for img in images_b64:
                if not img:
                    continue
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        stop_tokens = ["<end_of_turn>", "<eos>"] if getattr(self, "is_gemma", False) else ["<|im_end|>", "<|im_start|>"]
        start = time.perf_counter()
        result = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            repeat_penalty=float(repetition_penalty),
            seed=int(seed),
            stop=stop_tokens,
        )
        elapsed = max(time.perf_counter() - start, 1e-6)

        usage = result.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        if isinstance(completion_tokens, int) and completion_tokens > 0:
            tok_s = completion_tokens / elapsed
            if isinstance(prompt_tokens, int) and prompt_tokens >= 0:
                print(
                    f"[ialhabbal_VLLM] Tokens: prompt={prompt_tokens}, completion={completion_tokens}, "
                    f"time={elapsed:.2f}s, speed={tok_s:.2f} tok/s"
                )
            else:
                print(f"[ialhabbal_VLLM] Tokens: completion={completion_tokens}, time={elapsed:.2f}s, speed={tok_s:.2f} tok/s")

        content = (result.get("choices") or [{}])[0].get("message", {}).get("content", "")
        cleaned = clean_model_output(str(content or ""), OutputCleanConfig(mode="text"))
        return cleaned.strip()

    def run(
        self,
        model_name: str,
        preset_prompt: str,
        custom_prompt: str,
        image,
        video,
        frame_count: int,
        max_tokens: int,
        temperature: float,
        top_p: float,
        repetition_penalty: float,
        seed: int,
        keep_model_loaded: bool,
        device: str,
        ctx: int | None,
        n_batch: int | None,
        gpu_layers: int | None,
        image_max_tokens: int | None,
        top_k: int | None,
        pool_size: int | None,
    ):
        torch.manual_seed(int(seed))

        prompt = SYSTEM_PROMPTS.get(preset_prompt, preset_prompt)
        if custom_prompt and custom_prompt.strip():
            prompt = custom_prompt.strip()

        images_b64: list[str] = []
        if image is not None:
            img = _tensor_to_base64_png(image)
            if img:
                images_b64.append(img)
        if video is not None:
            for frame in _sample_video_frames(video, int(frame_count)):
                img = _tensor_to_base64_png(frame)
                if img:
                    images_b64.append(img)

        try:
            self._load_model(
                model_name=model_name,
                device=device,
                ctx=ctx,
                n_batch=n_batch,
                gpu_layers=gpu_layers,
                image_max_tokens=image_max_tokens,
                top_k=top_k,
                pool_size=pool_size,
            )
            if images_b64 and self.chat_handler is None:
                print("[ialhabbal_VLLM] Warning: images provided but this model entry has no mmproj_file; images will be ignored")
            text = self._invoke(
                system_prompt=(
                    "You are a helpful vision-language assistant. "
                    "Answer directly with the final answer only. No <think> and no reasoning."
                ),
                user_prompt=prompt,
                images_b64=images_b64 if self.chat_handler is not None else [],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                seed=seed,
            )
            return (text,)
        finally:
            if not keep_model_loaded:
                self.clear()


class ialhabbal_VLLM_GGUF(ialhabbal_VLLMGGUFBase):
    @classmethod
    def INPUT_TYPES(cls):
        all_models = GGUF_VL_CATALOG.get("models") or {}
        model_keys = sorted([key for key, entry in all_models.items() if (entry or {}).get("mmproj_filename")]) or ["(edit gguf_models.json)"]
        default_model = model_keys[0]

        prompts = PRESET_PROMPTS or ["🖼️ Detailed Description"]
        preferred_prompt = "🖼️ Detailed Description"
        default_prompt = preferred_prompt if preferred_prompt in prompts else prompts[0]

        return {
            "required": {
                "model_name": (model_keys, {"default": default_model}),
                "preset_prompt": (prompts, {"default": default_prompt}),
                "custom_prompt": ("STRING", {"default": "", "multiline": True}),
                "max_tokens": ("INT", {"default": 512, "min": 64, "max": 2048}),
                "keep_model_loaded": ("BOOLEAN", {"default": True}),
                "seed": ("INT", {"default": 1, "min": 1, "max": 2**32 - 1}),
            },
            "optional": {
                "image": ("IMAGE",),
                "video": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("RESPONSE",)
    FUNCTION = "process"
    CATEGORY = "🧪ialhabbal_VLLM"

    def process(
        self,
        model_name,
        preset_prompt,
        custom_prompt,
        max_tokens,
        keep_model_loaded,
        seed,
        image=None,
        video=None,
    ):
        return self.run(
            model_name=model_name,
            preset_prompt=preset_prompt,
            custom_prompt=custom_prompt,
            image=image,
            video=video,
            frame_count=16,
            max_tokens=max_tokens,
            temperature=0.6,
            top_p=0.9,
            repetition_penalty=1.2,
            seed=seed,
            keep_model_loaded=keep_model_loaded,
            device="auto",
            ctx=None,
            n_batch=None,
            gpu_layers=None,
            image_max_tokens=None,
            top_k=None,
            pool_size=None,
        )


class ialhabbal_VLLM_GGUF_Advanced(ialhabbal_VLLMGGUFBase):
    @classmethod
    def INPUT_TYPES(cls):
        all_models = GGUF_VL_CATALOG.get("models") or {}
        model_keys = sorted([key for key, entry in all_models.items() if (entry or {}).get("mmproj_filename")]) or ["(edit gguf_models.json)"]
        default_model = model_keys[0]

        prompts = PRESET_PROMPTS or ["🖼️ Detailed Description"]
        preferred_prompt = "🖼️ Detailed Description"
        default_prompt = preferred_prompt if preferred_prompt in prompts else prompts[0]

        num_gpus = torch.cuda.device_count()
        gpu_list = [f"cuda:{i}" for i in range(num_gpus)]
        device_options = ["auto", "cpu", "mps"] + gpu_list

        return {
            "required": {
                "model_name": (model_keys, {"default": default_model}),
                "device": (device_options, {"default": "auto"}),
                "preset_prompt": (prompts, {"default": default_prompt}),
                "custom_prompt": ("STRING", {"default": "", "multiline": True}),
                "max_tokens": ("INT", {"default": 512, "min": 64, "max": 4096}),
                "temperature": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 2.0}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0}),
                "repetition_penalty": ("FLOAT", {"default": 1.2, "min": 0.5, "max": 2.0}),
                "frame_count": ("INT", {"default": 16, "min": 1, "max": 64}),
                "ctx": ("INT", {"default": 8192, "min": 1024, "max": 262144, "step": 512}),
                "n_batch": ("INT", {"default": 512, "min": 64, "max": 32768, "step": 64}),
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 200}),
                "image_max_tokens": ("INT", {"default": 4096, "min": 256, "max": 1024000, "step": 256}),
                "top_k": ("INT", {"default": 0, "min": 0, "max": 32768}),
                "pool_size": ("INT", {"default": 4194304, "min": 1048576, "max": 10485760, "step": 524288}),
                "keep_model_loaded": ("BOOLEAN", {"default": True}),
                "seed": ("INT", {"default": 1, "min": 1, "max": 2**32 - 1}),
            },
            "optional": {
                "image": ("IMAGE",),
                "video": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("RESPONSE",)
    FUNCTION = "process"
    CATEGORY = "🧪ialhabbal_VLLM"

    def process(
        self,
        model_name,
        device,
        preset_prompt,
        custom_prompt,
        max_tokens,
        temperature,
        top_p,
        repetition_penalty,
        frame_count,
        ctx,
        n_batch,
        gpu_layers,
        image_max_tokens,
        top_k,
        pool_size,
        keep_model_loaded,
        seed,
        image=None,
        video=None,
    ):
        return self.run(
            model_name=model_name,
            preset_prompt=preset_prompt,
            custom_prompt=custom_prompt,
            image=image,
            video=video,
            frame_count=frame_count,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            seed=seed,
            keep_model_loaded=keep_model_loaded,
            device=device,
            ctx=ctx,
            n_batch=n_batch,
            gpu_layers=gpu_layers,
            image_max_tokens=image_max_tokens,
            top_k=top_k,
            pool_size=pool_size,
        )


NODE_CLASS_MAPPINGS = {
    "ialhabbal_VLLM_GGUF": ialhabbal_VLLM_GGUF,
    "ialhabbal_VLLM_GGUF_Advanced": ialhabbal_VLLM_GGUF_Advanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ialhabbal_VLLM_GGUF": "ialhabbal_VLLM (GGUF)",
    "ialhabbal_VLLM_GGUF_Advanced": "ialhabbal_VLLM Advanced (GGUF)",
}
