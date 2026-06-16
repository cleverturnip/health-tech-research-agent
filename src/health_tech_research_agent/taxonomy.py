
from __future__ import annotations

from pathlib import Path
import re
import pandas as pd


def safe_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def normalize_key(value) -> str:
    text = safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_tags(value) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    pieces = re.split(r"[;,|]", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def join_tags(tags) -> str:
    clean = []
    seen = set()
    for tag in tags or []:
        tag = safe_text(tag)
        if not tag:
            continue
        if tag not in seen:
            clean.append(tag)
            seen.add(tag)
    return "; ".join(clean)


def repo_dir_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def default_taxonomy_dir() -> Path:
    return repo_dir_from_module() / "taxonomy"


def read_taxonomy_csv(taxonomy_dir: Path, filename: str) -> pd.DataFrame:
    path = taxonomy_dir / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path).fillna("")


def load_taxonomy_tables(taxonomy_dir: str | Path | None = None) -> dict[str, pd.DataFrame]:
    taxonomy_dir = Path(taxonomy_dir) if taxonomy_dir else default_taxonomy_dir()

    return {
        "market_segments": read_taxonomy_csv(taxonomy_dir, "market_segments.csv"),
        "subsegment_tags": read_taxonomy_csv(taxonomy_dir, "subsegment_tags.csv"),
        "product_models": read_taxonomy_csv(taxonomy_dir, "product_models.csv"),
        "distribution_models": read_taxonomy_csv(taxonomy_dir, "distribution_models.csv"),
        "data_input_layers": read_taxonomy_csv(taxonomy_dir, "data_input_layers.csv"),
        "company_overrides": read_taxonomy_csv(taxonomy_dir, "company_taxonomy_overrides.csv"),
    }


def code_label_maps(tables):
    market_segments = tables.get("market_segments", pd.DataFrame())

    code_to_label = {}
    label_to_code = {}

    if not market_segments.empty:
        for _, row in market_segments.iterrows():
            code = safe_text(row.get("segment_code"))
            label = safe_text(row.get("segment_label"))
            if code:
                code_to_label[code] = label or code
                label_to_code[normalize_key(code)] = code
                label_to_code[normalize_key(label)] = code

    return code_to_label, label_to_code


def allowed_codes(df: pd.DataFrame, code_col: str) -> set[str]:
    if df.empty or code_col not in df.columns:
        return set()
    return set(df[code_col].astype(str).str.strip().replace("", pd.NA).dropna().tolist())


def normalize_code(value, allowed: set[str], label_to_code: dict[str, str] | None = None) -> str:
    text = safe_text(value)

    if not text:
        return ""

    if text in allowed:
        return text

    upper = text.upper().strip()
    if upper in allowed:
        return upper

    if label_to_code:
        mapped = label_to_code.get(normalize_key(text), "")
        if mapped in allowed:
            return mapped

    return ""


def make_haystack(row) -> str:
    fields = [
        "company",
        "business_model_classification",
        "final_recommendation",
        "final_takeaway",
        "commercial_scale_assessment",
        "pmf_scale_assessment",
        "commercial_scale_finding",
        "payer_institutional_finding",
        "outcomes_finding",
        "funding_finding",
        "review_notes",
        "priority_review_note",
        "why_now_or_why_not",
    ]

    return " | ".join(safe_text(row.get(field, "")) for field in fields).lower()


