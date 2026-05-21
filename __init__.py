import importlib.util
import os
import sys
import traceback

VERSION = "1.0.0"
WEB_DIRECTORY = "./web"

# Ensure local custom node files and helper modules are discoverable during package import.
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# Import each node separately so one broken node doesn't stop the suite from loading.
try:
    from .prompt_verify import PromptVerify
    NODE_CLASS_MAPPINGS["Prompt Verify"] = PromptVerify
except Exception as e:
    print(f"[ialhabbal] ERROR importing PromptVerify: {e}")
    traceback.print_exc()

try:
    from .compare import Compare
    NODE_CLASS_MAPPINGS[Compare.NAME] = Compare
except Exception as e:
    print(f"[ialhabbal] ERROR importing Compare: {e}")
    traceback.print_exc()

try:
    from .meta_prompt_extractor import MetaPromptExtractor
    NODE_CLASS_MAPPINGS["MetaPromptExtractor"] = MetaPromptExtractor
    NODE_DISPLAY_NAME_MAPPINGS["MetaPromptExtractor"] = "Meta Prompt Extractor"
except Exception as e:
    print(f"[ialhabbal] ERROR importing MetaPromptExtractor: {e}")
    traceback.print_exc()

try:
    from .Occlusion import OcclusionMask
    NODE_CLASS_MAPPINGS["OcclusionMask"] = OcclusionMask
    NODE_DISPLAY_NAME_MAPPINGS["OcclusionMask"] = "Occlusion Mask (Face Protection for ReActor)"
except Exception as e:
    print(f"[ialhabbal] ERROR importing OcclusionMask: {e}")
    traceback.print_exc()

try:
    from .batch_comfyui_processor import BatchLoadImages
    NODE_CLASS_MAPPINGS["BatchLoadImages"] = BatchLoadImages
    NODE_DISPLAY_NAME_MAPPINGS["BatchLoadImages"] = "Loader for Batch Image Processing"
except Exception as e:
    print(f"[ialhabbal] ERROR importing BatchLoadImages: {e}")
    traceback.print_exc()

try:
    from .photo_lab import PhotoLab
    NODE_CLASS_MAPPINGS["PhotoLab"] = PhotoLab
except Exception as e:
    print(f"[ialhabbal] ERROR importing PhotoLab: {e}")
    traceback.print_exc()

try:
    from .Save_It import Save_It
    NODE_CLASS_MAPPINGS["Save_It"] = Save_It
    NODE_DISPLAY_NAME_MAPPINGS["Save_It"] = "Save_It"
except Exception as e:
    print(f"[ialhabbal] ERROR importing Save_It: {e}")
    traceback.print_exc()

# VLLM nodes
try:
    from .ialhabbal_VLLM import ialhabbal_VLLM, ialhabbal_VLLM_Advanced
    NODE_CLASS_MAPPINGS["ialhabbal_VLLM"] = ialhabbal_VLLM
    NODE_DISPLAY_NAME_MAPPINGS["ialhabbal_VLLM"] = "ialhabbal VLLM"
    NODE_CLASS_MAPPINGS["ialhabbal_VLLM_Advanced"] = ialhabbal_VLLM_Advanced
    NODE_DISPLAY_NAME_MAPPINGS["ialhabbal_VLLM_Advanced"] = "ialhabbal VLLM Advanced"
except Exception as e:
    print(f"[ialhabbal] ERROR importing ialhabbal_VLLM nodes: {e}")
    traceback.print_exc()

try:
    from .ialhabbal_VLLM_GGUF import ialhabbal_VLLM_GGUF, ialhabbal_VLLM_GGUF_Advanced
    NODE_CLASS_MAPPINGS["ialhabbal_VLLM_GGUF"] = ialhabbal_VLLM_GGUF
    NODE_DISPLAY_NAME_MAPPINGS["ialhabbal_VLLM_GGUF"] = "ialhabbal VLLM GGUF"
    NODE_CLASS_MAPPINGS["ialhabbal_VLLM_GGUF_Advanced"] = ialhabbal_VLLM_GGUF_Advanced
    NODE_DISPLAY_NAME_MAPPINGS["ialhabbal_VLLM_GGUF_Advanced"] = "ialhabbal VLLM GGUF Advanced"
except Exception as e:
    print(f"[ialhabbal] ERROR importing ialhabbal_VLLM_GGUF nodes: {e}")
    traceback.print_exc()

try:
    from .ialhabbal_VLLM_PromptEnhancer import ialhabbal_VLLM_PromptEnhancer
    NODE_CLASS_MAPPINGS["ialhabbal_VLLM_PromptEnhancer"] = ialhabbal_VLLM_PromptEnhancer
    NODE_DISPLAY_NAME_MAPPINGS["ialhabbal_VLLM_PromptEnhancer"] = "ialhabbal VLLM Prompt Enhancer"
except Exception as e:
    print(f"[ialhabbal] ERROR importing ialhabbal_VLLM_PromptEnhancer: {e}")
    traceback.print_exc()

try:
    from .ialhabbal_VLLM_GGUF_PromptEnhancer import ialhabbal_VLLM_GGUF_PromptEnhancer
    NODE_CLASS_MAPPINGS["ialhabbal_VLLM_GGUF_PromptEnhancer"] = ialhabbal_VLLM_GGUF_PromptEnhancer
except Exception as e:
    print(f"[ialhabbal] ERROR importing ialhabbal_VLLM_GGUF_PromptEnhancer: {e}")
    traceback.print_exc()

__all__ = [
    "VERSION",
    "WEB_DIRECTORY",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS"
]
