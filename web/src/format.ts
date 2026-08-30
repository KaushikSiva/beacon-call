export function confidenceLabel(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function incidentTime(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(iso));
}

export function statusLabel(status: string): string {
  return status.replaceAll("_", " ").toUpperCase();
}
