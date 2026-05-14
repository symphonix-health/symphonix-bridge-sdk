import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve("C:/Users/hgeec/github/symphonix-bridge-sdk");
const outDir = path.join(root, "outputs", "patient_identity");
const renderDir = path.join(outDir, "xlsx_rendered");
const requirementsPath = path.join(root, "tests", "harness", "patient_identity", "requirements_matrix.json");
const scenariosPath = path.join(root, "tests", "harness", "patient_identity", "patient_identity_scenarios.json");
const outputPath = path.join(outDir, "Symphonix_Patient_Identity_Requirements_Matrix.xlsx");

await fs.mkdir(renderDir, { recursive: true });

const requirements = JSON.parse(await fs.readFile(requirementsPath, "utf8"));
const scenarios = JSON.parse(await fs.readFile(scenariosPath, "utf8"));

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const reqSheet = workbook.worksheets.add("Requirements");
const scenarioSheet = workbook.worksheets.add("Scenarios");
const backlogSheet = workbook.worksheets.add("Migration Backlog");
const sourceSheet = workbook.worksheets.add("Source Notes");

const reqRows = requirements.requirements.map((r) => [
  r.requirement_id,
  r.priority,
  r.family,
  r.category,
  r.title,
  r.statement,
  r.scenario_ids.length,
  r.scenario_ids.join(", "),
]);

const scenarioRows = scenarios.scenarios.map((s) => [
  s.use_case_id,
  s.scenario_category,
  s.priority,
  s.subsystem,
  s.requirement_ids.join(", "),
  s.title,
  s.automation_status,
  s.estimated_duration_seconds,
  s.expected_events.map((event) => event.topic).join(", "),
]);

const families = [...new Set(requirements.requirements.map((r) => r.family))].sort();
const familyRows = families.map((family) => [
  family,
  requirements.requirements.filter((r) => r.family === family).length,
]);
const priorityRows = ["P0", "P1", "P2"].map((priority) => [
  priority,
  requirements.requirements.filter((r) => r.priority === priority).length,
]);

function writeMatrix(sheet, startRow, startCol, rows) {
  const width = Math.max(...rows.map((row) => row.length));
  const normalized = rows.map((row) => [...row, ...Array(width - row.length).fill("")]);
  sheet.getRangeByIndexes(startRow, startCol, normalized.length, width).values = normalized;
}

