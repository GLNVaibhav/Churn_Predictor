import { SectorConfigSetting, UploadedDatasetPreview } from "@/lib/types";

export const sectorConfigSettings: SectorConfigSetting[] = [
  {
    sector: "telecom",
    targetCol: "Churn",
    modelPath: "outputs/universal/sector_models/telecom_best.pkl",
    trained: true,
    routingThresholdGreen: 0.75,
    routingThresholdYellow: 0.45,
  },
  {
    sector: "banking",
    targetCol: "Exited",
    modelPath: "outputs/universal/sector_models/banking_best.pkl",
    trained: true,
    routingThresholdGreen: 0.75,
    routingThresholdYellow: 0.45,
  },
  {
    sector: "healthcare",
    targetCol: "Attrition",
    modelPath: "outputs/universal/sector_models/healthcare_best.pkl",
    trained: true,
    routingThresholdGreen: 0.70,
    routingThresholdYellow: 0.40,
  },
  {
    sector: "ecommerce",
    targetCol: "Churned",
    modelPath: "outputs/universal/sector_models/ecommerce_best.pkl",
    trained: true,
    routingThresholdGreen: 0.75,
    routingThresholdYellow: 0.45,
  },
];

export const uploadPreview: UploadedDatasetPreview = {
  fileName: "real_world_telecom_customers.csv",
  rowCount: 1204,
  columnCount: 19,
  detectedSector: "telecom",
  detectionConfidence: 92,
  columns: [
    { name: "customerID", inferredType: "text", nullPercentage: 0, sampleValues: ["7590-VHVEG", "5575-GNVDE"] },
    { name: "tenure", inferredType: "numeric", nullPercentage: 0, sampleValues: ["1", "34", "2"] },
    { name: "MonthlyCharges", inferredType: "numeric", nullPercentage: 0, sampleValues: ["29.85", "56.95"] },
    { name: "Contract", inferredType: "categorical", nullPercentage: 0, sampleValues: ["Month-to-month", "One year"] },
    { name: "InternetService", inferredType: "categorical", nullPercentage: 1.2, sampleValues: ["DSL", "Fiber optic"] },
    { name: "TechSupport", inferredType: "categorical", nullPercentage: 0, sampleValues: ["No", "Yes"] },
    { name: "Support_Contacts", inferredType: "numeric", nullPercentage: 4.5, sampleValues: ["2", "0", "5"] },
  ],
};
