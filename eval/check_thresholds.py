from __future__ import annotations

import argparse
import json
from pathlib import Path


def _check_metric(cfg_name: str, cfg: dict, metric: str, min_value: float | None, max_value: float | None) -> list[str]:
    errs: list[str] = []
    if min_value is None and max_value is None:
        return errs
    value = cfg.get(metric)
    if value is None:
        errs.append(f"{cfg_name}: metric '{metric}' is missing (null)")
        return errs
    try:
        v = float(value)
    except Exception:
        errs.append(f"{cfg_name}: metric '{metric}' is non-numeric: {value!r}")
        return errs

    if min_value is not None and v < min_value:
        errs.append(f"{cfg_name}: {metric}={v:.4f} is below min {min_value:.4f}")
    if max_value is not None and v > max_value:
        errs.append(f"{cfg_name}: {metric}={v:.4f} is above max {max_value:.4f}")
    return errs


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail CI if eval summary metrics violate thresholds.")
    parser.add_argument("--summary", required=True, help="Path to eval summary.json")
    parser.add_argument("--min-hit", type=float, default=None, help="Minimum hit_at_k_avg")
    parser.add_argument("--min-keyword", type=float, default=None, help="Minimum keyword_coverage_avg")
    parser.add_argument("--min-faithfulness", type=float, default=None, help="Minimum judge_faithfulness_avg")
    parser.add_argument("--max-retrieve-ms", type=float, default=None, help="Maximum retrieve_ms_avg")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.exists():
        raise SystemExit(f"summary not found: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict) or not summary:
        raise SystemExit("summary json is empty or invalid")

    errors: list[str] = []
    for cfg_name, cfg in summary.items():
        if not isinstance(cfg, dict):
            errors.append(f"{cfg_name}: invalid summary block")
            continue
        errors.extend(_check_metric(cfg_name, cfg, "hit_at_k_avg", args.min_hit, None))
        errors.extend(_check_metric(cfg_name, cfg, "keyword_coverage_avg", args.min_keyword, None))
        errors.extend(_check_metric(cfg_name, cfg, "judge_faithfulness_avg", args.min_faithfulness, None))
        errors.extend(_check_metric(cfg_name, cfg, "retrieve_ms_avg", None, args.max_retrieve_ms))

    if errors:
        print("Threshold check failed:")
        for e in errors:
            print(f"- {e}")
        raise SystemExit(1)

    print("Threshold check passed.")


if __name__ == "__main__":
    main()
