"""
universal_churn/config.py
All configuration constants. Nothing here does computation — only data.
"""
from __future__ import annotations
from pathlib import Path

# ── Versioning ────────────────────────────────────────────────
PIPELINE_VERSION           = "1.0.0"
SECTOR_MODEL_VERSION       = "1.0.0"
UNIVERSAL_MODEL_VERSION    = "1.0.0"
NORMALIZATION_VERSION      = "1.0.0"
COVERAGE_ALGORITHM_VERSION = "1.0.0"

# ── Output paths ──────────────────────────────────────────────
UNIVERSAL_MODEL_PATH      = Path('outputs/universal/universal_xgb_model.pkl')
UNIVERSAL_SCALER_PATH     = Path('outputs/universal/universal_scaler.pkl')
UNIVERSAL_FEATURES_PATH   = Path('outputs/universal/universal_features.csv')
UNIVERSAL_LABEL_PATH      = Path('outputs/universal/universal_label_encoders.pkl')
UNIVERSAL_NORM_STATS_PATH = Path('outputs/universal/universal_norm_stats.pkl')

# ── Sector pipeline configuration ─────────────────────────────
SECTOR_CONFIG = {
    'telecom': {
        'data_path': 'data/telecom/WA_Fn-UseC_-Telco-Customer-Churn.csv',
        'target_col': 'Churn',
        'drop_cols': ['customerID'],
        'binary_map': {
            'Yes': 1, 'No': 0,
            'No phone service': 0, 'No internet service': 0,
            'Male': 1, 'Female': 0,
        },
        'ohe_cols': ['Contract', 'InternetService', 'PaymentMethod'],
        'scale_cols': ['tenure', 'MonthlyCharges', 'TotalCharges'],
        'model_path': 'outputs/universal/sector_models/telecom_best.pkl',
        'scaler_path': 'outputs/universal/sector_scalers/telecom_scaler.pkl',
        'features_path': 'outputs/universal/sector_features/telecom_features.csv',
    },
    'ecommerce': {
        'data_path': 'data/ecommerce/ECommerce.csv',
        'target_col': 'Churn',
        'drop_cols': ['CustomerID'],
        'binary_map': {},
        'ohe_cols': [],
        'scale_cols': [
            'Tenure', 'CityTier', 'WarehouseToHome', 'HourSpendOnApp',
            'NumberOfDeviceRegistered', 'SatisfactionScore', 'NumberOfAddress',
            'Complain', 'OrderAmountHikeFromlastYear', 'CouponUsed',
            'OrderCount', 'DaySinceLastOrder', 'CashbackAmount',
        ],
        'model_path': 'outputs/universal/sector_models/ecommerce_best.pkl',
        'scaler_path': 'outputs/universal/sector_scalers/ecommerce_scaler.pkl',
        'features_path': 'outputs/universal/sector_features/ecommerce_features.csv',
    },
    'banking': {
        'data_path': 'data/banking/Churn_Modelling.csv',
        'target_col': 'Exited',
        'drop_cols': ['RowNumber', 'CustomerId', 'Surname'],
        'binary_map': {'Male': 1, 'Female': 0},
        'label_encode_cols': ['Geography'],
        'ohe_cols': [],
        'scale_cols': [
            'CreditScore', 'Age', 'Tenure', 'Balance',
            'NumOfProducts', 'EstimatedSalary',
        ],
        'model_path': 'outputs/universal/sector_models/banking_best.pkl',
        'scaler_path': 'outputs/universal/sector_scalers/banking_scaler.pkl',
        'features_path': 'outputs/universal/sector_features/banking_features.csv',
    },
    'healthcare': {
        'data_path': 'data/healthcare/health_churn.csv',
        'target_col': 'Churned',
        'drop_cols': ['PatientID', 'Last_Interaction_Date'],
        'binary_map': {'Yes': 1, 'No': 0, 'Male': 1, 'Female': 0},
        'ohe_cols': ['State', 'Specialty', 'Insurance_Type'],
        'scale_cols': [
            'Age', 'Tenure_Months', 'Visits_Last_Year', 'Missed_Appointments',
            'Days_Since_Last_Visit', 'Overall_Satisfaction',
            'Wait_Time_Satisfaction', 'Staff_Satisfaction', 'Provider_Rating',
            'Avg_Out_Of_Pocket_Cost', 'Billing_Issues', 'Portal_Usage',
            'Referrals_Made', 'Distance_To_Facility_Miles',
        ],
        'model_path': 'outputs/universal/sector_models/healthcare_best.pkl',
        'scaler_path': 'outputs/universal/sector_scalers/healthcare_scaler.pkl',
        'features_path': 'outputs/universal/sector_features/healthcare_features.csv',
    },
}

