import { app } from "../../scripts/app.js";

async function tryToGetWorkflowDataFromEvent(e) {
    try {
        const dt = e.dataTransfer;
        if (!dt)
            return { workflow: null, prompt: null };
        // Try explicit types
        const tryTypes = ["application/json", "text/json", "text/plain"];
        for (const t of tryTypes) {
            if (dt.types && Array.from(dt.types).includes(t)) {
                const txt = dt.getData(t) || dt.getData("text/plain");
                if (txt) {
                    try {
                        const parsed = JSON.parse(txt);
                        return { workflow: parsed, prompt: null };
                    }
                    catch (err) { }
                }
            }
        }
        // Try files
        if (dt.files && dt.files.length) {
            const file = dt.files[0];
            const text = await file.text();
            try {
                const parsed = JSON.parse(text);
                return { workflow: parsed, prompt: null };
            }
            catch (err) { }
        }
    }
    catch (err) { }
    return { workflow: null, prompt: null };
}
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
import { NodeTypesString } from "./constants.js";
app.registerExtension({
    name: "compare.ImportIndividualNodes",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const onDragOver = nodeType.prototype.onDragOver;
        nodeType.prototype.onDragOver = function (e) {
            var _a;
            let handled = (_a = onDragOver === null || onDragOver === void 0 ? void 0 : onDragOver.apply) === null || _a === void 0 ? void 0 : _a.call(onDragOver, this, [...arguments]);
            if (handled != null) {
                return handled;
            }
            return importIndividualNodesInnerOnDragOver(this, e);
        };
        const onDragDrop = nodeType.prototype.onDragDrop;
        nodeType.prototype.onDragDrop = async function (e) {
            var _a;
            const alreadyHandled = await ((_a = onDragDrop === null || onDragDrop === void 0 ? void 0 : onDragDrop.apply) === null || _a === void 0 ? void 0 : _a.call(onDragDrop, this, [...arguments]));
            if (alreadyHandled) {
                return alreadyHandled;
            }
            return importIndividualNodesInnerOnDragDrop(this, e);
        };
    },
});
export function importIndividualNodesInnerOnDragOver(node, e) {
    var _a;
    return ((((_a = node.widgets) === null || _a === void 0 ? void 0 : _a.length) && !!CONFIG_SERVICE.getFeatureValue("import_individual_nodes.enabled")) ||
        false);
}
export async function importIndividualNodesInnerOnDragDrop(node, e) {
    var _a, _b;
    if (!((_a = node.widgets) === null || _a === void 0 ? void 0 : _a.length) || !CONFIG_SERVICE.getFeatureValue("import_individual_nodes.enabled")) {
        return false;
    }
    const dynamicWidgetLengthNodes = [NodeTypesString.POWER_LORA_LOADER];
    let handled = false;
    const { workflow, prompt } = await tryToGetWorkflowDataFromEvent(e);
    const exact = ((workflow === null || workflow === void 0 ? void 0 : workflow.nodes) || []).find((n) => {
        var _a, _b;
        return n.id === node.id &&
            n.type === node.type &&
            (dynamicWidgetLengthNodes.includes(node.type) ||
                ((_a = n.widgets_values) === null || _a === void 0 ? void 0 : _a.length) === ((_b = node.widgets_values) === null || _b === void 0 ? void 0 : _b.length));
    });
    if (!exact) {
        handled = !confirm("[ComfyUI-Compare] Could not find a matching node (same id & type) in the dropped workflow." +
            " Would you like to continue with the default drop behaviour instead?");
    }
    else if (!((_b = exact.widgets_values) === null || _b === void 0 ? void 0 : _b.length)) {
        handled = !confirm("[ComfyUI-Compare] Matching node found (same id & type) but there's no widgets to set." +
            " Would you like to continue with the default drop behaviour instead?");
    }
    else if (confirm("[ComfyUI-Compare] Found a matching node (same id & type) in the dropped workflow." +
        " Would you like to set the widget values?")) {
        node.configure({
            title: node.title,
            widgets_values: [...((exact === null || exact === void 0 ? void 0 : exact.widgets_values) || [])],
            mode: exact.mode,
        });
        handled = true;
    }
    return handled;
}
