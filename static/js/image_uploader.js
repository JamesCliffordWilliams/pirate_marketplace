/*
    image_uploader.js

    The Vault Campus Marketplace
    Created by James Williams - 10/26/26
    Updated by James Williams - 10/26/26 - you can pick several photos at once now
    This is the shared photo picker for the listing, storefront and returns forms.
    It only takes JPG, PNG, WebP and GIF, shrinks big photos, and removes location data from JPEGs.
    guardSubmit() stops a form from sending the same request twice.
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

    // Gets the real image type, or null if we don't take that kind of file.
    // Some browsers leave file.type empty, so this checks the file name too
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

    // Makes the file name and type match what's really in the file, since the server checks the extension
    function withType(file, type) {
        const ext = extensionOf(file.name);
        const matches = ext === TYPE_EXT[type] || (type === "image/jpeg" && ext === "jpeg");
        if (matches && file.type === type) return file;
        const base = file.name.replace(/\.[^.]*$/, "") || "photo";
        return new File([file], `${base}.${TYPE_EXT[type]}`, { type, lastModified: file.lastModified });
    }

    // Checks if a JPEG has location info saved in it. If we can't read it, we assume it does
    function jpegHasGps(buffer) {
        try {
            const view = new DataView(buffer);
            if (view.getUint16(0) !== 0xFFD8) return true;
            let pos = 2;
            while (pos + 4 <= view.byteLength) {
                const marker = view.getUint16(pos);
                if (marker === 0xFFDA) return false; // the picture itself starts here, so there's no more metadata
                if ((marker & 0xFF00) !== 0xFF00) return true;
                const length = view.getUint16(pos + 2);
                if (marker === 0xFFE1) {
                    if (view.getUint32(pos + 4) === 0x45786966) { // "Exif"
                        const tiff = pos + 10;
                        const little = view.getUint16(tiff) === 0x4949;
                        const ifd = tiff + view.getUint32(tiff + 4, little);
                        const count = view.getUint16(ifd, little);
                        for (let i = 0; i < count; i++) {
                            if (view.getUint16(ifd + 2 + i * 12, little) === 0x8825) return true; // GPS section
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
                // if that fails, use a normal <img>, which also turns the photo the right way
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

    // Gets a photo ready to upload and makes its preview. If something is wrong it throws an error the user can read
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
                // Browsers without WebP give back a PNG instead, so we use whatever type the blob really is
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

    // This sets up one photo picker. options.preview is where the thumbnail goes and options.onChange runs when the photo changes.
    // options.onExtraFiles gets any extra photos picked at the same time, and the page decides where they go.
    // The page reads picker.file and picker.previewUrl, and can call picker.pick(file) and picker.clear()
    function attach(input, options = {}) {
        const zone = input.closest(".drop-zone");
        const message = document.createElement("p");
        message.className = "upload-error";
        message.setAttribute("role", "alert");
        message.hidden = true;
        zone.after(message);

        let latestPick = 0;
        const picker = { input, file: null, previewUrl: null, pick, clear: () => setFile(null) };

        function setFile(file, previewUrl) {
            if (picker.previewUrl) URL.revokeObjectURL(picker.previewUrl);
            picker.file = file;
            picker.previewUrl = file ? previewUrl : null;
            zone.classList.toggle("has-image", Boolean(file));
            if (file) zone.style.setProperty("--preview-image", `url("${previewUrl}")`);
            else zone.style.removeProperty("--preview-image");
            renderThumb(options.preview, picker.file, picker.previewUrl);
            if (options.onChange) options.onChange(picker.file);
        }

        function showError(text) {
            message.textContent = text || "";
            message.hidden = !text;
        }

        async function pick(file) {
            const pickId = ++latestPick;
            input.value = ""; // clears the input so the same file can be picked again
            showError("");
            zone.classList.add("is-processing");
            zone.setAttribute("aria-busy", "true");
            const job = prepare(file);
            inFlight.add(job);
            try {
                const result = await job;
                if (pickId === latestPick) setFile(result.file, result.previewUrl);
                else URL.revokeObjectURL(result.previewUrl);
            } catch (error) {
                if (pickId === latestPick) showError(error.message);
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

    // This stops a form from being sent twice. If the handler returns true the page is leaving,
    // so the button stays off. Otherwise the button turns back on.
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

    window.ImageUploader = { attach, guardSubmit, _internals: { imageType, jpegHasGps } };
})();
