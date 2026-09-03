import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cameraSupported, detectBarcode } from "../barcode";
import { useI18n } from "../i18n";

export type ScanResult = {
  ok: boolean;
  message: string;
  close?: boolean;
};

export function ScanButton({
  onCode,
  disabled,
}: {
  onCode: (code: string) => Promise<ScanResult> | ScanResult;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="btn ghost scan-btn" type="button" disabled={disabled} onClick={() => setOpen(true)}>
        {t("scanBarcode")}
      </button>
      {open ? <BarcodeScanner onClose={() => setOpen(false)} onCode={onCode} /> : null}
    </>
  );
}

export function BarcodeScanner({
  onClose,
  onCode,
}: {
  onClose: () => void;
  onCode: (code: string) => Promise<ScanResult> | ScanResult;
}) {
  const { t } = useI18n();
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const onCodeRef = useRef(onCode);
  const onCloseRef = useRef(onClose);
  const tRef = useRef(t);
  onCodeRef.current = onCode;
  onCloseRef.current = onClose;
  tRef.current = t;
  const [status, setStatus] = useState(t("scanLooking"));
  const [statusOk, setStatusOk] = useState<boolean | null>(null);
  const [camError, setCamError] = useState("");
  const busy = useRef(false);
  const last = useRef({ code: "", at: 0 });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCloseRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let timer = 0;
    let cancelled = false;
    const video = videoRef.current;

    async function handleCode(code: string) {
      const now = Date.now();
      if (code === last.current.code && now - last.current.at < 1600) return;
      last.current = { code, at: now };
      const result = await onCodeRef.current(code);
      setStatus(result.message);
      setStatusOk(result.ok);
      if (result.close) onCloseRef.current();
    }

    async function tick() {
      if (cancelled) return;
      const el = videoRef.current;
      if (el && !busy.current && el.readyState >= 2) {
        busy.current = true;
        try {
          const code = await detectBarcode(el);
          if (!cancelled && code) await handleCode(code);
        } catch {
          /* keep scanning */
        } finally {
          busy.current = false;
        }
      }
      if (!cancelled) timer = window.setTimeout(tick, 140);
    }

    async function start() {
      if (!cameraSupported()) {
        setCamError(tRef.current("scanNoCamera"));
        setStatus(tRef.current("scanUsePhotoHint"));
        setStatusOk(null);
        return;
      }
      let abandoned = false;
      const pending = navigator.mediaDevices
        .getUserMedia({
          audio: false,
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
        })
        .then((s) => {
          if (cancelled || abandoned) s.getTracks().forEach((tr) => tr.stop());
          return s;
        });
      const timeout = new Promise<MediaStream>((_, reject) => {
        window.setTimeout(() => reject(new Error("camera-timeout")), 4000);
      });
      try {
        stream = await Promise.race([pending, timeout]);
        if (cancelled || abandoned) return;
        if (video) {
          video.srcObject = stream;
          await video.play();
        }
        setStatus(tRef.current("scanLooking"));
        setStatusOk(null);
        tick();
      } catch {
        abandoned = true;
        setCamError(tRef.current("scanNeedHttps"));
        setStatus(tRef.current("scanUsePhotoHint"));
        setStatusOk(null);
      }
    }

    start();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      stream?.getTracks().forEach((tr) => tr.stop());
      if (video) video.srcObject = null;
    };
  }, []);

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    setStatus(t("scanLooking"));
    setStatusOk(null);
    try {
      const bitmap = await createImageBitmap(file);
      const code = await detectBarcode(bitmap);
      bitmap.close();
      if (!code) {
        setStatus(t("scanNotFound"));
        setStatusOk(false);
        return;
      }
      const result = await onCodeRef.current(code);
      setStatus(result.message);
      setStatusOk(result.ok);
      if (result.close) onCloseRef.current();
    } catch {
      setStatus(t("scanNotFound"));
      setStatusOk(false);
    }
  }

  return createPortal(
    <div className="scan-overlay" role="dialog" aria-modal="true" aria-label={t("scanBarcode")}>
      <div className="scan-video-wrap">
        <video ref={videoRef} autoPlay playsInline muted />
        <div className="scan-reticle" />
      </div>
      <div className="scan-toolbar">
        <p className={`scan-status${statusOk === true ? " ok" : statusOk === false ? " bad" : ""}`}>{status}</p>
        {camError ? <p className="muted">{camError}</p> : <p className="muted">{t("scanPoint")}</p>}
        <div className="row">
          <button className="btn ghost" type="button" onClick={() => fileRef.current?.click()}>
            {t("scanUsePhoto")}
          </button>
          <button className="btn" type="button" onClick={onClose}>
            {t("scanClose")}
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            const file = e.currentTarget.files?.[0];
            e.currentTarget.value = "";
            onPhoto(file);
          }}
        />
      </div>
    </div>,
    document.body,
  );
}
