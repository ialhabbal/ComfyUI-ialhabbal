import { getObjectValue, setObjectValue } from "../../common/shared_utils.js";
import { mynodeApi } from "../../common/mynode_api.js";
// Local config object for this custom node
const LOCAL_CONFIG = {};
class ConfigService extends EventTarget {
    getConfigValue(key, def) {
        return getObjectValue(LOCAL_CONFIG, key, def);
    }
    getFeatureValue(key, def) {
        key = "features." + key.replace(/^features\./, "");
        return getObjectValue(LOCAL_CONFIG, key, def);
    }
    async setConfigValues(changed) {
        const body = new FormData();
        body.append("json", JSON.stringify(changed));
        const response = await mynodeApi.fetchJson("/config", { method: "POST", body });
        if (response.status === "ok") {
            for (const [key, value] of Object.entries(changed)) {
                setObjectValue(LOCAL_CONFIG, key, value);
                this.dispatchEvent(new CustomEvent("config-change", { detail: { key, value } }));
            }
        }
        else {
            return false;
        }
        return true;
    }
}
export const SERVICE = new ConfigService();