function header(range) {
  range.format = {
    fill: "#0B5D5E",
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
}

function body(range) {
  range.format = {
    fill: "#FFFFFF",
    font: { color: "#1F2937" },
    verticalAlignment: "top",
    wrapText: true,
  };
}

summary.showGridLines = false;
writeMatrix(summary, 0, 0, [["Symphonix Patient Identity Closed Loop", "", "", "", "", ""]]);
summary.getRange("A1:F1").merge();
summary.getRange("A1:F1").format = {
  fill: "#12343B",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "left",
};
writeMatrix(summary, 2, 0, [
  ["Metric", "Value", "Notes"],
  ["Canonical identifier", "SPID", "Symphonix Patient Identifier"],
  ["FHIR identifier system", requirements.metadata.canonical_identifier_system, "Internal master identity namespace"],
  ["Requirement count", requirements.requirements.length, "All rows trace to scenarios"],
  ["Scenario count", scenarios.scenarios.length, "Positive, negative, and edge coverage"],
  ["P0 requirements", priorityRows.find((r) => r[0] === "P0")[1], "Safety-critical and migration-critical"],
  ["Static enforcement", "Opt-in", "Set SYMPHONIX_PATIENT_IDENTITY_ENFORCE=1 after repo migration"],
]);
header(summary.getRange("A3:C3"));
body(summary.getRange("A4:C9"));

writeMatrix(summary, 11, 0, [["Requirements By Family", "Count"], ...familyRows]);
header(summary.getRange("A12:B12"));
body(summary.getRangeByIndexes(12, 0, familyRows.length, 2));
const chart = summary.charts.add("bar", summary.getRangeByIndexes(11, 0, familyRows.length + 1, 2));
chart.title = "Requirements by Family";
chart.hasLegend = false;
chart.xAxis = { axisType: "textAxis" };
chart.setPosition("D12", "J28");

writeMatrix(reqSheet, 0, 0, [[
  "Requirement ID",
  "Priority",
  "Family",
  "Category",
  "Title",
  "Statement",
  "Scenario Count",
  "Scenario IDs",
], ...reqRows]);
header(reqSheet.getRange("A1:H1"));
body(reqSheet.getRangeByIndexes(1, 0, reqRows.length, 8));
reqSheet.tables.add(`A1:H${reqRows.length + 1}`, true, "RequirementsTable");
reqSheet.freezePanes.freezeRows(1);

writeMatrix(scenarioSheet, 0, 0, [[
  "Use Case ID",
  "Category",
  "Priority",
  "Subsystem",
  "Requirement IDs",
  "Title",
  "Automation Status",
  "Duration Sec",
  "Expected Events",
], ...scenarioRows]);
header(scenarioSheet.getRange("A1:I1"));
body(scenarioSheet.getRangeByIndexes(1, 0, scenarioRows.length, 9));
scenarioSheet.tables.add(`A1:I${scenarioRows.length + 1}`, true, "ScenariosTable");
scenarioSheet.freezePanes.freezeRows(1);

writeMatrix(backlogSheet, 0, 0, [[
  "Repo / Area",
  "Current Pattern",
  "Target Change",
  "Priority",
  "Readiness Gate",
], [
  "BulletTrain Client Registry",
  "mpiId UUID, nationalID, duplicate/confusion tables",
  "Make SPID the clinical patient id; preserve mpiId and nationalID as aliases; add outbox lifecycle events",
  "P0",
  "Creation emits patient.identity.created with SPID and idempotency key",
], [
  "BulletTrain Shared HealthRecord",
  "Local patient_id and PAT-* creation",
  "Consume registry creation events; reject local patient creation and invalid SPID writes",
  "P0",
  "No generate_id(\"PAT-\") path remains for patients",
], [
  "Appointment / Screening / EPS / Maternity / Triage siblings",
  "PAT-* and nhs_number field usage",
  "Rename internal identity fields to patient_id/SPID and keep NHS Number as external alias only",
  "P0",
  "Static harness enforce mode has zero findings",
], [
  "Bridge SDK / Nexus A2A",
  "Canonical envelope has no explicit patient identity metadata",
  "Add patient_id, identifier_system, identity_version, lifecycle_status to patient-data envelopes",
  "P1",
  "Adapter tests extract SPID from FHIR and metadata",
], [
  "Agent workspaces",
  "Identity reasoning possible without hard guardrails",
  "Agents recommend only; merge, split, restriction removal, and death correction require human approval",
  "P0",
  "Unauthorized A2A identity mutation is denied",
]]);
header(backlogSheet.getRange("A1:E1"));
body(backlogSheet.getRange("A2:E6"));
backlogSheet.tables.add("A1:E6", true, "MigrationBacklogTable");
backlogSheet.freezePanes.freezeRows(1);

writeMatrix(sourceSheet, 0, 0, [[
  "Source",
  "Use In Architecture",
  "URL / Path",
], [
  "NHS Personal Demographics Service",
  "PDS as national master demographic database and NBO data-quality model",
  "https://digital.nhs.uk/services/personal-demographics-service",
], [
  "NHS PDS National Back Office",
  "Data quality incidents, duplicate records, confused records, incorrect death status",
  "https://digital.nhs.uk/services/personal-demographics-service/national-back-office-for-the-personal-demographics-service",
], [
  "NHS Data Dictionary",
  "10-digit modulus-11 checksum pattern",
  "https://v2.datadictionary.nhs.uk/data_dictionary/data_field_notes/n/nhs_number_de.asp%40shownav%3D0.html",
], [
  "NHS access restriction guidance",
  "Sensitive status / S-flag handling as modern stop-note equivalent",
  "https://digital.nhs.uk/services/personal-demographics-service/restricting-access-to-a-patients-demographic-record",
], [
  "NHS Notify",
  "Suppression for flagged records and patient death status",
  "https://webcms.prod.nhsnotify.national.nhs.uk/using-nhs-notify/recipients-you-cannot-message",
], [
  "Bridge SDK architecture doc",
  "Target architecture, migration plan, and harness commands",
  "docs/architecture/patient-identity-closed-loop.md",
]]);
header(sourceSheet.getRange("A1:C1"));
body(sourceSheet.getRange("A2:C7"));
sourceSheet.tables.add("A1:C7", true, "SourceNotesTable");
sourceSheet.freezePanes.freezeRows(1);

for (const sheet of [summary, reqSheet, scenarioSheet, backlogSheet, sourceSheet]) {
  const used = sheet.getUsedRange();
  used.format.font = { name: "Arial", size: 10, color: "#1F2937" };
  used.format.wrapText = true;
}

summary.getRange("A:C").format.columnWidthPx = 210;
summary.getRange("D:J").format.columnWidthPx = 120;
reqSheet.getRange("A:A").format.columnWidthPx = 140;
reqSheet.getRange("B:D").format.columnWidthPx = 95;
reqSheet.getRange("E:E").format.columnWidthPx = 210;
reqSheet.getRange("F:F").format.columnWidthPx = 420;
reqSheet.getRange("G:H").format.columnWidthPx = 150;
scenarioSheet.getRange("A:A").format.columnWidthPx = 190;
scenarioSheet.getRange("B:D").format.columnWidthPx = 115;
scenarioSheet.getRange("E:E").format.columnWidthPx = 230;
scenarioSheet.getRange("F:F").format.columnWidthPx = 300;
scenarioSheet.getRange("G:I").format.columnWidthPx = 160;
backlogSheet.getRange("A:A").format.columnWidthPx = 200;
backlogSheet.getRange("B:C").format.columnWidthPx = 300;
backlogSheet.getRange("D:D").format.columnWidthPx = 75;
backlogSheet.getRange("E:E").format.columnWidthPx = 280;
sourceSheet.getRange("A:A").format.columnWidthPx = 210;
sourceSheet.getRange("B:B").format.columnWidthPx = 360;
sourceSheet.getRange("C:C").format.columnWidthPx = 460;

summary.getRange("A1:F1").format = {
  fill: "#12343B",
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "left",
};
header(summary.getRange("A3:C3"));
header(summary.getRange("A12:B12"));
header(reqSheet.getRange("A1:H1"));
header(scenarioSheet.getRange("A1:I1"));
header(backlogSheet.getRange("A1:E1"));
header(sourceSheet.getRange("A1:C1"));

const inspectSummary = await workbook.inspect({
  kind: "table",
  range: "Summary!A1:J28",
  include: "values,formulas",
  tableMaxRows: 28,
  tableMaxCols: 10,
  maxChars: 6000,
});
console.log(inspectSummary.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

for (const sheetName of ["Summary", "Requirements", "Scenarios", "Migration Backlog", "Source Notes"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(renderDir, `${sheetName.replaceAll(" ", "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(outputPath);
process.exit(0);