# ── Coverage scoring weights (5=critical → 1=minor) ───────────
SECTOR_FEATURE_WEIGHTS: dict[str, dict[str, int]] = {
    'telecom': {
        'Contract': 5, 'tenure': 5, 'MonthlyCharges': 5, 'TotalCharges': 4,
        'InternetService': 4, 'TechSupport': 3, 'OnlineSecurity': 3,
        'PaymentMethod': 3, 'MultipleLines': 2, 'OnlineBackup': 2,
        'DeviceProtection': 2, 'StreamingTV': 2, 'StreamingMovies': 2,
        'PaperlessBilling': 1, 'SeniorCitizen': 1, 'Partner': 1,
        'Dependents': 1, 'PhoneService': 1, 'gender': 1,
    },
    'banking': {
        'NumOfProducts': 5, 'Age': 5, 'Balance': 5, 'IsActiveMember': 5,
        'Geography': 4, 'CreditScore': 4, 'Tenure': 4, 'EstimatedSalary': 3,
        'HasCrCard': 2, 'Gender': 1,
    },
    'ecommerce': {
        'Tenure': 5, 'Complain': 5, 'DaySinceLastOrder': 5,
        'SatisfactionScore': 4, 'OrderCount': 4, 'CashbackAmount': 4,
        'OrderAmountHikeFromlastYear': 3, 'CouponUsed': 3,
        'NumberOfDeviceRegistered': 3, 'HourSpendOnApp': 3,
        'WarehouseToHome': 2, 'NumberOfAddress': 2, 'CityTier': 1,
        'PreferredLoginDevice': 1, 'PreferredPaymentMode': 1,
        'PreferedOrderCat': 1, 'MaritalStatus': 1, 'Gender': 1,
    },
    'healthcare': {
        'Days_Since_Last_Visit': 5, 'Billing_Issues': 5,
        'Overall_Satisfaction': 5, 'Visits_Last_Year': 5,
        'Avg_Out_Of_Pocket_Cost': 4, 'Age': 4, 'Missed_Appointments': 4,
        'Wait_Time_Satisfaction': 3, 'Staff_Satisfaction': 3,
        'Provider_Rating': 3, 'Distance_To_Facility_Miles': 3,
        'Tenure_Months': 3, 'Portal_Usage': 2, 'Referrals_Made': 2,
        'Insurance_Type': 2, 'Specialty': 2, 'Gender': 1, 'State': 1,
    },
}

# ── Sector detection signatures ───────────────────────────────
SECTOR_SIGNATURES = {
    'telecom': [
        {'monthlycharges', 'totalcharges', 'contract', 'internetservice',
         'phoneservice', 'multiplelines', 'streamingtv'},
    ],
    'ecommerce': [
        {'cashbackamount', 'daysincelastorder', 'couponused', 'ordercount',
         'warehousetohome', 'hourspendonapp', 'preferredpaymentmode'},
    ],
    'banking': [
        {'rownumber', 'surname', 'creditscore', 'geography', 'numofproducts',
         'hascrcard', 'isactivemember', 'estimatedsalary', 'exited'},
    ],
    'healthcare': [
        {'patientid', 'specialty', 'insurancetype', 'visitslastyear',
         'missedappointments', 'overallsatisfaction', 'waittimesatisfaction',
         'staffsatisfaction', 'providerrating', 'avgoutofpocketcost',
         'billingissues', 'portalusage', 'referralsmade',
         'distancetofacilitymiles', 'churned'},
        {'medicalcondition', 'policytype', 'monthlypremium',
         'frequencyofvisits', 'claimhistorycount', 'customersupportcalls'},
    ],
}
MIN_SIGNATURE_HITS = 2

# ── Sector-specific decision thresholds ───────────────────────
SECTOR_THRESHOLDS = {
    'telecom': 0.50, 'ecommerce': 0.35, 'banking': 0.50, 'healthcare': 0.65,
}

# ── Universal feature list ────────────────────────────────────
UNIVERSAL_FEATURES = [
    'tenure_normalized', 'charge_normalized', 'has_complaint',
    'satisfaction_score', 'is_active', 'num_products_services',
    'is_senior_or_high_risk', 'has_support', 'contract_stability',
    'payment_auto', 'engagement_score', 'coupon_dependency',
    'cashback_engagement', 'recency_score', 'convenience_score',
    'lockin_risk', 'dormant_loyalty_risk', 'missed_appt_rate',
    'composite_satisfaction', 'billing_friction', 'care_accessibility',
    'referral_engagement',
]

# ── Columns used for per-sector normalization maxima ──────────
SECTOR_NORM_COLUMNS = {
    'telecom': ['tenure', 'MonthlyCharges'],
    'ecommerce': ['Tenure', 'CashbackAmount', 'OrderCount', 'CouponUsed',
                  'DaySinceLastOrder', 'WarehouseToHome'],
    'banking': ['Tenure', 'Balance', 'CreditScore'],
    'healthcare': [
        'Tenure_Months', 'Avg_Out_Of_Pocket_Cost', 'Overall_Satisfaction',
        'Visits_Last_Year', 'Days_Since_Last_Visit',
        'Distance_To_Facility_Miles', 'Wait_Time_Satisfaction',
        'Staff_Satisfaction', 'Provider_Rating', 'Missed_Appointments',
        'Billing_Issues', 'Referrals_Made', 'Portal_Usage',
        'FrequencyOfVisits', 'MonthlyPremium', 'ClaimHistoryCount',
        'CustomerSupportCalls',
    ],
}

# ── Global concept translation map ────────────────────────────
GLOBAL_CONCEPT_MAP = {
    'customerid': 'customerid', 'patientid': 'customerid',
    'customer id': 'customerid', 'exited': 'churn', 'churned': 'churn',
    'creditscore': 'creditscore', 'numofproducts': 'numofproducts',
    'isactivemember': 'isactivemember', 'frequencyofvisits': 'isactivemember',
    'estimatedsalary': 'estimatedsalary', 'warehousetohome': 'warehousetohome',
    'hourspendonapp': 'hourspendonapp',
    'numberofdeviceregistered': 'numberofdeviceregistered',
    'satisfactionscore': 'satisfactionscore',
    'daysincelastorder': 'daysincelastorder',
    'days_since_last_visit': 'daysincelastorder',
    'complain': 'complain', 'customersupportcalls': 'complain',
    'billing_issues': 'complain', 'cashbackamount': 'cashbackamount',
    'monthlycharges': 'cashbackamount', 'monthlypremium': 'cashbackamount',
    'avg_out_of_pocket_cost': 'cashbackamount', 'tenure': 'tenure',
    'tenure_months': 'tenure', 'contract': 'contract', 'policytype': 'contract',
}