/** Shared sector display labels — single source of truth. */
export const SECTOR_LABELS: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  finance: "Banking",
  ecommerce: "E-Commerce",
  healthcare: "Healthcare",
  retail: "Retail",
};

export function sectorLabel(sector?: string | null): string {
  if (!sector) return "Unknown";
  const key = sector.toLowerCase();
  return SECTOR_LABELS[key] || sector.charAt(0).toUpperCase() + sector.slice(1);
}
