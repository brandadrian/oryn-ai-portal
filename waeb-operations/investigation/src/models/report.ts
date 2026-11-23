import * as zod from "zod";

export const reportSchema = zod.object({
  zusammenfassung: zod.string().min(1),
  root_cause: zod.object({
    aussage: zod.string().min(1),
    sicherheit: zod.enum(["hoch", "mittel", "niedrig", "unbekannt"]),
    begruendung: zod.string().min(1),
  }),
  belege: zod.array(zod.object({
    id: zod.string().min(1),
    befund: zod.string().min(1),
  })),
  fix_vorschlaege: zod.array(zod.string()),
  offene_fragen: zod.array(zod.string()),
});

export type Report = zod.infer<typeof reportSchema>;

export function validateEvidence(report: Report, successfulIds: Set<string>): void {
  for (const evidence of report.belege) {
    if (!successfulIds.has(evidence.id)) {
      throw new Error(`Report verweist auf unbekannten oder fehlgeschlagenen Beleg: ${evidence.id}`);
    }
  }
  if (report.root_cause.sicherheit !== "unbekannt" && report.belege.length === 0) {
    throw new Error("Report nennt eine Ursache ohne Belege.");
  }
}
