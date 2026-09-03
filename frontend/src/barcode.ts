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

async function imageDataFrom(source: ImageBitmapSource): Promise<ImageData | null> {
  if (typeof HTMLVideoElement !== "undefined" && source instanceof HTMLVideoElement) {
    if (source.readyState < 2 || source.videoWidth < 16) return null;
    return drawToImageData(source, source.videoWidth, source.videoHeight);
  }
  if (typeof HTMLCanvasElement !== "undefined" && source instanceof HTMLCanvasElement) {
    const ctx = source.getContext("2d");
    if (!ctx) return null;
    return ctx.getImageData(0, 0, source.width, source.height);
  }
  if (typeof ImageData !== "undefined" && source instanceof ImageData) return source;
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
  ctx.drawImage(source, 0, 0, w, h);
  return ctx.getImageData(0, 0, w, h);
}

async function detectQrFallback(source: ImageBitmapSource): Promise<string | null> {
  const image = await imageDataFrom(source);
  if (!image) return null;
  const { default: jsQR } = await import("jsqr");
  const hit = jsQR(image.data, image.width, image.height, { inversionAttempts: "attemptBoth" });
  const raw = hit?.data?.trim();
  return raw || null;
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

export function cameraSupported(): boolean {
  return Boolean(navigator.mediaDevices?.getUserMedia);
}
