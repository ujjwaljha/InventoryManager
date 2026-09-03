const FORMATS = [
  "aztec",
  "code_128",
  "code_39",
  "code_93",
  "codabar",
  "data_matrix",
  "ean_13",
  "ean_8",
  "itf",
  "pdf417",
  "qr_code",
  "upc_a",
  "upc_e",
];

type Detector = {
  detect: (source: ImageBitmapSource) => Promise<{ rawValue?: string }[]>;
};

let detectorReady: Promise<Detector | null> | null = null;

function nativeDetector(): Promise<Detector | null> {
  if (detectorReady) return detectorReady;
  detectorReady = (async () => {
    const Ctor = (window as unknown as { BarcodeDetector?: new (opts?: { formats?: string[] }) => Detector }).BarcodeDetector;
    if (!Ctor) return null;
    try {
      const supported = await (Ctor as unknown as { getSupportedFormats?: () => Promise<string[]> }).getSupportedFormats?.();
      const formats = supported?.filter((f) => FORMATS.includes(f));
      return new Ctor(formats?.length ? { formats } : { formats: FORMATS });
    } catch {
      try {
        return new Ctor();
      } catch {
        return null;
      }
    }
  })();
  return detectorReady;
}

function isHtmlImage(source: unknown): source is HTMLImageElement {
  return typeof HTMLImageElement !== "undefined" && source instanceof HTMLImageElement;
}

async function imageDataFrom(source: ImageBitmapSource): Promise<ImageData | null> {
  if (typeof HTMLVideoElement !== "undefined" && source instanceof HTMLVideoElement) {
    if (source.readyState < 2 || source.videoWidth < 16) return null;
    return drawToImageData(source, source.videoWidth, source.videoHeight);
  }
  if (typeof HTMLCanvasElement !== "undefined" && source instanceof HTMLCanvasElement) {
    return drawToImageData(source, source.width, source.height);
  }
  if (typeof ImageData !== "undefined" && source instanceof ImageData) return source;
  if (isHtmlImage(source)) {
    const w = source.naturalWidth || source.width;
    const h = source.naturalHeight || source.height;
    if (w < 8 || h < 8) return null;
    return drawToImageData(source, w, h);
  }
  try {
    const bitmap = source instanceof ImageBitmap ? source : await createImageBitmap(source);
    const data = drawToImageData(bitmap, bitmap.width, bitmap.height);
    if (!(source instanceof ImageBitmap)) bitmap.close();
    return data;
  } catch {
    return null;
  }
}

function drawToImageData(source: CanvasImageSource, width: number, height: number): ImageData | null {
  const max = 800;
  let w = width;
  let h = height;
  if (w > max || h > max) {
    const scale = max / Math.max(w, h);
    w = Math.max(1, Math.round(w * scale));
    h = Math.max(1, Math.round(h * scale));
  }
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(source, 0, 0, w, h);
  return ctx.getImageData(0, 0, w, h);
}

function upsample(image: ImageData, factor: number): ImageData {
  const w = image.width * factor;
  const h = image.height * factor;
  const out = new ImageData(w, h);
  for (let y = 0; y < image.height; y++) {
    for (let x = 0; x < image.width; x++) {
      const si = (y * image.width + x) * 4;
      for (let dy = 0; dy < factor; dy++) {
        for (let dx = 0; dx < factor; dx++) {
          const di = ((y * factor + dy) * w + (x * factor + dx)) * 4;
          out.data[di] = image.data[si];
          out.data[di + 1] = image.data[si + 1];
          out.data[di + 2] = image.data[si + 2];
          out.data[di + 3] = 255;
        }
      }
    }
  }
  return out;
}

async function detectQrFallback(source: ImageBitmapSource): Promise<string | null> {
  const image = await imageDataFrom(source);
  if (!image) return null;
  const { default: jsQR } = await import("jsqr");
  const variants = [image];
  if (image.width < 400 || image.height < 400) variants.push(upsample(image, 2));
  for (const variant of variants) {
    const hit = jsQR(variant.data, variant.width, variant.height, { inversionAttempts: "attemptBoth" });
    const raw = hit?.data?.trim();
    if (raw) return raw;
  }
  return null;
}

export async function detectBarcode(source: ImageBitmapSource): Promise<string | null> {
  const detector = await nativeDetector();
  if (detector) {
    try {
      const hits = await detector.detect(source);
      const raw = hits.map((h) => (h.rawValue || "").trim()).find(Boolean);
      if (raw) return raw;
    } catch {
      /* try QR fallback */
    }
  }
  return detectQrFallback(source);
}

export async function detectBarcodeFromFile(file: File): Promise<string | null> {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return await detectBarcode(img);
  } catch {
    try {
      const bitmap = await createImageBitmap(file);
      const code = await detectBarcode(bitmap);
      bitmap.close();
      return code;
    } catch {
      return null;
    }
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function cameraSupported(): boolean {
  return Boolean(navigator.mediaDevices?.getUserMedia);
}
