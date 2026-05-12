import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Import helpers from centralized re-export module in this extension's comfyui folder.
import { CompareBaseServerNode, addConnectionLayoutSupport, CompareBaseWidget, measureText } from "../../comfyui/index.js";

// Debug marker to confirm this extension script is loaded in the browser
try { console.info("ComfyUI-Compare: compare.js loaded"); } catch (e) {}

function imageDataToUrl(data) {
  return api.apiURL(`/view?filename=${encodeURIComponent(data.filename)}&type=${data.type}&subfolder=${data.subfolder}${app.getPreviewFormatParam()}${app.getRandParam()}`);
}

export class CompareNode extends CompareBaseServerNode {
  constructor(title = CompareNode.title) {
    super(title);
    this.imageIndex = 0;
    this.imgs = [];
    this.serialize_widgets = true;
    this.isPointerDown = false;
    this.isPointerOver = false;
    this.pointerOverPos = [0, 0];
    this.canvasWidget = null;
    this.properties = this.properties || {};
    this.properties["comparer_mode"] = "Slide";
  }

  onExecuted(output) {
    super.onExecuted && super.onExecuted(output);
    if ("images" in output) {
      this.canvasWidget.value = {
        images: (output.images || []).map((d, i) => ({ name: i === 0 ? "A" : "B", selected: true, url: imageDataToUrl(d) })),
      };
    } else {
      output.a_images = output.a_images || [];
      output.b_images = output.b_images || [];
      const imagesToChoose = [];
      const multiple = output.a_images.length + output.b_images.length > 2;
      for (const [i, d] of output.a_images.entries()) {
        imagesToChoose.push({ name: output.a_images.length > 1 || multiple ? `A${i + 1}` : "A", selected: i === 0, url: imageDataToUrl(d) });
      }
      for (const [i, d] of output.b_images.entries()) {
        imagesToChoose.push({ name: output.b_images.length > 1 || multiple ? `B${i + 1}` : "B", selected: i === 0, url: imageDataToUrl(d) });
      }
      this.canvasWidget.value = { images: imagesToChoose };
    }
  }

  onSerialize(serialised) {
    super.onSerialize && super.onSerialize(serialised);
    for (let [index, widget_value] of (serialised.widgets_values || []).entries()) {
      if (this.widgets[index] && this.widgets[index].name === "compare_comparer") {
        serialised.widgets_values[index] = this.widgets[index].value.images.map((d) => {
          const copy = Object.assign({}, d);
          delete copy.img;
          return copy;
        });
      }
    }
  }

  onNodeCreated() {
    this.canvasWidget = this.addCustomWidget(new CompareWidget("compare_comparer", this));
    this.setSize(this.computeSize());
    this.setDirtyCanvas(true, true);
  }

  setIsPointerDown(down) {
    if (down === undefined) down = this.isPointerDown;
    const newIsDown = down && !!app.canvas.pointer_is_down;
    if (this.isPointerDown !== newIsDown) {
      this.isPointerDown = newIsDown;
      this.setDirtyCanvas(true, false);
    }
    this.imageIndex = this.isPointerDown ? 1 : 0;
    if (this.isPointerDown) {
      requestAnimationFrame(() => this.setIsPointerDown());
    }
  }

  onMouseDown(event, pos, canvas) {
    super.onMouseDown && super.onMouseDown(event, pos, canvas);
    this.setIsPointerDown(true);
    return false;
  }

  onMouseEnter(event) {
    super.onMouseEnter && super.onMouseEnter(event);
    this.setIsPointerDown(!!app.canvas.pointer_is_down);
    this.isPointerOver = true;
  }

  onMouseLeave(event) {
    super.onMouseLeave && super.onMouseLeave(event);
    this.setIsPointerDown(false);
    this.isPointerOver = false;
  }

  onMouseMove(event, pos, canvas) {
    super.onMouseMove && super.onMouseMove(event, pos, canvas);
    this.pointerOverPos = [pos[0], pos[1]];
    this.imageIndex = this.pointerOverPos[0] > this.size[0] / 2 ? 1 : 0;
  }

  static setUp(comfyClass, nodeData) {
    CompareBaseServerNode.registerForOverride(comfyClass, nodeData, CompareNode);
  }

  static onRegisteredForOverride(comfyClass) {
    addConnectionLayoutSupport(CompareNode, app, [["Left", "Right"], ["Right", "Left"]]);
    setTimeout(() => { CompareNode.category = comfyClass.category; });
  }

  getHelp() {
    return `Compare node: shows image A over B by default. Hover to switch to B and drag to wipe A left→right.`;
  }
}