PRIMARY_KEYWORD_RULES = [
    (
        "PROVIDER_INFRASTRUCTURE_AI",
        [
            r"clinical ai",
            r"medical ai",
            r"ai scribe",
            r"ambient scribe",
            r"clinical documentation",
            r"prior auth",
            r"prior authorization",
            r"provider workflow",
            r"revenue cycle",
            r"\brcm\b",
            r"coding automation",
            r"clinical decision support",
            r"medical search",
        ],
    ),
    (
        "DIAGNOSTICS_LIFE_SCIENCES",
        [
            r"clinical diagnostic",
            r"clinical diagnostics",
            r"companion diagnostic",
            r"diagnostic.*clinical",
            r"early detection.*clinical",
            r"clinical trial",
            r"real-world evidence",
            r"\brwe\b",
            r"drug discovery",
            r"pharma",
            r"life sciences",
            r"biotech",
        ],
    ),
    (
        "WOMENS_FAMILY_HEALTH",
        [
            r"women.?s health",
            r"reproductive",
            r"fertility",
            r"ivf",
            r"egg freezing",
            r"maternity",
            r"pregnancy",
            r"postpartum",
            r"menopause",
            r"pcos",
            r"hormonal",
            r"ob[- ]?gyn",
            r"pediatric",
            r"family[- ]?building",
            r"family benefits",
        ],
    ),
    (
        "METABOLIC_NUTRITION_HEALTH",
        [
            r"metabolic",
            r"obesity",
            r"weight loss",
            r"weight management",
            r"glp[- ]?1",
            r"glp1",
            r"diabetes",
            r"prediabetes",
            r"cardiometabolic",
            r"\bcgm\b",
            r"glucose",
            r"food as medicine",
            r"nutrition",
            r"dietitian",
            r"dietician",
            r"medically tailored",
            r"food security",
            r"grocery benefit",
        ],
    ),
    (
        "MENTAL_BEHAVIORAL_HEALTH",
        [
            r"mental health",
            r"behavioral health",
            r"therapy",
            r"therapist",
            r"psychiatry",
            r"depression",
            r"anxiety",
            r"substance use",
            r"addiction",
            r"opioid",
            r"alcohol use",
            r"eating disorder",
        ],
    ),
    (
        "SPECIALTY_CONDITION_CARE",
        [
            r"\bgi\b",
            r"gastro",
            r"digestive",
            r"gut health",
            r"\bibs\b",
            r"\bibd\b",
            r"crohn",
            r"colitis",
            r"\bmsk\b",
            r"musculoskeletal",
            r"physical therapy",
            r"virtual pt",
            r"oncology",
            r"cancer",
            r"kidney",
            r"renal",
            r"cardiology",
            r"dermatology",
            r"neurology",
            r"specialty care",
        ],
    ),
    (
        "PRIMARY_LONGITUDINAL_CARE",
        [
            r"primary care",
            r"urgent care",
            r"longitudinal care",
            r"virtual primary",
            r"hybrid primary",
            r"front door",
        ],
    ),
    (
        "SENIOR_HOME_CARE",
        [
            r"senior care",
            r"aging",
            r"caregiver",
            r"home care",
            r"hospital at home",
            r"aging in place",
        ],
    ),
    (
        "CONSUMER_HEALTH_OPTIMIZATION",
        [
            r"consumer health",
            r"health membership",
            r"cash-pay health membership",
            r"cash pay health membership",
            r"preventive wellness",
            r"preventive health",
            r"health optimization",
            r"longevity",
            r"healthspan",
            r"wellness optimization",
            r"consumer.*biomarker",
            r"biomarker.*consumer",
            r"consumer.*lab",
            r"lab.*consumer",
            r"advanced screening",
            r"full-body scan",
            r"full body scan",
            r"sleep",
            r"fitness",
            r"performance",
            r"recovery",
            r"wearable",
            r"smart ring",
            r"biometric",
        ],
    ),
    (
        "CARE_NAVIGATION_ACCESS",
        [
            r"care navigation",
            r"patient advocacy",
            r"care advocacy",
            r"benefits navigation",
            r"care matching",
            r"concierge",
        ],
    ),
    (
        "PAYER_BENEFITS_INFRASTRUCTURE",
        [
            r"health insurance",
            r"benefits platform",
            r"employer benefits",
            r"health plan",
            r"payer infrastructure",
            r"medicaid",
            r"medicare",
            r"value-based care",
            r"value based care",
            r"\bvbc\b",
        ],
    ),
]


