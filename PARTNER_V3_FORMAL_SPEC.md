# Partner Ver.3 Formal Spec

## Philosophy
調教で◎本命を見つけ、地雷を除外し、市場人気とは独立した能力・展開・血統・馬場の理由から「◎が来るなら一緒に来やすい相手」を選ぶ。

## Ranking weights
- Ability: 60%
- Development compatibility: 25%
- Pedigree-condition compatibility: 10%
- Surface/day-bias compatibility: 5%
- Training additive weight: 0% (used upstream for anchor selection)

## Candidate handling
- Effective Jirai is excluded.
- Anchor is excluded.
- Market main line = top two in popularity among remaining candidates, when odds/popularity are available.
- NEXUS linked longshot = highest Partner Score outside market main line.

## Interpretation
Partner Score is a relative ranking score, not a calibrated conditional place probability.

## Data decisions
- SmartRC: removed completely.
- Distance-change correction: provisional reconstructed master is not shipped. Missing master -> zero correction fallback. The distance-change bucket remains available for bounded Partner explanation/penalty only.
