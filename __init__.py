import traceback

VERSION = "0.0.1"
WEB_DIRECTORY = "./web"

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

__all__ = ["VERSION", "WEB_DIRECTORY", "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
