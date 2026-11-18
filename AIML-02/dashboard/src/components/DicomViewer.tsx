import { useEffect, useRef, useState } from "react";

import { API_URL, getImageIds } from "../api";

interface StackViewportLike {
  setStack: (imageIds: string[], index: number) => Promise<void>;
  render: () => void;
}

interface Props {
  studyUid: string;
  overlay: string | null;
}

export function DicomViewer({ studyUid, overlay }: Props) {
  const elementRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"loading" | "cornerstone" | "preview">("loading");

  useEffect(() => {
    let engine: { destroy: () => void } | null = null;
    let cancelled = false;
    setMode("loading");
    setError(null);

    void (async () => {
      try {
        // Cornerstone3D is imported lazily because its codec bundle is
        // optional at runtime; the rendered preview is the fallback.
        const core = await import("@cornerstonejs/core");
        const loader = await import("@cornerstonejs/dicom-image-loader");
        await core.init();
        await loader.init();

        const imageIds = await getImageIds(studyUid);
        if (!imageIds.length) throw new Error("No DICOM instances found");
        if (cancelled || !elementRef.current) return;

        const viewportId = `viewport-${studyUid}`;
        const renderingEngine = new core.RenderingEngine(`engine-${studyUid}`);
        engine = renderingEngine;
        renderingEngine.enableElement({
          viewportId,
          type: core.Enums.ViewportType.STACK,
          element: elementRef.current,
          defaultOptions: { background: [0, 0, 0] },
        });
        const viewport = renderingEngine.getViewport(viewportId) as unknown as StackViewportLike;
        await viewport.setStack(imageIds, Math.floor(imageIds.length / 2));
        viewport.render();
        if (!cancelled) setMode("cornerstone");
      } catch {
        if (!cancelled) setMode("preview");
      }
    })();

    return () => {
      cancelled = true;
      engine?.destroy();
    };
  }, [studyUid]);

  return (
    <div className="viewer-wrap">
      <div ref={elementRef} className="viewer-canvas" />
      {mode === "preview" && (
        <img
          className="viewer-image"
          src={`${API_URL}/studies/${studyUid}/preview`}
          alt="Rendered DICOM slice"
          onError={() => setError("No preview available for this study")}
        />
      )}
      {overlay && mode !== "loading" && (
        <img className="viewer-overlay" src={overlay} alt="Grad-CAM overlay" />
      )}
      {mode === "loading" && !error && <p className="viewer-status">Loading DICOM…</p>}
      {error && <p className="viewer-error">{error}</p>}
    </div>
  );
}