CompareNode.title = "Compare";
CompareNode.type = "Compare";
CompareNode.comfyClass = "Compare";
CompareNode["@comparer_mode"] = { type: "combo", values: ["Slide", "Click"] };
class CompareWidget extends CompareBaseWidget {
  constructor(name, node) {
    super(name);
    this.type = "custom";
    this.hitAreas = {};
    this.selected = [];
    this._value = { images: [] };
    this.node = node;
    // Overlay state for enlarged view / controls
    this.overlayOpen = false;
    this.controlSize = 18;
  }

  set value(v) {
    let cleanedVal;
    if (Array.isArray(v)) {
      cleanedVal = v.map((d, i) => {
        if (!d || typeof d === "string") {
          return { url: d, name: i === 0 ? "A" : "B", selected: true };
        }
        return d;
      });
    } else {
      cleanedVal = (v && v.images) || [];
    }

    if (cleanedVal.length > 2) {
      const hasAAndB = cleanedVal.some((i) => i.name.startsWith("A")) && cleanedVal.some((i) => i.name.startsWith("B"));
      if (!hasAAndB) cleanedVal = [cleanedVal[0], cleanedVal[1]];
    }

    let selected = cleanedVal.filter((d) => d.selected);
    if (!selected.length && cleanedVal.length) cleanedVal[0].selected = true;
    selected = cleanedVal.filter((d) => d.selected);
    if (selected.length === 1 && cleanedVal.length > 1) cleanedVal.find((d) => !d.selected).selected = true;

    this._value.images = cleanedVal;
    selected = cleanedVal.filter((d) => d.selected);
    this.setSelected(selected);
  }

  get value() { return this._value; }

  setSelected(selected) {
    this._value.images.forEach((d) => (d.selected = false));
    this.node.imgs.length = 0;
    for (const sel of selected) {
      if (!sel.img) { sel.img = new Image(); sel.img.src = sel.url; this.node.imgs.push(sel.img); }
      sel.selected = true;
    }
    this.selected = selected;
  }

  draw(ctx, node, width, y) {
    this.hitAreas = {};
    if (this._value.images.length > 2) {
      ctx.textAlign = "left"; ctx.textBaseline = "top"; ctx.font = `14px Arial`;
      const drawData = []; const spacing = 5; let x = 0;
      for (const img of this._value.images) {
        const w = measureText(ctx, img.name);
        drawData.push({ img, text: img.name, x, width: w });
        x += w + spacing;
      }
      x = (node.size[0] - (x - spacing)) / 2;
      for (const d of drawData) {
        ctx.fillStyle = d.img.selected ? "rgba(180, 180, 180, 1)" : "rgba(180, 180, 180, 0.5)";
        ctx.fillText(d.text, x, y);
        this.hitAreas[d.text] = { bounds: [x, y, d.width, 14], data: d.img, onDown: this.onSelectionDown };
        x += d.width + spacing;
      }
      y += 20;
    }

    const a = this.selected[0];
    const b = this.selected[1];
    if (!a && !b) return;

    // Draw base: B if present (otherwise A)
    if (b) this.drawImage(ctx, b, y);
    else if (a) this.drawImage(ctx, a, y);

    // Default (no hover): show A fully on top if present
    if (!node.isPointerOver) {
      if (a) this.drawImage(ctx, a, y);
    } else {
      // Hover: start with B (already drawn). As mouse moves right, reveal A from left→right.
      const cropX = this.node.pointerOverPos ? this.node.pointerOverPos[0] : null;
      if (a) this.drawImage(ctx, a, y, cropX);
    }

    // Make the entire image area clickable to open the overlay (if an image was drawn)
    // Prefer the A image bounds if available, otherwise B.
    let areaBounds = null;
    if (a && a.img && a.img._lastDrawBounds) areaBounds = a.img._lastDrawBounds;
    else if (b && b.img && b.img._lastDrawBounds) areaBounds = b.img._lastDrawBounds;
    if (areaBounds) {
      this.hitAreas.__image_area = { bounds: [areaBounds.x, areaBounds.y, areaBounds.width, areaBounds.height], data: null, onDown: this.onImageDown };
    }

    // Draw overlay controls (close X and toggle). Toggle is placed top-left to the left of the image.
    if (this.overlayOpen && areaBounds) {
      const padding = 6;
      const btn = this.controlSize;

      // Close (X) - top-right of the image
      const closeX = areaBounds.x + areaBounds.width - btn - padding;
      const closeY = areaBounds.y + padding;
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect(closeX, closeY, btn, btn);
      ctx.fillStyle = "white";
      ctx.font = `12px Arial`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("X", closeX + btn / 2, closeY + btn / 2);
      this.hitAreas.__close = { bounds: [closeX, closeY, btn, btn], data: null, onDown: this.onCloseDown };

      // Toggle - top-left, to the left of the image (clamped to node left padding)
      const toggleW = 28;
      let toggleX = areaBounds.x - toggleW - padding;
      if (toggleX < padding) toggleX = padding;
      const toggleY = areaBounds.y + padding;
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect(toggleX, toggleY, toggleW, btn);
      ctx.fillStyle = "white";
      ctx.font = `12px Arial`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      // Show label for toggle (A/B)
      const toggleLabel = (this.selected && this.selected.length > 0 && this.selected[0] && this.selected[0].name) ? this.selected[0].name : "A";
      ctx.fillText(toggleLabel, toggleX + toggleW / 2, toggleY + btn / 2);
      this.hitAreas.__toggle = { bounds: [toggleX, toggleY, toggleW, btn], data: null, onDown: this.onToggleDown };
    }
  }

