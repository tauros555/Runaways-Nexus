from __future__ import annotations

from pathlib import Path
import pandas as pd

from rd_modules.feature_engine import build_features
from rd_modules.simulator_engine import predict, assign_grade
from rd_modules.scenario_engine import predict_scenario, scenario_adjustment
from rd_modules.monte_carlo import simulate_race
from rd_modules.route_bias import assign_route_positions

BASE = Path(__file__).resolve().parents[1]
RD_DATA = BASE / "data" / "rd"
HISTORY_FILE = RD_DATA / "history_seed_2020_2026.csv.gz"
COURSE_FILE = RD_DATA / "course_structure.csv"
THRESHOLD_FILE = RD_DATA / "scenario_thresholds.csv"


def _read_csv_any(path: Path) -> pd.DataFrame:
    last = None
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except Exception as e:
            last = e
    raise RuntimeError(f"CSV読込失敗: {path.name}: {last}")


def load_rd_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    last = None
    hist = None
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            hist = pd.read_csv(HISTORY_FILE, compression="gzip", encoding=enc, low_memory=False)
            break
        except Exception as e:
            last = e
    if hist is None:
        raise RuntimeError(f"Race Development履歴読込失敗: {last}")
    course = _read_csv_any(COURSE_FILE)
    thresholds = _read_csv_any(THRESHOLD_FILE)
    return hist, course, thresholds


def course_row(course: pd.DataFrame, place: str, surface: str, distance: float) -> dict:
    surf = "芝" if str(surface).strip() == "芝" else "ダート"
    z = course[
        (course["場所"].astype(str) == str(place))
        & (course["芝・ダート"].astype(str) == surf)
        & (pd.to_numeric(course["距離"], errors="coerce") == float(distance))
    ]
    return z.iloc[0].to_dict() if len(z) else {}


def run_race_development(
    current: pd.DataFrame,
    history: pd.DataFrame,
    course: pd.DataFrame,
    thresholds: pd.DataFrame,
    n_sims: int = 10000,
    route_bias: str = "フラット",
) -> tuple[pd.DataFrame, dict, dict]:
    x = current.copy()
    surface = str(x["芝・ダ"].iloc[0])
    place = str(x["場所"].iloc[0])
    distance = float(pd.to_numeric(x["距離"], errors="coerce").iloc[0])
    date = int(pd.to_numeric(x["年月日"], errors="coerce").iloc[0])
    year = int(str(date)[:4])
    cr = course_row(course, place, surface, distance)
    feat = build_features(x, history, cr)
    pred, raceinfo = predict(feat)
    pred = assign_grade(pred, thresholds, year, surface)
    scen, pred = predict_scenario(pred, raceinfo)

    active = scen["PredictedScenario"]
    pred = scenario_adjustment(pred, active)
    if "Move_First_to_4" not in pred.columns:
        pred["Move_First_to_4"] = 0.0
    # Route prediction only. Use flat bias here so Nexus can apply independent day-bias adjustment later.
    pred = assign_route_positions(pred, cr, "フラット")
    mc, meta = simulate_race(pred, scen, n_sims=n_sims, mode="AUTO", seed=5601)
    cols = [c for c in [
        "馬番", "馬名", "FullWinProb", "ScenarioFullWinProb", "展開評価", "今回想定脚質",
        "初角進路", "最終角進路", "進路バイアス評価",
        "LeadProb_Jockey", "FirstPred_Jockey", "FourPred_Jockey",
        "HorseFinishPast5", "距離変化区分", "距離変化_補正ソース",
        "距離変化_Lead補正", "距離変化_初角補正", "距離変化_勝率補正"
    ] if c in pred.columns]
    out = pred[cols].copy().merge(mc[["馬番", "MC勝率", "MC連対率", "MC複勝率"]], on="馬番", how="left")
    out["race_development_prob"] = pd.to_numeric(out["MC勝率"], errors="coerce").fillna(pd.to_numeric(out.get("ScenarioFullWinProb"), errors="coerce")).fillna(0)
    combined_meta = {**scen, **meta}
    return out, raceinfo, combined_meta
