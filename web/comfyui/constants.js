import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
export function addCompare(str) {
    return str + " (compare)";
}
export function stripCompare(str) {
    return str.replace(/\s*\(compare\)$/, "");
}
export const NodeTypesString = {
    ANY_SWITCH: addCompare("Any Switch"),
    CONTEXT: addCompare("Context"),
    CONTEXT_BIG: addCompare("Context Big"),
    CONTEXT_SWITCH: addCompare("Context Switch"),
    CONTEXT_SWITCH_BIG: addCompare("Context Switch Big"),
    CONTEXT_MERGE: addCompare("Context Merge"),
    CONTEXT_MERGE_BIG: addCompare("Context Merge Big"),
    DYNAMIC_CONTEXT: addCompare("Dynamic Context"),
    DYNAMIC_CONTEXT_SWITCH: addCompare("Dynamic Context Switch"),
    DISPLAY_ANY: addCompare("Display Any"),
    IMAGE_OR_LATENT_SIZE: addCompare("Image or Latent Size"),
    NODE_MODE_RELAY: addCompare("Mute / Bypass Relay"),
    NODE_MODE_REPEATER: addCompare("Mute / Bypass Repeater"),
    FAST_MUTER: addCompare("Fast Muter"),
    FAST_BYPASSER: addCompare("Fast Bypasser"),
    FAST_GROUPS_MUTER: addCompare("Fast Groups Muter"),
    FAST_GROUPS_BYPASSER: addCompare("Fast Groups Bypasser"),
    FAST_ACTIONS_BUTTON: addCompare("Fast Actions Button"),
    LABEL: addCompare("Label"),
    POWER_PRIMITIVE: addCompare("Power Primitive"),
    POWER_PROMPT: addCompare("Power Prompt"),
    POWER_PROMPT_SIMPLE: addCompare("Power Prompt - Simple"),
    POWER_PUTER: addCompare("Power Puter"),
    POWER_CONDUCTOR: addCompare("Power Conductor"),
    SDXL_EMPTY_LATENT_IMAGE: addCompare("SDXL Empty Latent Image"),
    SDXL_POWER_PROMPT_POSITIVE: addCompare("SDXL Power Prompt - Positive"),
    SDXL_POWER_PROMPT_NEGATIVE: addCompare("SDXL Power Prompt - Simple / Negative"),
    POWER_LORA_LOADER: addCompare("Power Lora Loader"),
    KSAMPLER_CONFIG: addCompare("KSampler Config"),
    NODE_COLLECTOR: addCompare("Node Collector"),
    REROUTE: addCompare("Reroute"),
    RANDOM_UNMUTER: addCompare("Random Unmuter"),
    SEED: addCompare("Seed"),
    BOOKMARK: addCompare("Bookmark"),
    IMAGE_COMPARER: addCompare("Image Comparer"),
    IMAGE_INSET_CROP: addCompare("Image Inset Crop"),
};
const UNRELEASED_KEYS = {
    [NodeTypesString.DYNAMIC_CONTEXT]: "dynamic_context",
    [NodeTypesString.DYNAMIC_CONTEXT_SWITCH]: "dynamic_context",
    [NodeTypesString.POWER_CONDUCTOR]: "power_conductor",
};
export function getNodeTypeStrings() {
    const unreleasedKeys = Object.keys(UNRELEASED_KEYS);
    return Object.values(NodeTypesString)
        .map((i) => stripCompare(i))
        .filter((i) => {
        if (unreleasedKeys.includes(i)) {
            return !!CONFIG_SERVICE.getConfigValue(`unreleased.${UNRELEASED_KEYS[i]}.enabled`);
        }
        return true;
    })
        .sort();
}
