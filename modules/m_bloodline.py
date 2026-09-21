from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
from modules.m_autogen import combined_runner_master

BASE = Path(__file__).resolve().parents[1]
M_DIR = BASE / "data" / "nexus_m"

FILES = {
    "runner": M_DIR / "m_runner_9branch.csv",
    "course": M_DIR / "m_course_rules.csv",
    "track_going": M_DIR / "m_track_going_rules.csv",
    "physical": M_DIR / "m_physical_rules.csv",
    "physical_bins": M_DIR / "m_physical_bins.csv",
    "going_physical": M_DIR / "m_going_physical_rules.csv",
    "distance": M_DIR / "m_distance_transition.csv",
    "lead": M_DIR / "m_lead_competition.csv",
    "mobility": M_DIR / "m_mobility.csv",
    "closing": M_DIR / "m_closing_longspurt.csv",
}

BLOCK_MAP={"父ブロック":"M父","母父ブロック":"M母父","母母父ブロック":"M母母父"}
JUDGE_SCORE={"強":2,"やや強":1,"中立":0,"やや弱":-1,"弱":-2}

def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    for enc in ("utf-8-sig","cp932","utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except Exception:
            pass
    return pd.DataFrame()

def _hid(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"\.0$","",regex=True).str.strip()

def _uniq(items):
    return list(dict.fromkeys([str(x) for x in items if str(x).strip() not in {"","－","nan","None"}]))

def load_m_bundle() -> dict[str,pd.DataFrame]:
    out={k:_read(v) for k,v in FILES.items()}
    out["runner"]=combined_runner_master()
    return out

def attach_m_signature(current: pd.DataFrame, bundle: dict[str,pd.DataFrame]) -> pd.DataFrame:
    x=current.copy()
    if "血統登録番号" not in x.columns:
        x["血統登録番号"]=""
    x["_hid"]=_hid(x["血統登録番号"])

    m=bundle.get("runner",pd.DataFrame()).copy()
    if m.empty:
        for c in ["M9","M父","M母父","M母母父"]:
            x[c]=""
        return x

    m["_hid"]=_hid(m["血統登録番号"])
    required=[
        "枝1_父ブロック_父父","枝2_父ブロック_母父","枝3_父ブロック_母母父",
        "枝4_母父ブロック_父父","枝5_母父ブロック_母父","枝6_母父ブロック_母母父",
        "枝7_母母父ブロック_父父","枝8_母母父ブロック_母父","枝9_母母父ブロック_母母父",
    ]
    for c in required:
        if c not in m.columns: m[c]=""
    m["M父"]=m[required[0:3]].astype(str).agg("".join,axis=1)
    m["M母父"]=m[required[3:6]].astype(str).agg("".join,axis=1)
    m["M母母父"]=m[required[6:9]].astype(str).agg("".join,axis=1)
    m["M9"]=m.get("現代馬9枝シグネチャ","")
    keep=m[["_hid","M9","M父","M母父","M母母父"]].drop_duplicates("_hid")
    return x.merge(keep,on="_hid",how="left")

def _match_patterns(row:pd.Series, rules:pd.DataFrame, conditions:list[str]) -> list[dict]:
    if rules.empty or not conditions:
        return []
    rr=rules[rules["条件"].astype(str).isin([str(c) for c in conditions])].copy()
    hits=[]
    for _,q in rr.iterrows():
        block=str(q.get("ブロック",""))
        col=BLOCK_MAP.get(block)
        if not col or str(row.get(col,"")) != str(q.get("3枝パターン","")):
            continue
        n=float(pd.to_numeric(q.get("出走数"),errors="coerce")) if pd.notna(pd.to_numeric(q.get("出走数"),errors="coerce")) else 0
        wj=str(q.get("勝期待判定","中立"))
        pj=str(q.get("複勝期待判定","中立"))
        signal=0 if n<300 else int(np.clip(JUDGE_SCORE.get(wj,0)+JUDGE_SCORE.get(pj,0),-2,2))
        hits.append({
            "condition":str(q.get("条件","")),
            "block":block,
            "pattern":str(q.get("3枝パターン","")),
            "n":int(n),
            "win_ae":pd.to_numeric(q.get("勝A_E"),errors="coerce"),
            "win_z":pd.to_numeric(q.get("勝z"),errors="coerce"),
            "place_ae":pd.to_numeric(q.get("複勝A_E"),errors="coerce"),
            "place_z":pd.to_numeric(q.get("複勝z"),errors="coerce"),
            "roi":pd.to_numeric(q.get("単勝回収率"),errors="coerce"),
            "win_judge":wj,
            "place_judge":pj,
            "signal":signal,
        })
    return hits

def _course_hits(row:pd.Series, rules:pd.DataFrame, place:str, distance:int, surface:str) -> list[dict]:
    if rules.empty: return []
    cond=f"{place}×{int(distance)}×{surface}"
    rr=rules[rules["条件"].astype(str).eq(cond)].copy()
    hits=[]
    for _,q in rr.iterrows():
        block=str(q.get("ブロック",""))
        col=BLOCK_MAP.get(block)
        if not col or str(row.get(col,"")) != str(q.get("3枝パターン","")):
            continue
        hits.append({
            "condition":cond,
            "direction":str(q.get("方向","")),
            "confidence":str(q.get("信頼度","")),
            "block":block,
            "pattern":str(q.get("3枝パターン","")),
            "n":int(pd.to_numeric(q.get("出走数"),errors="coerce") or 0),
            "roi":pd.to_numeric(q.get("単勝回収率"),errors="coerce"),
            "win_ae":pd.to_numeric(q.get("勝A_E"),errors="coerce"),
            "win_z":pd.to_numeric(q.get("勝z"),errors="coerce"),
            "place_ae":pd.to_numeric(q.get("複勝A_E"),errors="coerce"),
            "place_z":pd.to_numeric(q.get("複勝z"),errors="coerce"),
        })
    return hits

def _physical_band(surface:str, cushion:float|None, moisture:float|None) -> str|None:
    v=cushion if surface=="芝" else moisture
    if v is None or pd.isna(v): return None
    v=float(v)
    if surface=="芝":
        if v<=8.70:return "低"
        if v<=9.20:return "やや低"
        if v<=9.50:return "標準"
        if v<=9.90:return "やや高"
        return "高"
    if v<=2.70:return "低"
    if v<=4.30:return "やや低"
    if v<=6.60:return "標準"
    if v<=9.90:return "やや高"
    return "高"

def _hit_text(h:dict, prefix:str) -> str:
    sig=h.get("signal",0)
    mark="＋＋" if sig>=2 else ("＋" if sig==1 else ("－－" if sig<=-2 else ("－" if sig==-1 else "中立")))
    return f"{prefix}:{h.get('block','')} {h.get('pattern','')} {mark} (n={h.get('n',0)})"

def _course_state(hits:list[dict]):
    strict=[h for h in hits if h["direction"]=="プラス" and h["confidence"] in {"A","B"} and pd.notna(h["roi"]) and float(h["roi"])>=110]
    pos_ab=[h for h in hits if h["direction"]=="プラス" and h["confidence"] in {"A","B"}]
    pos_c=[h for h in hits if h["direction"]=="プラス" and h["confidence"]=="C"]
    neg_ab=[h for h in hits if h["direction"]=="マイナス" and h["confidence"] in {"A","B"}]
    neg_c=[h for h in hits if h["direction"]=="マイナス" and h["confidence"]=="C"]
    if strict:return "strict",strict
    if pos_ab and not neg_ab:return "positive",pos_ab
    if neg_ab and not pos_ab:return "negative",neg_ab
    if pos_c and not (neg_ab or neg_c):return "mild_positive",pos_c
    if neg_c and not (pos_ab or pos_c):return "mild_negative",neg_c
    if hits:return "mixed",hits
    return "none",[]

def _current_grade(base_state:str, current_hits:list[dict], has_m:bool):
    if not has_m:return "－"
    signals=[int(h.get("signal",0)) for h in current_hits]
    strong_pos=any(s>=2 for s in signals)
    strong_neg=any(s<=-2 for s in signals)
    mild_pos=sum(s>=1 for s in signals)
    mild_neg=sum(s<=-1 for s in signals)

    if base_state=="strict":
        return "○" if strong_neg and not strong_pos else "◎"
    if base_state=="positive":
        return "△" if strong_neg and not strong_pos else "○"
    if base_state=="mild_positive":
        return "○" if strong_pos else ("△" if not strong_neg else "×")
    if base_state=="negative":
        return "△" if strong_pos and not strong_neg else "×"
    if base_state=="mild_negative":
        return "○" if strong_pos and not strong_neg else ("×" if strong_neg else "△")
    if strong_pos and not strong_neg:return "○"
    if strong_neg and not strong_pos:return "×"
    if mild_pos>=2 and mild_neg==0:return "○"
    if current_hits:return "△"
    return "－"

def evaluate_m(current:pd.DataFrame, place:str, distance:int, surface:str,
               going:str|None=None, cushion:float|None=None, moisture:float|None=None,
               bundle:dict[str,pd.DataFrame]|None=None) -> pd.DataFrame:
    bundle=bundle or load_m_bundle()
    x=attach_m_signature(current,bundle)
    band=_physical_band(surface,cushion,moisture)
    rows=[]

    for _,r in x.iterrows():
        has_m=any(str(r.get(c,"")).strip() not in {"","nan","None"} for c in ["M父","M母父","M母母父"])
        course_hits=_course_hits(r,bundle.get("course",pd.DataFrame()),place,distance,surface)
        base_state,base_selected=_course_state(course_hits)

        going_hits=[]
        if going:
            conds=[f"{place}×{surface}×{going}",f"{int(distance)}×{surface}×{going}"]
            going_hits=_match_patterns(r,bundle.get("track_going",pd.DataFrame()),conds)

        physical_hits=[]
        composite_hits=[]
        if band:
            if surface=="芝":
                pconds=[band,f"{place}×{band}",f"{int(distance)}×{band}"]
                cconds=[f"{going}×{band}",f"{place}×{going}×{band}",f"{int(distance)}×{going}×{band}"] if going else []
            else:
                pconds=[band,f"{place}×{band}",f"{int(distance)}×{band}"]
                cconds=[f"{going}×{band}",f"{place}×{going}×{band}",f"{int(distance)}×{going}×{band}"] if going else []
            physical_hits=_match_patterns(r,bundle.get("physical",pd.DataFrame()),pconds)
            composite_hits=_match_patterns(r,bundle.get("going_physical",pd.DataFrame()),cconds)

        current_hits=going_hits+physical_hits+composite_hits
        grade=_current_grade(base_state,current_hits,has_m)

        strict=[h for h in course_hits if h["direction"]=="プラス" and h["confidence"] in {"A","B"} and pd.notna(h["roi"]) and float(h["roi"])>=110]
        strict_reason=_uniq([f"M×{place}{surface}{int(distance)}◎" for _ in strict])

        if base_state=="strict": course_display=f"M×{place}{surface}{int(distance)}◎"
        elif base_state in {"positive","mild_positive"}: course_display=f"M×{place}{surface}{int(distance)}○"
        elif base_state in {"negative","mild_negative"}: course_display=f"M×{place}{surface}{int(distance)}×"
        elif base_state=="mixed": course_display=f"M×{place}{surface}{int(distance)}△"
        else: course_display="－"

        plus=[]; minus=[]
        detail=[]
        for h in going_hits:
            t=_hit_text(h,"馬場")
            detail.append(t)
            (plus if h["signal"]>0 else minus if h["signal"]<0 else detail).append(t) if h["signal"]!=0 else None
        for h in physical_hits:
            t=_hit_text(h,("クッション" if surface=="芝" else "含水率"))
            detail.append(t)
            if h["signal"]>0: plus.append(t)
            elif h["signal"]<0: minus.append(t)
        for h in composite_hits:
            t=_hit_text(h,"馬場×物理")
            detail.append(t)
            if h["signal"]>0: plus.append(t)
            elif h["signal"]<0: minus.append(t)

        course_detail=_uniq([
            f"{h['block']} {h['pattern']} {h['direction']} {h['confidence']} ROI {float(h['roi']):.1f}%"
            if pd.notna(h["roi"]) else f"{h['block']} {h['pattern']} {h['direction']} {h['confidence']}"
            for h in course_hits
        ])
        reasons=_uniq(course_detail+detail)

        rows.append({
            "馬番":r.get("馬番"),
            "M評価":grade,
            "M9":r.get("M9",""),
            "M父":r.get("M父",""),
            "M母父":r.get("M母父",""),
            "M母母父":r.get("M母母父",""),
            "M×コース":course_display,
            "M×距離":"－",
            "M×坂":"－",
            "M×芝ダ":"－",
            "M×馬場状態":" / ".join(_uniq([_hit_text(h,"馬場") for h in going_hits])) if going_hits else "－",
            "M×クッション値":(" / ".join(_uniq([_hit_text(h,"クッション") for h in physical_hits])) if surface=="芝" and physical_hits else "－"),
            "M×含水率":(" / ".join(_uniq([_hit_text(h,"含水率") for h in physical_hits])) if surface!="芝" and physical_hits else "－"),
            "M×馬場物理複合":" / ".join(_uniq([_hit_text(h,"馬場×物理") for h in composite_hits])) if composite_hits else "－",
            "M物理帯":band or "未指定",
            "Mプラス根拠":" / ".join(_uniq(plus)) if plus else "－",
            "Mマイナス根拠":" / ".join(_uniq(minus)) if minus else "－",
            "M評価根拠":" / ".join(reasons) if reasons else "今回参照可能な検証条件なし",
            "M_STRICT_110":bool(strict),
            "M_STRICT_REASON":" / ".join(strict_reason),
        })
    return pd.DataFrame(rows)

def add_distance_m(result:pd.DataFrame, bundle:dict[str,pd.DataFrame]) -> pd.DataFrame:
    x=result.copy()
    rules=bundle.get("distance",pd.DataFrame())
    if rules.empty or "距離変化区分" not in x.columns:
        x["M×距離"]="－"
        return x
    out=[]
    for _,r in x.iterrows():
        labels=[]
        for _,q in rules.iterrows():
            col=BLOCK_MAP.get(str(q.get("ブロック","")))
            if col and str(r.get(col,""))==str(q.get("3枝パターン","")) and str(r.get("距離変化区分",""))==str(q.get("距離変化区分","")):
                sign="+" if float(q.get("Simulator補正",0))>0 else "−"
                labels.append(f'{q.get("距離変化区分")} {q.get("信頼度")}{sign}')
        out.append(" / ".join(_uniq(labels)) if labels else "－")
    x["M×距離"]=out
    return x
