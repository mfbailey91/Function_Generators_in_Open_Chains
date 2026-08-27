"""V4.2D analysis package (center-IK reference, metrics, pairing)."""

from inequality_mechanisms.analysis.v4.optimality_metrics import (
    STAGE_C_ROW_COUNT,
    extract_stage_c_views,
    join_stage_c_to_reference,
    load_stage_c_records,
)
from inequality_mechanisms.analysis.v4.optimality_pairing import (
    PAIRING_LABEL,
    decompose_final_gaps,
    pair_mechanism_contrasts,
)
from inequality_mechanisms.analysis.v4.optimality_reference import (
    CANDIDATE_GENERATOR_ID,
    FROZEN_STAGE_C_ROWS,
    FROZEN_V4_2C_FILES_DIGEST,
    PRIMARY_REFERENCE_COUNT,
    SCHEMA_VERSION,
    OptimalityReferenceError,
    build_center_ik_references,
    candidate_key,
    join_representation_penalty,
    load_report_config,
    load_v4_2b_historical_references,
    reconstruct_v4_2c_problem,
    verify_source_package_digests,
)

__all__ = [
    "CANDIDATE_GENERATOR_ID",
    "FROZEN_STAGE_C_ROWS",
    "FROZEN_V4_2C_FILES_DIGEST",
    "PAIRING_LABEL",
    "PRIMARY_REFERENCE_COUNT",
    "SCHEMA_VERSION",
    "STAGE_C_ROW_COUNT",
    "OptimalityReferenceError",
    "build_center_ik_references",
    "candidate_key",
    "decompose_final_gaps",
    "extract_stage_c_views",
    "join_representation_penalty",
    "join_stage_c_to_reference",
    "load_report_config",
    "load_stage_c_records",
    "load_v4_2b_historical_references",
    "pair_mechanism_contrasts",
    "reconstruct_v4_2c_problem",
    "verify_source_package_digests",
]
