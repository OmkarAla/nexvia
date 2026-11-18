import type { DecisionResult, Study } from "./types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const ORTHANC_URL = import.meta.env.VITE_ORTHANC_URL ?? "http://localhost:8042";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export function getStudies(status?: string): Promise<{ studies: Study[] }> {
  const query = status ? `?status=${status}` : "";
  return request<{ studies: Study[] }>(`/studies${query}`);
}

export function getStudy(id: string): Promise<{ study: Study }> {
  return request<{ study: Study }>(`/studies/${id}`);
}

export function decide(
  id: string,
  body: { decision: "approve" | "reject"; comment: string; reviewer: string },
): Promise<DecisionResult> {
  return request<DecisionResult>(`/studies/${id}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function overlayUrl(path: string): string {
  return `${API_URL}/overlays/${path}`;
}

interface DicomJson {
  0x0020000e?: { Value: string[] };
  "0020000E"?: { Value: string[] };
  0x00080018?: { Value: string[] };
  "00080018"?: { Value: string[] };
}

export async function getImageIds(studyUid: string): Promise<string[]> {
  try {
    const seriesResponse = await fetch(
      `${ORTHANC_URL}/dicom-web/studies/${studyUid}/series`,
    );
    const series = (await seriesResponse.json()) as DicomJson[];
    if (series.length) {
      const seriesUid = series[0]["0020000E"]?.Value?.[0];
      if (seriesUid) {
        const instanceResponse = await fetch(
          `${ORTHANC_URL}/dicom-web/studies/${studyUid}/series/${seriesUid}/instances`,
        );
        const instances = (await instanceResponse.json()) as DicomJson[];
        const ids = instances
          .map((item) => item["00080018"]?.Value?.[0])
          .filter((uid): uid is string => Boolean(uid))
          .map((uid) => `wadouri:${ORTHANC_URL}/instances/${uid}/file`);
        if (ids.length) return ids;
      }
    }
  } catch {
    // Orthanc is not running; fall through to the committed demo files.
  }

  const fallback = await fetch(`${API_URL}/demo/studies`);
  if (!fallback.ok) return [];
  const payload = (await fallback.json()) as {
    studies: Array<{ study_uid: string; image_urls: string[] }>;
  };
  const match = payload.studies.find((study) => study.study_uid === studyUid);
  return (match?.image_urls ?? []).map((url) => `wadouri:${API_URL}${url}`);
}