SUBSEGMENT_RULES = [
    ("fertility_family_building", [r"fertility", r"ivf", r"egg freezing", r"family[- ]?building"]),
    ("maternity_postpartum", [r"maternity", r"pregnancy", r"postpartum", r"maternal"]),
    ("menopause_midlife", [r"menopause", r"midlife"]),
    ("hormonal_pcos", [r"hormonal", r"pcos"]),
    ("obesity_glp1", [r"obesity", r"weight loss", r"weight management", r"glp[- ]?1", r"glp1"]),
    ("diabetes_cardiometabolic", [r"diabetes", r"prediabetes", r"cardiometabolic"]),
    ("metabolic_behavior_change", [r"metabolic", r"\bcgm\b", r"glucose", r"behavior change"]),
    ("food_as_medicine", [r"food as medicine", r"medically tailored", r"grocery benefit"]),
    ("nutrition_care", [r"nutrition", r"dietitian", r"dietician"]),
    ("gi_digestive", [r"\bgi\b", r"gastro", r"digestive", r"\bibs\b", r"\bibd\b", r"crohn", r"colitis"]),
    ("msk_physical_therapy", [r"\bmsk\b", r"musculoskeletal", r"physical therapy", r"virtual pt"]),
    ("oncology_cancer", [r"oncology", r"cancer"]),
    ("kidney_renal", [r"kidney", r"renal"]),
    ("longevity_prevention", [r"preventive wellness", r"preventive health", r"longevity", r"healthspan", r"health optimization", r"wellness optimization"]),
    ("consumer_labs_biomarkers", [r"consumer.*biomarker", r"biomarker.*consumer", r"consumer.*lab", r"lab.*consumer", r"blood test", r"lab test"]),
    ("advanced_screening", [r"advanced screening", r"full-body scan", r"full body scan", r"screening"]),
    ("sleep", [r"sleep"]),
    ("fitness_performance", [r"fitness", r"performance", r"training"]),
    ("recovery", [r"recovery"]),
    ("therapy_psychiatry", [r"therapy", r"therapist", r"psychiatry", r"mental health"]),
    ("substance_use", [r"substance use", r"addiction", r"opioid", r"alcohol use"]),
    ("eating_disorder", [r"eating disorder"]),
]


PRODUCT_RULES = [
    ("VIRTUAL_CARE", [r"virtual care", r"telehealth", r"telemedicine"]),
    ("HYBRID_CARE", [r"hybrid care", r"in-person", r"clinic", r"home-based"]),
    ("MARKETPLACE_PROVIDER_NETWORK", [r"marketplace", r"provider network", r"clinician network", r"in-network provider"]),
    ("CARE_NAVIGATION_SERVICE", [r"navigation", r"advocacy", r"concierge", r"care matching"]),
    ("COACHING_BEHAVIOR_CHANGE", [r"coaching", r"behavior change", r"habit", r"lifecycle", r"engagement"]),
    ("DEVICE_HARDWARE", [r"device", r"hardware"]),
    ("WEARABLE_COMPANION_APP", [r"wearable", r"smart ring", r"companion app"]),
    ("DIAGNOSTIC_TESTING", [r"diagnostic", r"lab test", r"blood test", r"biomarker", r"screening"]),
    ("DIGITAL_THERAPEUTIC", [r"digital therapeutic", r"digital therapeutics"]),
    ("AI_CLINICAL_WORKFLOW", [r"clinical ai", r"clinical decision support", r"medical ai", r"medical search"]),
    ("AI_ADMIN_WORKFLOW", [r"scribe", r"prior auth", r"coding", r"revenue cycle", r"\brcm\b"]),
    ("BENEFITS_PLATFORM", [r"benefits platform", r"employer benefits", r"health plan"]),
    ("DATA_ANALYTICS_PLATFORM", [r"analytics", r"data platform", r"risk stratification"]),
    ("TRIALS_RWE_PLATFORM", [r"clinical trial", r"real-world evidence", r"\brwe\b"]),
]


DISTRIBUTION_RULES = [
    ("D2C", [r"\bd2c\b", r"direct-to-consumer", r"consumer pays", r"cash-pay", r"cash pay", r"subscription"]),
    ("EMPLOYER", [r"employer", r"workforce", r"employee benefit"]),
    ("PAYER", [r"payer", r"health plan", r"insurer", r"insurance", r"covered lives"]),
    ("HEALTH_SYSTEM", [r"health system", r"hospital", r"provider enterprise"]),
    ("PROVIDER_GROUP", [r"provider group", r"clinician group", r"medical group"]),
    ("GOV_MEDICAID", [r"government", r"medicaid", r"medicare", r"cms"]),
    ("PHARMA", [r"pharma", r"life sciences", r"biotech"]),
    ("B2B2C", [r"b2b2c", r"institutional buyer", r"member-facing", r"patient-facing"]),
    ("MARKETPLACE", [r"marketplace", r"network monetization"]),
]


