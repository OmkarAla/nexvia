import { Enums, RenderingEngine, init as coreInit } from "@cornerstonejs/core";
import { init as dicomLoaderInit } from "@cornerstonejs/dicom-image-loader";
import { useEffect, useRef, useState } from "react";

import { getImageIds } from "../api";

interface StackViewportLike {
  setStack: (imageIds: string[], index: number) => Promise<void>;
  render: () => void;
}

let initialization: Promise<void> | null = null;

function initialize(): Promise<void> {
  if (!initialization) {
    initialization = (async () => {
      await coreInit();
      await dicomLoaderInit();
    })();
  }
  return initialization;
}

interface Props {
  studyUid: string;
  overlay: string | null;
}

export function DicomViewer({ studyUid, overlay }: Props) {
  const elementRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let engine: RenderingEngine | null = null;
    let cancelled = false;
    setReady(false);
    setError(null);

    void (async () => {
      try {
        await initialize();
        const imageIds = await getImageIds(studyUid);
        if (!imageIds.length) throw new Error("No DICOM instances found for this study");
        if (cancelled || !elementRef.current) return;

        const viewportId = `viewport-${studyUid}`;
        engine = new RenderingEngine(`engine-${studyUid}`);
        engine.enableElement({
          viewportId,
          type: Enums.ViewportType.STACK,
          element: elementRef.current,
          defaultOptions: { background: [0, 0, 0] },
        });
        const viewport = engine.getViewport(viewportId) as unknown as StackViewportLike;
        await viewport.setStack(imageIds, Math.floor(imageIds.length / 2));
        viewport.render();
        if (!cancelled) setReady(true);
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
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
      {overlay && ready && <img className="viewer-overlay" src={overlay} alt="Grad-CAM overlay" />}
      {!ready && !error && <p className="viewer-status">Loading DICOM…</p>}
      {error && <p className="viewer-error">{error}</p>}
    </div>
  );
}