  onSelectionDown(event, pos, node, bounds) {
    const selected = [...this.selected];
    if (bounds && bounds.data && bounds.data.name && bounds.data.name.startsWith("A")) selected[0] = bounds.data;
    else if (bounds && bounds.data && bounds.data.name && bounds.data.name.startsWith("B")) selected[1] = bounds.data;
    this.setSelected(selected);
  }

  onImageDown(event, pos, node, bounds) {
    // bounds is the hit area entry with .bounds = [x,y,w,h]
    try {
      const bb = bounds && bounds.bounds ? bounds.bounds : bounds;
      // If clicked on left or right half, set imageIndex accordingly
      if (bb && Array.isArray(bb) && bb.length >= 3) {
        const relX = pos[0] - bb[0];
        this.node.imageIndex = (relX > bb[2] / 2) ? 1 : 0;
      }
    } catch (e) {}
    this.overlayOpen = true;
    this.node.setDirtyCanvas(true, true);
  }

  onCloseDown(event, pos, node, bounds) {
    this.overlayOpen = false;
    this.node.setDirtyCanvas(true, true);
  }

  onToggleDown(event, pos, node, bounds) {
    // Swap the selected order (A <-> B) so top image toggles
    if (!this.selected || this.selected.length < 2) return;
    const swapped = [this.selected[1], this.selected[0]];
    this.setSelected(swapped);
    this.node.setDirtyCanvas(true, true);
  }

  drawImage(ctx, image, y, cropX) {
    if (!image || !image.img || !image.img.naturalWidth || !image.img.naturalHeight) return;
    let nodeWidth = this.node.size[0];
    let nodeHeight = this.node.size[1];
    const imageAspect = image.img.naturalWidth / image.img.naturalHeight;
    let height = nodeHeight - y;
    const widgetAspect = nodeWidth / height;
    let targetWidth, targetHeight; let offsetX = 0;
    if (imageAspect > widgetAspect) { targetWidth = nodeWidth; targetHeight = nodeWidth / imageAspect; }
    else { targetHeight = height; targetWidth = height * imageAspect; offsetX = (nodeWidth - targetWidth) / 2; }

    const widthMultiplier = image.img.naturalWidth / targetWidth;
    const sourceX = 0; const sourceY = 0;
    const sourceWidth = (cropX != null && !isNaN(cropX)) ? Math.max(0, (cropX - offsetX) * widthMultiplier) : image.img.naturalWidth;
    const sourceHeight = image.img.naturalHeight;
    const destX = (nodeWidth - targetWidth) / 2; const destY = y + (height - targetHeight) / 2;
    const destWidth = (cropX != null && !isNaN(cropX)) ? Math.max(0, cropX - offsetX) : targetWidth; const destHeight = targetHeight;

    ctx.save();
    ctx.beginPath();
    const globalCompositeOperation = ctx.globalCompositeOperation;
    if (cropX != null && !isNaN(cropX)) { ctx.rect(destX, destY, destWidth, destHeight); ctx.clip(); }
    ctx.drawImage(image.img, sourceX, sourceY, sourceWidth, sourceHeight, destX, destY, destWidth, destHeight);
    if (cropX != null && !isNaN(cropX) && cropX >= destX && cropX <= destX + destWidth) {
      ctx.beginPath(); ctx.moveTo(cropX, destY); ctx.lineTo(cropX, destY + destHeight);
      ctx.globalCompositeOperation = "difference"; ctx.strokeStyle = "rgba(255,255,255,1)"; ctx.stroke();
    }
    ctx.globalCompositeOperation = globalCompositeOperation;
    ctx.restore();

    // store last draw bounds for interaction (used by overlay controls placement)
    image.img._lastDrawBounds = { x: destX, y: destY, width: destWidth, height: destHeight };
    return image.img._lastDrawBounds;
  }

  computeSize(width) { return [width, 20]; }

  serializeValue(node, index) { const v = []; for (const data of this._value.images) { const d = Object.assign({}, data); delete d.img; v.push(d); } return { images: v }; }
}

    app.registerExtension({
  name: "ComfyUI-Compare",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const name = (nodeData && nodeData.name) ? nodeData.name.toString().toLowerCase() : "";
    if (name === "compare" || name.includes("compare")) {
      CompareNode.setUp(nodeType, nodeData);
    }
  },
});