DATA_INPUT_RULES = [
    ("WEARABLE_BIOMETRICS", [r"wearable", r"smart ring", r"biometric"]),
    ("CGM", [r"\bcgm\b", r"continuous glucose", r"glucose"]),
    ("LABS_BIOMARKERS", [r"lab", r"biomarker", r"blood test"]),
    ("EHR_CLINICAL", [r"\behr\b", r"clinical record", r"medical record"]),
    ("CLAIMS", [r"claims", r"utilization"]),
    ("PATIENT_REPORTED", [r"patient-reported", r"symptom", r"survey", r"reported outcomes"]),
    ("PROVIDER_DOCUMENTATION", [r"documentation", r"clinical note", r"scribe"]),
    ("IMAGING", [r"imaging", r"scan", r"radiology"]),
    ("DEVICE_SENSOR", [r"sensor", r"device data"]),
    ("SELF_LOGGED_BEHAVIOR", [r"self-logged", r"logging", r"food log", r"activity log", r"behavior"]),
]


def match_rules(haystack: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    matches = []
    for code, patterns in rules:
        if any(re.search(pattern, haystack, flags=re.IGNORECASE) for pattern in patterns):
            matches.append(code)
    return matches


def first_rule_match(haystack: str, rules: list[tuple[str, list[str]]]) -> tuple[str, str]:
    for code, patterns in rules:
        for pattern in patterns:
            if re.search(pattern, haystack, flags=re.IGNORECASE):
                return code, pattern
    return "", ""


def validate_tag_list(value, allowed: set[str]) -> list[str]:
    tags = []
    for tag in split_tags(value):
        clean = tag.strip()
        if clean in allowed:
            tags.append(clean)
    return tags


def build_taxonomy_prompt_block(taxonomy_dir: str | Path | None = None) -> str:
    taxonomy_dir = Path(taxonomy_dir) if taxonomy_dir else default_taxonomy_dir()
    path = taxonomy_dir / "llm_taxonomy_prompt_block.txt"

    if path.exists():
        return path.read_text(encoding="utf-8")

    return (
        "CONTROLLED HEALTH-TECH TAXONOMY\n"
        "Choose exactly one primary_market_segment from the approved taxonomy. "
        "Use subsegment_tags, product_model_tags, distribution_model_tags, and data_input_tags for nuance."
    )


def classify_dataframe(df: pd.DataFrame, taxonomy_dir: str | Path | None = None, hard_stop: bool = True) -> pd.DataFrame:
    tables = load_taxonomy_tables(taxonomy_dir)
    code_to_label, label_to_code = code_label_maps(tables)

    market_segments = tables["market_segments"]
    subsegments = tables["subsegment_tags"]
    product_models = tables["product_models"]
    distribution_models = tables["distribution_models"]
    data_layers = tables["data_input_layers"]
    overrides = tables["company_overrides"]

    allowed_primary = allowed_codes(market_segments, "segment_code")
    allowed_subsegments = allowed_codes(subsegments, "tag_code")
    allowed_product = allowed_codes(product_models, "product_model_code")
    allowed_distribution = allowed_codes(distribution_models, "distribution_model_code")
    allowed_data = allowed_codes(data_layers, "data_input_code")

    # Subsegment tags are segment-specific. They should not contradict the selected primary segment.
    subsegment_parent = {}
    if not subsegments.empty and "tag_code" in subsegments.columns and "parent_market_segment" in subsegments.columns:
        for _, sub_row in subsegments.iterrows():
            tag = safe_text(sub_row.get("tag_code"))
            parent = safe_text(sub_row.get("parent_market_segment"))
            if tag and parent:
                subsegment_parent[tag] = parent

    override_by_company = {}
    if not overrides.empty and "company" in overrides.columns:
        for _, row in overrides.iterrows():
            key = normalize_key(row.get("company"))
            if key:
                override_by_company[key] = row.to_dict()

    out = df.copy()

    for col in [
        "primary_market_segment_code",
        "primary_market_segment",
        "market_segment",
        "subsegment_tags",
        "product_model_tags",
        "distribution_model_tags",
        "data_input_tags",
        "taxonomy_assignment_method",
        "taxonomy_assignment_basis",
    ]:
        if col not in out.columns:
            out[col] = ""

    unresolved_rows = []

    for idx, row in out.iterrows():
        company = safe_text(row.get("company"))
        company_key = normalize_key(company)
        haystack = make_haystack(row)

        method = ""
        basis = ""

        primary_code = ""
        subsegment_tags = []
        product_tags = []
        distribution_tags = []
        data_tags = []

        # 1. Exact company override wins.
        if company_key in override_by_company:
            override = override_by_company[company_key]
            primary_code = normalize_code(
                override.get("primary_market_segment", ""),
                allowed_primary,
                label_to_code,
            )
            subsegment_tags = validate_tag_list(override.get("subsegment_tags", ""), allowed_subsegments)
            product_tags = validate_tag_list(override.get("product_model_tags", ""), allowed_product)
            distribution_tags = validate_tag_list(override.get("distribution_model_tags", ""), allowed_distribution)
            data_tags = validate_tag_list(override.get("data_input_tags", ""), allowed_data)
            method = "company_override"
            basis = safe_text(override.get("override_reason")) or "Company override table"

        # 2. LLM-provided taxonomy fields, validated against allowed codes.
        if not primary_code:
            llm_primary = (
                row.get("primary_market_segment_code", "")
                or row.get("primary_market_segment", "")
                or row.get("market_segment", "")
            )
            primary_code = normalize_code(llm_primary, allowed_primary, label_to_code)

            if primary_code:
                method = "llm_validated"
                basis = "LLM/company row field matched approved taxonomy"

                subsegment_tags = validate_tag_list(row.get("subsegment_tags", ""), allowed_subsegments)
                product_tags = validate_tag_list(row.get("product_model_tags", ""), allowed_product)
                distribution_tags = validate_tag_list(row.get("distribution_model_tags", ""), allowed_distribution)
                data_tags = validate_tag_list(row.get("data_input_tags", ""), allowed_data)

        # 3. Deterministic fallback from text.
        if not primary_code:
            primary_code, matched_pattern = first_rule_match(haystack, PRIMARY_KEYWORD_RULES)
            if primary_code:
                method = "keyword_fallback"
                basis = f"Matched pattern: {matched_pattern}"

        if not primary_code:
            primary_code = "OTHER_REVIEW"
            method = "unmapped_review"
            basis = "No override, validated LLM field, or deterministic keyword match"

        # Infer nuance tags when missing.
        if not subsegment_tags:
            subsegment_tags = [
                tag for tag in match_rules(haystack, SUBSEGMENT_RULES)
                if tag in allowed_subsegments
            ]

        if not product_tags:
            product_tags = [
                tag for tag in match_rules(haystack, PRODUCT_RULES)
                if tag in allowed_product
            ]

        if not distribution_tags:
            distribution_tags = [
                tag for tag in match_rules(haystack, DISTRIBUTION_RULES)
                if tag in allowed_distribution
            ]

        if not data_tags:
            data_tags = [
                tag for tag in match_rules(haystack, DATA_INPUT_RULES)
                if tag in allowed_data
            ]

        # Drop subsegment tags whose configured parent does not match the primary segment.
        # This prevents outputs like METABOLIC_NUTRITION_HEALTH + longevity_prevention
        # unless the taxonomy explicitly parents that tag to the metabolic segment.
        subsegment_tags = [
            tag for tag in subsegment_tags
            if not subsegment_parent.get(tag) or subsegment_parent.get(tag) == primary_code
        ]

        primary_label = code_to_label.get(primary_code, primary_code)

        out.at[idx, "primary_market_segment_code"] = primary_code
        out.at[idx, "primary_market_segment"] = primary_label
        out.at[idx, "market_segment"] = primary_label
        out.at[idx, "subsegment_tags"] = join_tags(subsegment_tags)
        out.at[idx, "product_model_tags"] = join_tags(product_tags)
        out.at[idx, "distribution_model_tags"] = join_tags(distribution_tags)
        out.at[idx, "data_input_tags"] = join_tags(data_tags)
        out.at[idx, "taxonomy_assignment_method"] = method
        out.at[idx, "taxonomy_assignment_basis"] = basis

        if primary_code == "OTHER_REVIEW":
            unresolved_rows.append(idx)

    if hard_stop and unresolved_rows:
        unresolved = out.loc[
            unresolved_rows,
            [
                "company",
                "primary_market_segment_code",
                "primary_market_segment",
                "taxonomy_assignment_method",
                "taxonomy_assignment_basis",
                "business_model_classification",
                "final_takeaway",
            ],
        ].copy()

        print("TAXONOMY CLASSIFICATION HARD STOP")
        print("The companies below could not be assigned to a controlled primary_market_segment.")
        print("Add them to taxonomy/company_taxonomy_overrides.csv or update the taxonomy rules.")
        print(unresolved.to_string(index=False))

        raise RuntimeError(
            f"Taxonomy classification failed for {len(unresolved)} companies."
        )

    return out




# =============================================================================
# LLM-FIRST TAXONOMY CLASSIFIER OVERRIDE
# Added to ensure Step 14 validates LLM taxonomy assignments before falling back
# to company overrides or keyword rules.
# =============================================================================

def classify_dataframe(df: pd.DataFrame, taxonomy_dir: str | Path | None = None, hard_stop: bool = True) -> pd.DataFrame:
    tables = load_taxonomy_tables(taxonomy_dir)
    code_to_label, label_to_code = code_label_maps(tables)

    market_segments = tables["market_segments"]
    subsegments = tables["subsegment_tags"]
    product_models = tables["product_models"]
    distribution_models = tables["distribution_models"]
    data_layers = tables["data_input_layers"]
    overrides = tables["company_overrides"]

    allowed_primary = allowed_codes(market_segments, "segment_code")
    allowed_subsegments = allowed_codes(subsegments, "tag_code")
    allowed_product = allowed_codes(product_models, "product_model_code")
    allowed_distribution = allowed_codes(distribution_models, "distribution_model_code")
    allowed_data = allowed_codes(data_layers, "data_input_code")

    override_by_company = {}
    if not overrides.empty and "company" in overrides.columns:
        for _, row in overrides.iterrows():
            key = normalize_key(row.get("company"))
            if key:
                override_by_company[key] = row.to_dict()

    out = df.copy()

    required_output_cols = [
        "primary_market_segment_code",
        "primary_market_segment",
        "market_segment",
        "subsegment_tags",
        "product_model_tags",
        "distribution_model_tags",
        "data_input_tags",
        "taxonomy_assignment_method",
        "taxonomy_assignment_basis",
        "taxonomy_confidence",
        "taxonomy_rationale",
        "taxonomy_needs_review",
        "taxonomy_review_reason",
    ]

    for col in required_output_cols:
        if col not in out.columns:
            out[col] = ""
        # Keep taxonomy columns object-typed so later string assignments do not trigger pandas dtype warnings.
        out[col] = out[col].astype("object")

    unresolved_rows = []

    for idx, row in out.iterrows():
        company = safe_text(row.get("company"))
        company_key = normalize_key(company)
        haystack = make_haystack(row)

        primary_code = ""
        subsegment_tags = []
        product_tags = []
        distribution_tags = []
        data_tags = []
        method = ""
        basis = ""
        confidence = safe_text(row.get("taxonomy_confidence", ""))
        rationale = safe_text(row.get("taxonomy_rationale", ""))
        needs_review = safe_text(row.get("taxonomy_needs_review", ""))
        review_reason = safe_text(row.get("taxonomy_review_reason", ""))

        # 1. LLM-provided taxonomy fields are now source of truth when valid.
        llm_primary = (
            row.get("primary_market_segment_code", "")
            or row.get("primary_market_segment", "")
            or row.get("market_segment", "")
        )

        primary_code = normalize_code(llm_primary, allowed_primary, label_to_code)

        if primary_code:
            method = safe_text(row.get("taxonomy_assignment_method", "")) or "llm_validated"
            basis = rationale or safe_text(row.get("taxonomy_assignment_basis", "")) or "LLM taxonomy field matched approved taxonomy"

            subsegment_tags = validate_tag_list(row.get("subsegment_tags", ""), allowed_subsegments)
            product_tags = validate_tag_list(row.get("product_model_tags", ""), allowed_product)
            distribution_tags = validate_tag_list(row.get("distribution_model_tags", ""), allowed_distribution)
            data_tags = validate_tag_list(row.get("data_input_tags", ""), allowed_data)

        # 2. Company overrides only fill gaps or true exceptions.
        if not primary_code and company_key in override_by_company:
            override = override_by_company[company_key]

            primary_code = normalize_code(
                override.get("primary_market_segment", ""),
                allowed_primary,
                label_to_code,
            )

            subsegment_tags = validate_tag_list(override.get("subsegment_tags", ""), allowed_subsegments)
            product_tags = validate_tag_list(override.get("product_model_tags", ""), allowed_product)
            distribution_tags = validate_tag_list(override.get("distribution_model_tags", ""), allowed_distribution)
            data_tags = validate_tag_list(override.get("data_input_tags", ""), allowed_data)

            method = "company_override"
            basis = safe_text(override.get("override_reason")) or "Company override table"

        # 3. Keyword fallback is last resort only.
        if not primary_code:
            primary_code, matched_pattern = first_rule_match(haystack, PRIMARY_KEYWORD_RULES)

            if primary_code:
                method = "keyword_fallback_last_resort"
                basis = f"Matched pattern: {matched_pattern}"

        if not primary_code:
            primary_code = "OTHER_REVIEW"
            method = "unmapped_review"
            basis = "No validated LLM field, company override, or deterministic fallback match"

        # Infer missing nuance tags only when LLM/override omitted them.
        if not subsegment_tags:
            subsegment_tags = [
                tag for tag in match_rules(haystack, SUBSEGMENT_RULES)
                if tag in allowed_subsegments
            ]

        if not product_tags:
            product_tags = [
                tag for tag in match_rules(haystack, PRODUCT_RULES)
                if tag in allowed_product
            ]

        if not distribution_tags:
            distribution_tags = [
                tag for tag in match_rules(haystack, DISTRIBUTION_RULES)
                if tag in allowed_distribution
            ]

        if not data_tags:
            data_tags = [
                tag for tag in match_rules(haystack, DATA_INPUT_RULES)
                if tag in allowed_data
            ]

        primary_label = code_to_label.get(primary_code, primary_code)

        out.at[idx, "primary_market_segment_code"] = primary_code
        out.at[idx, "primary_market_segment"] = primary_label
        out.at[idx, "market_segment"] = primary_label
        out.at[idx, "subsegment_tags"] = join_tags(subsegment_tags)
        out.at[idx, "product_model_tags"] = join_tags(product_tags)
        out.at[idx, "distribution_model_tags"] = join_tags(distribution_tags)
        out.at[idx, "data_input_tags"] = join_tags(data_tags)
        out.at[idx, "taxonomy_assignment_method"] = method
        out.at[idx, "taxonomy_assignment_basis"] = basis

        if confidence:
            out.at[idx, "taxonomy_confidence"] = confidence

        if rationale:
            out.at[idx, "taxonomy_rationale"] = rationale

        if needs_review:
            out.at[idx, "taxonomy_needs_review"] = needs_review

        if review_reason:
            out.at[idx, "taxonomy_review_reason"] = review_reason

        if primary_code == "OTHER_REVIEW":
            unresolved_rows.append(idx)

    if hard_stop and unresolved_rows:
        display_cols = [
            "company",
            "primary_market_segment_code",
            "primary_market_segment",
            "taxonomy_assignment_method",
            "taxonomy_assignment_basis",
            "business_model_classification",
            "final_takeaway",
        ]

        display_cols = [col for col in display_cols if col in out.columns]

        unresolved = out.loc[unresolved_rows, display_cols].copy()

        print("TAXONOMY CLASSIFICATION HARD STOP")
        print("The companies below could not be assigned to a controlled primary_market_segment.")
        print("This should be rare. Run Step 27 backfill or update taxonomy governance.")
        print(unresolved.to_string(index=False))

        raise RuntimeError(
            f"Taxonomy classification failed for {len(unresolved)} companies."
        )

    return out
