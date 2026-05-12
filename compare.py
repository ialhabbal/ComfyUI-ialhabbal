from nodes import PreviewImage


class Compare(PreviewImage):
    """A simple Compare node that exposes two image inputs and returns UI payloads
    that the ComfyUI frontend can display. This backend focuses on saving images and
    returning both a combined `images` array (for default preview) and separate
    `a_images` / `b_images` arrays (for any custom frontend widgets).
    """

    NAME = "Compare"
    CATEGORY = "Custom"
    FUNCTION = "compare_images"
    DESCRIPTION = "Compares two images with a hover slider (frontend optional)."

    @classmethod
    def INPUT_TYPES(cls):  # pylint: disable = invalid-name, missing-function-docstring
        return {
            "required": {},
            "optional": {
                "image_a": ("IMAGE",),
                "image_b": ("IMAGE",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    def compare_images(self, image_a=None, image_b=None, filename_prefix="compare.", prompt=None, extra_pnginfo=None):
        # We'll return a structure compatible with ComfyUI preview nodes.
        result = {"ui": {"images": [], "a_images": [], "b_images": []}}

        if image_a is not None and len(image_a) > 0:
            a_saved = self.save_images(image_a, filename_prefix + "a.", prompt, extra_pnginfo)["ui"]["images"]
            result["ui"]["a_images"] = a_saved
            if len(a_saved) > 0:
                result["ui"]["images"].append(a_saved[0])

        if image_b is not None and len(image_b) > 0:
            b_saved = self.save_images(image_b, filename_prefix + "b.", prompt, extra_pnginfo)["ui"]["images"]
            result["ui"]["b_images"] = b_saved
            if len(b_saved) > 0:
                result["ui"]["images"].append(b_saved[0])

        return result
