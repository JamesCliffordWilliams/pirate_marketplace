/*
    image_uploader.js

    The Vault Campus Marketplace
    Created by James Williams - 10/26/26
    Updated by James Williams - 10/26/26 - several photos at once (onExtraFiles), picker.pick()
    Shared photo picker for the listing, storefront and returns forms.
    - Each .drop-zone is a <label> around its file input, so one click opens one dialog
    - Accepts JPG, PNG, WebP and GIF; says why anything else was refused
    - Shrinks large photos, keeps transparency, and re-encodes JPEGs with GPS data
    - Makes one small preview per pick and revokes old preview URLs
    guardSubmit() lets a form send only one request at a time.
*/

(function () {
    const TYPE_EXT = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif" };
    const EXT_TYPE = { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp", gif: "image/gif" };
    const MAX_SIDE = 2000;
    const PASS_BYTES = 1.5 * 1024 * 1024;
    const PREVIEW_SIDE = 480;
    const inFlight = new Set();

    function extensionOf(name) {
        const dot = name.lastIndexOf(".");
        return dot === -1 ? "" : name.slice(dot + 1).toLowerCase();
    }

    // Real image type, or null when we don't accept it (some browsers leave file.type empty)
    function imageType(file) {
        if (TYPE_EXT[file.type]) return file.type;
        return file.type ? null : EXT_TYPE[extensionOf(file.name)] || null;
    }

    function typeMessage(file) {
        if (/hei[cf]/.test(file.type) || /^hei[cf]$/.test(extensionOf(file.name))) {
            return "HEIC photos aren't supported. Export the photo as a JPG and try again.";
        }
        return "That file type isn't supported. Use a JPG, PNG, WebP or GIF image.";
    }

    // Gives the file the extension and type that match its contents (the server checks the extension)
    function withType(file, type) {
        const ext = extensionOf(file.name);
        const matches = ext === TYPE_EXT[type] || (type === "image/jpeg" && ext === "jpeg");
        if (matches && file.type === type) return file;
        const base = file.name.replace(/\.[^.]*$/, "") || "photo";
        return new File([file], `${base}.${TYPE_EXT[type]}`, { type, lastModified: file.lastModified });
    }

    // True when a JPEG's EXIF or XMP data holds a location. Unreadable metadata counts as true.
    function jpegHasGps(buffer) {
        try {
            const view = new DataView(buffer);
            if (view.getUint16(0) !== 0xFFD8) return true;
            let pos = 2;
            while (pos + 4 <= view.byteLength) {
                const marker = view.getUint16(pos);
                if (marker === 0xFFDA) return false; // image data starts; no more metadata
                if ((marker & 0xFF00) !== 0xFF00) return true;
                const length = view.getUint16(pos + 2);
                if (marker === 0xFFE1) {
                    if (view.getUint32(pos + 4) === 0x45786966) { // "Exif"
                        const tiff = pos + 10;
                        const little = view.getUint16(tiff) === 0x4949;
                        const ifd = tiff + view.getUint32(tiff + 4, little);
                        const count = view.getUint16(ifd, little);
                        for (let i = 0; i < count; i++) {
                            if (view.getUint16(ifd + 2 + i * 12, little) === 0x8825) return true; // GPS IFD
                        }
                    } else {
                        const text = new TextDecoder().decode(new Uint8Array(buffer, pos + 4, length - 2));
                        if (text.includes("GPSLatitude")) return true;
                    }
                }
                pos += 2 + length;
            }
            return true; // metadata ran past what we read
        } catch (error) {
            return true;
        }
    }

    async function decode(file) {
        if (window.createImageBitmap) {
            try {
                return await createImageBitmap(file, { imageOrientation: "from-image" });
            } catch (error) {
                // fall back to <img>, which also applies EXIF orientation
            }
        }
        const url = URL.createObjectURL(file);
        try {
            const img = new Image();
            img.src = url;
            await img.decode();
            return img;
        } finally {
            URL.revokeObjectURL(url);
        }
    }

    function draw(source, width, height, scale) {
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
        return canvas;
    }

    function toBlob(canvas, type, quality) {
        return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
    }

    function hasAlpha(canvas) {
        const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
        for (let i = 3; i < data.length; i += 4) {
            if (data[i] < 255) return true;
        }
        return false;
    }

    // Returns { file, previewUrl } ready to upload, or throws an Error with a message for the user
    async function prepare(file) {
        const type = imageType(file);
        if (!type) throw new Error(typeMessage(file));
        if (type === "image/gif") return { file: withType(file, type), previewUrl: URL.createObjectURL(file) };

        const hasGps = type === "image/jpeg" && jpegHasGps(await file.slice(0, 256 * 1024).arrayBuffer());
        let source;
        try {
            source = await decode(file);
        } catch (error) {
            throw new Error("We couldn't read that image. Try a different file.");
        }

        try {
            const width = source.naturalWidth || source.width;
            const height = source.naturalHeight || source.height;
            const preview = draw(source, width, height, Math.min(1, PREVIEW_SIDE / Math.max(width, height)));
            const alpha = type !== "image/jpeg" && hasAlpha(preview);
            const previewBlob = await toBlob(preview, alpha ? "image/png" : "image/jpeg", 0.8);

            let output = withType(file, type);
            const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
            const oversized = scale < 1 || file.size > PASS_BYTES;
            if (oversized || hasGps) {
                // Without WebP support toBlob returns a PNG, so the blob's own type is used below
                const blob = await toBlob(
                    draw(source, width, height, scale),
                    alpha ? "image/webp" : "image/jpeg",
                    oversized ? 0.85 : 0.92
                );
                if (!blob || !TYPE_EXT[blob.type]) {
                    if (hasGps) throw new Error("We couldn't prepare that photo. Try a different file.");
                } else if (hasGps || blob.size < file.size) {
                    output = withType(new File([blob], file.name, { lastModified: file.lastModified }), blob.type);
                }
            }
            return { file: output, previewUrl: URL.createObjectURL(previewBlob || file) };
        } finally {
            if (source.close) source.close();
        }
    }

    function renderThumb(container, file, previewUrl) {
        if (!container) return;
        container.replaceChildren();
        if (!file) return;
        const wrap = document.createElement("div");
        wrap.className = "thumb-wrap";
        const img = document.createElement("img");
        img.src = previewUrl;
        img.alt = file.name;
        const name = document.createElement("span");
        name.className = "thumb-name";
        name.textContent = file.name;
        wrap.append(img, name);
        container.appendChild(wrap);
    }

    // Wires one picker. options.preview: thumbnail container; options.onChange(file, picker);
    // options.onExtraFiles(files): more files picked or dropped at once (the page decides where they go)
    function attach(input, options = {}) {
        const zone = input.closest(".drop-zone");
        const message = document.createElement("p");
        message.className = "upload-error";
        message.setAttribute("role", "alert");
        message.hidden = true;
        zone.after(message);

        let latestPick = 0;
        const picker = {
            file: null,
            previewUrl: null,
            set(file, previewUrl) {
                if (picker.previewUrl) URL.revokeObjectURL(picker.previewUrl);
                picker.file = file || null;
                picker.previewUrl = file ? previewUrl : null;
                zone.classList.toggle("has-image", Boolean(file));
                if (file) zone.style.setProperty("--preview-image", `url("${previewUrl}")`);
                else zone.style.removeProperty("--preview-image");
                renderThumb(options.preview, picker.file, picker.previewUrl);
                if (options.onChange) options.onChange(picker.file, picker);
            },
            clear() {
                picker.set(null);
            },
            showError(text) {
                message.textContent = text || "";
                message.hidden = !text;
            }
        };

        async function pick(file) {
            const pickId = ++latestPick;
            input.value = ""; // lets the same file be picked again (also clears a multi-pick)
            picker.showError("");
            zone.classList.add("is-processing");
            zone.setAttribute("aria-busy", "true");
            const job = prepare(file);
            inFlight.add(job);
            try {
                const result = await job;
                if (pickId === latestPick) picker.set(result.file, result.previewUrl);
                else URL.revokeObjectURL(result.previewUrl);
            } catch (error) {
                if (pickId === latestPick) picker.showError(error.message);
            } finally {
                inFlight.delete(job);
                if (pickId === latestPick) {
                    zone.classList.remove("is-processing");
                    zone.removeAttribute("aria-busy");
                }
            }
        }

        function pickMany(fileList) {
            const files = Array.from(fileList || []);
            if (!files.length) return;
            pick(files[0]);
            if (files.length > 1 && options.onExtraFiles) options.onExtraFiles(files.slice(1));
        }

        picker.pick = pick;
        input.addEventListener("change", () => pickMany(input.files));
        zone.addEventListener("dragover", (event) => {
            event.preventDefault();
            zone.classList.add("dragover");
        });
        zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
        zone.addEventListener("drop", (event) => {
            event.preventDefault();
            zone.classList.remove("dragover");
            if (event.dataTransfer) pickMany(event.dataTransfer.files);
        });
        return picker;
    }

    // Submit handler that ignores repeat submits. The handler returns true when the page is
    // leaving (the button stays disabled); anything else re-enables the button.
    function guardSubmit(form, busyLabel, handler) {
        const button = form.querySelector('[type="submit"]');
        let submitting = false;
        return async (event) => {
            event.preventDefault();
            if (submitting) return;
            submitting = true;
            const label = button ? button.textContent : "";
            if (button) {
                button.disabled = true;
                button.textContent = busyLabel;
            }
            let leaving = false;
            try {
                await Promise.allSettled([...inFlight]); // wait for photos still being prepared
                leaving = (await handler(event)) === true;
            } finally {
                if (!leaving) {
                    submitting = false;
                    if (button) {
                        button.disabled = false;
                        button.textContent = label;
                    }
                }
            }
        };
    }

    window.ImageUploader = { attach, prepare, guardSubmit, _internals: { imageType, withType, jpegHasGps } };
})();
