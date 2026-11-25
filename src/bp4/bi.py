"""Pure filter-dependent BP4 statistics and independent artifact tasks.

Run ``python -m src.bp4.bi all`` after processed data exist. No Spark/ETL runs in UI.
"""
import argparse
import itertools
import json
import warnings
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.spatial.distance import pdist, squareform

from src.bp4.features import ROOT, OUT, OUTCOMES, CLIMATE, UNITS, prepare, derive, select

INSUFFICIENT = "Insufficient Evidence"
DEFAULT = {"minimum_n": 8, "alpha": .05, "seed": 42, "permutations": 199,
           "gap_threshold_ton_ha": .15, "peer_n": 2, "z_threshold": 1.5, "iqr_factor": 1.5,
           "decline_threshold_pct": 5., "priority_high": .67, "priority_moderate": .34,
           "stable_cv_pct": 10., "weak_correlation": .3, "cluster_bootstraps": 30, "minimum_score_regions": 7,
           "risk_weights": {"volatility": 1/3, "frequency": 1/3, "magnitude": 1/3, "climate_evidence": 0., "production_relevance": 1., "data_confidence": 0.}}


def holm(values):
    """Holm-adjust finite p-values while retaining missing results."""
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    order = np.where(np.isfinite(values))[0]
    order = order[np.argsort(values[order])]
    if len(order):
        out[order] = np.minimum(1, np.maximum.accumulate(values[order] * np.arange(len(order), 0, -1)))
    return out


def config():
    path = ROOT / "configs/bp4_bi.json"
    return DEFAULT | (json.loads(path.read_text(encoding="utf-8")) if path.exists() else {})


def adjust(frame, p="p", output="q"):
    if not frame.empty and p in frame:
        frame[output] = holm(frame[p])
    return frame


def cv(s):
    s = s.dropna()
    return s.std(ddof=1) / s.mean() * 100 if len(s) >= 2 and s.mean() > 0 else np.nan


def correlation(frame, x, y, method="Pearson", minimum=8):
    g = frame[[x, y]].replace([np.inf, -np.inf], np.nan).dropna()
    result = dict(n=len(g), coefficient=np.nan, p=np.nan, ci_low=np.nan, ci_high=np.nan,
                  method=method, status=INSUFFICIENT)
    if len(g) < minimum or g[x].nunique() < 2 or g[y].nunique() < 2:
        return result
    fn = stats.pearsonr if method == "Pearson" else stats.spearmanr
    r, p = fn(g[x], g[y])
    # Fisher-z intervals are nominal, with an approximate rank analogue for Spearman.
    z = np.arctanh(np.clip(r, -.99999999, .99999999))
    se = (1.06 if method == "Spearman" else 1.) / np.sqrt(len(g) - 3)
    lo, hi = np.tanh([z - 1.96 * se, z + 1.96 * se])
    return result | dict(coefficient=float(r), p=float(p), ci_low=float(lo), ci_high=float(hi), status="Exploratory; nominal CI assumes independent observations")


def group_tests(frame, value, c):
    groups = [g[value].dropna().to_numpy() for _, g in frame.groupby("region")]
    groups = [g for g in groups if len(g) >= 3]
    normal = len(groups) >= 2 and all(len(g) >= 3 and np.ptp(g) > 0 and stats.shapiro(g).pvalue > c["alpha"] for g in groups)
    equal = len(groups) >= 2 and all(np.ptp(g) > 0 for g in groups) and stats.levene(*groups).pvalue > c["alpha"]
    rows = []
    for name, fn in [("One-way ANOVA", stats.f_oneway), ("Kruskal-Wallis", stats.kruskal)]:
        row = dict(method=name, n=sum(map(len, groups)), groups=len(groups), statistic=np.nan, p=np.nan,
                   normality_supported=normal, equal_variance_supported=equal, status=INSUFFICIENT,
                   unit="region-year", assumptions="Repeated years / serial dependence limit independent-group inference")
        if len(groups) >= 2 and np.ptp(np.concatenate(groups)) > 0:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                test = fn(*groups)
            row.update(statistic=float(test.statistic), p=float(test.pvalue), status="Exploratory")
            all_values=np.concatenate(groups)
            if name == "One-way ANOVA":
                row["effect_size"] = sum(len(g)*(g.mean()-all_values.mean())**2 for g in groups)/sum((all_values-all_values.mean())**2)
                row["effect_definition"] = "eta squared"
            else:
                row["effect_size"] = max(0.,(test.statistic-len(groups)+1)/(len(all_values)-len(groups)))
                row["effect_definition"] = "rank epsilon squared approximation"
        rows.append(row)
    pivot = frame.pivot(index="year", columns="region", values=value).dropna()
    row = dict(method="Friedman year-block sensitivity", n=len(pivot), groups=len(pivot.columns), statistic=np.nan, p=np.nan,
               status=INSUFFICIENT, unit="complete calendar-year blocks", assumptions="Controls common year ranks; residual serial dependence remains")
    if len(pivot) >= c["minimum_n"] and len(pivot.columns) >= 3 and pivot.nunique(axis=1).gt(1).any():
        test = stats.friedmanchisquare(*(pivot[col] for col in pivot))
        row.update(statistic=float(test.statistic), p=float(test.pvalue), status="Exploratory")
        row["effect_size"] = test.statistic/(len(pivot)*(len(pivot.columns)-1))
        row["effect_definition"] = "Kendall W"
    rows.append(row)
    return adjust(pd.DataFrame(rows))


def performance_gap(frame, c):
    """Leave-region-out, same-year nearest-climate-peer reference. No fitted prediction."""
    rows = []
    scale = frame[list(CLIMATE.values())].std(ddof=0).replace(0, np.nan)
    for _, row in frame.iterrows():
        peers = frame[(frame.year == row.year) & frame.region.ne(row.region)].dropna(subset=["yield_value", *CLIMATE.values()])
        distance = ((peers[list(CLIMATE.values())] - row[list(CLIMATE.values())].astype(float)) / scale).pow(2).sum(axis=1, min_count=2)
        nearest = peers.loc[distance.dropna().nsmallest(c["peer_n"]).index]
        reference = nearest.yield_value.mean() if len(nearest) == c["peer_n"] and row[list(CLIMATE.values())].notna().all() else np.nan
        rows.append(dict(region=row.region, year=row.year, observed_yield=row.yield_value, reference_yield=reference,
                         performance_gap=row.yield_value-reference, peer_regions="; ".join(nearest.region)))
    detail = pd.DataFrame(rows)
    result = []
    for region, g in detail.groupby("region"):
        gaps = g.performance_gap.dropna()
        n, mean = len(gaps), gaps.mean()
        margin = stats.t.ppf(.975, n-1) * gaps.sem() if n >= c["minimum_n"] else np.nan
        label = INSUFFICIENT if n < c["minimum_n"] else "Neutral / Inconclusive"
        if n >= c["minimum_n"]:
            if mean-margin > c["gap_threshold_ton_ha"]: label = "Bright Spot"
            elif mean+margin < -c["gap_threshold_ton_ha"]: label = "Underperformer"
        result.append(dict(region=region, observed_yield=g.observed_yield.mean(), reference_yield=g.reference_yield.mean(),
                           performance_gap=mean, ci_low=mean-margin, ci_high=mean+margin, n=n, classification=label))
    return pd.DataFrame(result), detail


def benchmark(frame, c):
    rows = []
    for region, g in frame.groupby("region"):
        for outcome, col in OUTCOMES.items():
            s = g[col].dropna()
            rows.append(dict(region=region, outcome=outcome, mean=s.mean(), median=s.median(), std=s.std(), cv_pct=cv(s), minimum=s.min(), maximum=s.max(), n=len(s), units=UNITS[col]))
    gaps, detail = performance_gap(frame, c)
    tests = pd.concat([group_tests(frame, col, c).assign(outcome=name) for name, col in OUTCOMES.items()], ignore_index=True)
    return dict(statistics=pd.DataFrame(rows), tests=tests, gaps=gaps, peer_reference=detail)


def pettitt(year, values, minimum=8):
    g = pd.DataFrame(dict(year=year, value=values)).dropna().sort_values("year")
    row = dict(change_year=np.nan, change_statistic=np.nan, change_p=np.nan, change_status=INSUFFICIENT)
    if len(g) < minimum or g.value.nunique() < 2:
        return row
    ranks = stats.rankdata(g.value)
    u = 2*np.cumsum(ranks) - np.arange(1, len(g)+1)*(len(g)+1)
    # At least three observations on either side of the candidate split.
    eligible = np.arange(2, len(g)-3)
    if not len(eligible): return row
    pos = eligible[np.argmax(np.abs(u[eligible]))]
    k = abs(u[pos])
    p = min(1., 2*np.exp(-6*k*k/(len(g)**3+len(g)**2)))
    return dict(change_year=int(g.year.iloc[pos+1]), change_statistic=float(k), change_p=float(p), change_status="Candidate only; approximate Pettitt p assumes exchangeability")


def trend_table(frame, c):
    rows = []
    for region, g in frame.groupby("region"):
        for col in [*OUTCOMES.values(), *CLIMATE.values()]:
            v = g[["year", col]].dropna().sort_values("year")
            row = dict(region=region, indicator=col, units=UNITS[col]+"/year", n=len(v), slope=np.nan,
                       ci_low=np.nan, ci_high=np.nan, tau=np.nan, p=np.nan, lag1_autocorrelation=np.nan,
                       block_permutation_p=np.nan, status=INSUFFICIENT)
            row.update(pettitt(v.year, v[col], c["minimum_n"]))
            if len(v) >= c["minimum_n"] and v[col].nunique() > 1:
                slope, intercept, lo, hi = stats.theilslopes(v[col], v.year)
                tau, p = stats.kendalltau(v.year, v[col])
                residual = v[col].to_numpy() - (intercept+slope*v.year.to_numpy())
                ac = np.corrcoef(residual[:-1], residual[1:])[0, 1] if np.std(residual[:-1]) > 0 and np.std(residual[1:]) > 0 else np.nan
                # Randomize contiguous 3-year blocks, preserving local dependence approximately.
                rng = np.random.default_rng(c["seed"])
                blocks = [x for x in np.array_split(v[col].to_numpy(), int(np.ceil(len(v)/3)))]
                null = [abs(stats.kendalltau(v.year, np.concatenate([blocks[i] for i in rng.permutation(len(blocks))])).statistic) for _ in range(c["permutations"])]
                row.update(slope=slope, ci_low=lo, ci_high=hi, tau=tau, p=p, lag1_autocorrelation=ac,
                           block_permutation_p=(1+sum(t >= abs(tau) for t in null))/(len(null)+1),
                           status="Exploratory; block permutation is a short-series sensitivity check")
            rows.append(row)
    result = adjust(pd.DataFrame(rows))
    adjust(result, "change_p", "change_q")
    adjust(result, "block_permutation_p", "block_q")
    result["change_supported"] = result.change_q.lt(c["alpha"])
    return result


def align_lag(frame, climate, outcome, lag, unit="region"):
    if lag not in (0, 1, 2): raise ValueError("Supported lags: 0, 1, 2")
    keys = [unit, "year"]
    weather = frame[keys+[climate]].copy().rename(columns={climate: "climate_value"})
    weather["climate_year"] = weather.year
    weather["year"] += lag
    keep = list(dict.fromkeys(keys+["region", outcome, "production_change_pct", "yield_change_pct", "area_change_pct"]))
    return frame[keep].merge(weather, on=keys, how="left", validate="one_to_one")


def relationship_table(frame, c, unit="region"):
    rows = []
    for name, col in CLIMATE.items():
        for form in ["absolute", "anomaly"]:
            x = col if form == "absolute" else col+"_anomaly"
            for outcome in ["production_change_pct", "yield_change_pct"]:
                for lag in range(3):
                    aligned = align_lag(frame, x, outcome, lag, unit)
                    for region, g in aligned.groupby("region"):
                        valid = g.dropna(subset=["climate_value", outcome])
                        for method in ["Pearson", "Spearman"]:
                            rows.append(dict(region=region, climate=name, form=form, outcome=outcome, lag=lag,
                                             analysis_unit="province-year pooled" if unit == "province_id" else "regional annual",
                                             start_year=valid.year.min(), end_year=valid.year.max(), **correlation(g, "climate_value", outcome, method, c["minimum_n"])))
    return adjust(pd.DataFrame(rows))


def bins(frame, x, y, c):
    rows, tests = [], []
    for region, g in frame.groupby("region"):
        v = g[[x, y]].dropna().copy()
        if len(v) < c["minimum_n"] or v[x].nunique() < 3:
            rows.append(dict(region=region, category=INSUFFICIENT, n=len(v), mean=np.nan, ci_low=np.nan, ci_high=np.nan))
            continue
        edges = v[x].quantile([0, 1/3, 2/3, 1]).to_numpy()
        if len(np.unique(edges)) < 4:
            rows.append(dict(region=region, category=INSUFFICIENT, n=len(v), mean=np.nan, ci_low=np.nan, ci_high=np.nan))
            continue
        v["category"] = pd.cut(v[x], edges, labels=["Low", "Medium", "High"], include_lowest=True)
        for cat, a in v.groupby("category", observed=True):
            n, mean = len(a), a[y].mean()
            margin = stats.t.ppf(.975, n-1)*a[y].sem() if n >= 3 else np.nan
            rows.append(dict(region=region, category=str(cat), n=n, mean=mean, ci_low=mean-margin, ci_high=mean+margin,
                             climate_min=a[x].min(), climate_max=a[x].max()))
        groups = [a[y].to_numpy() for _, a in v.groupby("category", observed=True)]
        p = stats.kruskal(*groups).pvalue if all(len(a) >= 3 for a in groups) and v[y].nunique() > 1 else np.nan
        tests.append(dict(region=region, method="Kruskal-Wallis across climate terciles", n=len(v), p=p, status="Exploratory" if np.isfinite(p) else INSUFFICIENT))
    return pd.DataFrame(rows), adjust(pd.DataFrame(tests))


def abnormal(frame, outcome="Yield", method="IQR", direction="Low", c=None):
    c = c or config()
    short = outcome.lower()
    col = short+"_deviation"
    f = frame.copy()
    f["score"] = np.nan
    f["abnormal"] = False
    f["detection_status"] = INSUFFICIENT
    for _, g in f.groupby("region"):
        s = g[col].dropna()
        if len(s) < c["minimum_n"] or s.std() <= 0: continue
        z = (g[col]-s.mean())/s.std()
        lo, hi = s.quantile([.25, .75]); spread = hi-lo
        flag = z.lt(-c["z_threshold"]) if direction == "Low" else z.gt(c["z_threshold"])
        if method == "IQR": flag = g[col].lt(lo-c["iqr_factor"]*spread) if direction == "Low" else g[col].gt(hi+c["iqr_factor"]*spread)
        f.loc[g.index, "score"] = z
        f.loc[g.index, "abnormal"] = flag
        f.loc[g.index, "detection_status"] = "Available"
    totals = f.groupby("year").production_ton.sum(min_count=1)
    events = f[f.abnormal].groupby("year").agg(affected_regions=("region", "nunique"), affected_production_ton=("production_ton", "sum"))
    event = pd.DataFrame({"year": sorted(f.year.unique())}).set_index("year").join(events)
    event[["affected_regions", "affected_production_ton"]] = event[["affected_regions", "affected_production_ton"]].fillna(0)
    event["affected_production_share_pct"] = event.affected_production_ton.div(totals.where(totals.gt(0)))*100
    event["scope"] = np.select([event.affected_regions.gt(1), event.affected_regions.eq(1)], ["Widespread", "Localized"], default="No detected event")
    supported = f.groupby("year").detection_status.apply(lambda s: s.eq("Available").all())
    event.loc[~supported, ["affected_regions", "affected_production_ton", "affected_production_share_pct"]] = np.nan
    event.loc[~supported, "scope"] = INSUFFICIENT
    return f, event.reset_index()


def sensitivity(frame, outcome, c):
    rows = []
    for region, g in frame.groupby("region"):
        for climate, col in CLIMATE.items():
            x, y = col+"_anomaly", outcome.lower()+"_change_pct"
            v = g[[x, y]].dropna()
            row = dict(region=region, climate=climate, outcome=outcome, n=len(v), slope=np.nan,
                       standardized_coefficient=np.nan, ci_low=np.nan, ci_high=np.nan, p=np.nan,
                       low_category_mean=np.nan, high_category_mean=np.nan, status=INSUFFICIENT,
                       slope_units="outcome change percentage points per "+("C" if climate=="Temperature" else "rainfall anomaly percentage point"))
            if len(v) >= c["minimum_n"] and v[x].nunique() > 1 and v[y].nunique() > 1:
                fit = stats.linregress(v[x], v[y]); margin = stats.t.ppf(.975, len(v)-2)*fit.stderr
                row.update(slope=fit.slope, standardized_coefficient=fit.rvalue, ci_low=fit.slope-margin, ci_high=fit.slope+margin,
                           p=fit.pvalue, low_category_mean=v.loc[v[x].le(v[x].quantile(1/3)), y].mean(),
                           high_category_mean=v.loc[v[x].ge(v[x].quantile(2/3)), y].mean(), status="Exploratory univariate association")
            rows.append(row)
    return adjust(pd.DataFrame(rows))


def priority(frame, outcome, threshold, reference, c, normalization_frame=None):
    if normalization_frame is not None:
        full,sen=priority(normalization_frame,outcome,threshold,reference,c)
        return full[full.region.isin(frame.region.unique())].copy(),sen[sen.region.isin(frame.region.unique())].copy()
    sen = sensitivity(frame, outcome, c)
    rows = []
    total = frame.groupby("year").production_ton.sum(min_count=1).mean()
    metric = outcome.lower()+("_change_pct" if reference == "Previous year" else "_deviation_pct")
    for region, g in frame.groupby("region"):
        v = g[metric].dropna(); declined = v.lt(-threshold)
        s = sen[sen.region.eq(region)]
        # Holm-supported association is retained as diagnostic evidence; its default score weight is zero.
        evidence = s.loc[s.q.lt(c["alpha"]), "standardized_coefficient"].abs().max()
        adequate = s.standardized_coefficient.notna().all()
        rows.append(dict(region=region, n=len(v), volatility=cv(g[OUTCOMES[outcome]]), frequency=declined.mean()*100 if len(v) else np.nan,
                         magnitude=-v[declined].mean() if declined.any() else 0. if len(v) else np.nan,
                         largest_decline_pct=-v.min() if v.lt(0).any() else 0. if len(v) else np.nan,
                         production_associated_ton=g.loc[v.index[declined], "production_ton"].sum(min_count=1) if declined.any() else 0.,
                         climate_evidence=(float(evidence) if pd.notna(evidence) else 0.) if adequate else np.nan,
                         production_relevance=g.production_ton.mean()/total*100 if total > 0 else np.nan,
                         data_confidence=float(g.complete.mean()), climate_n=int(s.n.min()) if len(s) else 0))
    f = pd.DataFrame(rows)
    weights = c["risk_weights"]
    if any(v < 0 for v in weights.values()) or sum(weights.values()) <= 0: raise ValueError("Risk weights must be nonnegative with positive total")
    for col in weights:
        a = f[col]; span = a.max()-a.min()
        normalized = ((a-a.min())/span) if span > 0 else a.where(a.isna(), 0.)
        # The confidence component is a lack-of-confidence flag, never sufficient to assign priority.
        f[col+"_component"] = 1-a if col == "data_confidence" else normalized
    cols = [x+"_component" for x,w in weights.items() if w>0]
    valid = f[cols].notna().all(axis=1) & f.n.ge(c["minimum_n"]) & f.climate_n.ge(c["minimum_n"]) & f.data_confidence.ge(.9)
    valid &= len(f) >= c["minimum_score_regions"]
    f["score_reference_region_n"] = len(f)
    f["effective_n"]=f[['n','climate_n']].min(axis=1)
    for name,weight in weights.items():f[name+'_weight']=weight
    f["monitoring_score"] = sum(f[k+"_component"]*w for k, w in weights.items() if w>0)/sum(weights.values())
    f.loc[~valid, "monitoring_score"] = np.nan
    f["priority"] = np.select([~valid, f.monitoring_score.ge(c["priority_high"]), f.monitoring_score.ge(c["priority_moderate"])],
                               [INSUFFICIENT, "Higher Monitoring Priority", "Moderate Monitoring Priority"], default="Lower Monitoring Priority")
    return f, sen


def segmentation(frame, k, c):
    names = ["temperature", "rainfall", "yield_cv", "production_cv", "climate_association"]
    def features(f):
        rows = []
        for region, g in f.groupby("region"):
            r = [correlation(g, col+"_anomaly", "yield_change_pct", minimum=c["minimum_n"])["coefficient"] for col in CLIMATE.values()]
            rows.append(dict(region=region, temperature=g.temperature_c.mean(), rainfall=g.rainfall_mm.mean(), yield_cv=cv(g.yield_value),
                             production_cv=cv(g.production_ton), climate_association=max(map(abs, r)) if all(np.isfinite(r)) else np.nan))
        return pd.DataFrame(rows).set_index("region")
    raw = features(frame)
    empty = dict(assignments=pd.DataFrame({"status": [INSUFFICIENT]}), profiles=pd.DataFrame(), standardized=pd.DataFrame(), linkage=pd.DataFrame(), stability=pd.DataFrame())
    if k not in (2, 3) or len(raw) < max(k+1, 4) or raw.isna().any().any(): return empty
    scale = raw.std(ddof=0).replace(0, 1)
    z = (raw-raw.mean())/scale
    link = linkage(z.to_numpy(), method="ward")
    labels = cut_tree(link, n_clusters=k).flatten()+1
    assignments = raw.reset_index().assign(cluster=labels)
    _, _, vt = np.linalg.svd(z.to_numpy(), full_matrices=False)
    xy = z.to_numpy()@vt[:2].T
    assignments["PC1"], assignments["PC2"] = xy[:, 0], xy[:, 1]
    # Year-block resampling tests feature/assignment sensitivity; not independent validation.
    rng = np.random.default_rng(c["seed"])
    years = sorted(frame.year.unique()); agreement = np.zeros((len(raw), len(raw))); successful = 0
    for _ in range(c["cluster_bootstraps"]):
        draw = rng.choice(years, len(years), replace=True)
        boot = pd.concat([frame[frame.year.eq(y)] for y in draw], ignore_index=True)
        b = features(boot).reindex(raw.index)
        if b.isna().any().any(): continue
        bz = (b-b.mean())/b.std(ddof=0).replace(0, 1)
        lab = cut_tree(linkage(bz.to_numpy(), method="ward"), n_clusters=k).flatten()
        agreement += lab[:, None] == lab[None, :]; successful += 1
    stability = pd.DataFrame(agreement/successful if successful else np.full_like(agreement, np.nan), index=raw.index, columns=raw.index)
    profiles = assignments.groupby("cluster")[names].mean().reset_index()
    distance = squareform(pdist(z))
    silhouette = []
    for i, label in enumerate(labels):
        own = np.where(labels == label)[0]; other = [distance[i, labels == j].mean() for j in np.unique(labels) if j != label]
        a = distance[i, own[own != i]].mean() if len(own) > 1 else 0.
        b = min(other)
        silhouette.append((b-a)/max(a, b) if len(own) > 1 and max(a, b) > 0 else 0.)
    assignments["silhouette"] = silhouette
    assignments["stability_resamples"] = successful
    return dict(assignments=assignments, profiles=profiles, standardized=z.reset_index(), linkage=pd.DataFrame(link, columns=["left", "right", "distance", "size"]), stability=stability.reset_index())


def interregional(frame, metric, method, threshold, c):
    wide = frame.pivot(index="year", columns="region", values=metric).sort_index()
    rows = []
    supply = frame.groupby("region").production_ton.mean()
    total = frame.groupby("year").production_ton.sum(min_count=1).mean()
    for a, b in itertools.combinations(wide.columns, 2):
        pair = wide[[a, b]].dropna()
        corr = correlation(pair, a, b, method, c["minimum_n"])
        midpoint = int(np.median(wide.index)) if len(wide) else 0
        early = correlation(pair.loc[pair.index <= midpoint], a, b, method, c["minimum_n"])
        late = correlation(pair.loc[pair.index > midpoint], a, b, method, c["minimum_n"])
        if len(pair):
            q1, q3 = pair.quantile(.25), pair.quantile(.75)
            clean = pair[((pair >= q1-1.5*(q3-q1)) & (pair <= q3+1.5*(q3-q1))).all(axis=1)]
        else: clean = pair
        robust = correlation(clean, a, b, method, c["minimum_n"])
        alternative = correlation(pair, a, b, "Spearman" if method == "Pearson" else "Pearson", c["minimum_n"])
        joint = pair[a].lt(-threshold) & pair[b].lt(-threshold)
        rows.append(dict(region_a=a, region_b=b, **corr, metric=metric, joint_decline_frequency_pct=joint.mean()*100 if len(pair) else np.nan,
                         joint_decline_years=", ".join(map(str, pair.index[joint])), joint_n=int(joint.sum()),
                         production_share_pct=(supply[a]+supply[b])/total*100 if total > 0 else np.nan,
                         missing_pair_years=len(wide)-len(pair), early_coefficient=early["coefficient"], late_coefficient=late["coefficient"],
                         early_n=early["n"], late_n=late["n"], outlier_removed_coefficient=robust["coefficient"], outlier_removed_n=robust["n"],
                         alternative_method_coefficient=alternative["coefficient"],
                         interpretation="Explore complementarity" if corr["n"] >= c["minimum_n"] and abs(corr["coefficient"]) < c["weak_correlation"] else "Inconclusive / correlated exposure"))
    return adjust(pd.DataFrame(rows))


def decisions(bench, trends, relationships, events, risk, segments, pairs, c):
    rows = []
    def add(category, region, metric, evidence, confidence, implication, action, limitation):
        rows.append({"Insight Category": category, "Region / Province": region, "Supporting Metric": metric,
                     "Evidence Summary": evidence, "Statistical Confidence / Data Quality": confidence,
                     "Business Implication": implication, "Suggested Follow-up Action": action, "Limitations": limitation})
    for _, r in risk.iterrows():
        add("Monitoring priority", r.region, f"Score {r.monitoring_score:.3f}; decline frequency {r.frequency:.1f}%",
            r.priority, f"n={r.n}; completeness={r.data_confidence:.0%}", "Prioritize evidence review",
            "Collect additional historical observations and exposure data" if r.priority == INSUFFICIENT else "Review suppliers, crop calendars, irrigation, price and logistics", "Historical score is not crop-failure probability")
    for _, r in bench["statistics"].query("outcome == 'Yield'").iterrows():
        if r.n >= c["minimum_n"] and r.cv_pct <= c["stable_cv_pct"] and r["mean"] >= bench["statistics"].query("outcome == 'Yield'")["mean"].median():
            add("Stable sourcing reference", r.region, f"Yield {r['mean']:.2f} t/ha; CV {r.cv_pct:.1f}%", "High relative mean and configured low CV", f"n={r.n}", "Candidate for supplier evaluation", "Check supplier availability, quality and logistics", "Regional history does not guarantee supplier performance")
    for _, r in bench["gaps"].iterrows():
        if r.classification in ["Bright Spot", "Underperformer"]:
            add("Climate-context benchmark", r.region, f"Gap {r.performance_gap:+.2f} t/ha [{r.ci_low:.2f}, {r.ci_high:.2f}]", r.classification,
                f"n={r.n}; nominal peer-gap CI", "Review unexplained regional differences", "Investigate soil, varieties, irrigation and agronomic practices", "Climate peers are descriptive; residual is not management efficiency")
    for _, r in trends[trends.q.lt(c["alpha"])].iterrows():
        add("Historical trend", r.region, f"{r.indicator}: {r.slope:+.3f} {r.units}", f"Holm q={r.q:.3g}; block q={r.block_q:.3g}", f"n={r.n}", "Check changing planning assumptions", "Review crop-calendar and production records", "Short series and temporal dependence limit inference")
    rel = relationships[(relationships.lag.eq(0)) & relationships.form.eq("anomaly") & relationships.method.eq("Pearson")]
    for _, r in rel[rel.q.lt(c["alpha"])].iterrows():
        add("Climate association", r.region, f"{r.climate} / {r.outcome}: r={r.coefficient:.2f}; q={r.q:.3g}", f"{r.analysis_unit}; lag {r.lag}; {r.start_year:.0f}-{r.end_year:.0f}", f"n={r.n}; nominal CI [{r.ci_low:.2f}, {r.ci_high:.2f}]", "Strengthen monitoring hypotheses", "Review water availability and crop calendars alongside area changes", "Association does not establish cause; no proven intervention")
    if not pairs.empty:
        for _, r in pairs[pairs.interpretation.eq("Explore complementarity")].iterrows():
            add("Diversification review", r.region_a+" / "+r.region_b, f"r={r.coefficient:.2f}; joint declines={r.joint_decline_frequency_pct:.1f}%", f"Combined production share={r.production_share_pct:.1f}%", f"n={r.n}; q={r.q:.3g}", "Candidate for geographic sourcing review", "Compare supplier availability, price, quality and transport", "Low historical correlation does not guarantee future protection")
    valid_events = events.dropna(subset=["affected_production_share_pct"])
    if not valid_events.empty and valid_events.affected_regions.gt(0).any():
        r = valid_events.loc[valid_events.affected_production_share_pct.idxmax()]
        add("Simultaneous events", "Selected regions", f"{r.year}: {r.affected_regions:.0f} regions; {r.affected_production_share_pct:.1f}% supply share", r.scope, "Detrended event screen", "Review common exposure", "Inspect monthly weather and local production records", "Simultaneity is not evidence of a common cause")
    if not segments["assignments"].empty and "cluster" in segments["assignments"]:
        for _, r in segments["assignments"].iterrows():
            add("Exploratory segment", r.region, f"Cluster {r.cluster}; silhouette={r.silhouette:.2f}", "Standardized climate, variability and association features", f"{r.stability_resamples} year-resamples; only seven regional units", "Compare monitoring profiles", "Inspect cluster profile and co-assignment stability", "Feature-dependent clusters are not operationally validated")
    return pd.DataFrame(rows)


def load_context(years=(2010, 2024), regions=None, baseline=(2010, 2024), c=None):
    c = c or config()
    r = pd.read_parquet(OUT / "regional.parquet")
    p = pd.read_parquet(OUT / "province.parquet")
    regions = sorted(r.region.unique()) if regions is None else regions
    # Reference uses the independent full prepared period; analysis filters apply afterwards.
    r = derive(r, "region", baseline, c["minimum_n"])
    p = derive(p, "province_id", baseline, c["minimum_n"])
    return select(r, years, regions), select(p, years, regions)


def run_task(task, r, p, c):
    if task == "benchmark": return benchmark(r, c)
    if task == "trends": return {"trends": trend_table(r, c)}
    if task == "relationships":
        categories,tests=[],[]
        for climate,col in CLIMATE.items():
            for form in ["absolute","anomaly"]:
                for outcome in ["production_change_pct","yield_change_pct"]:
                    b,t=bins(r,col if form=="absolute" else col+"_anomaly",outcome,c)
                    categories.append(b.assign(climate=climate,form=form,outcome=outcome))
                    tests.append(t.assign(climate=climate,form=form,outcome=outcome))
        return dict(regional=relationship_table(r, c), pooled=relationship_table(p, c, "province_id"),
                    bins=pd.concat(categories,ignore_index=True),bin_tests=pd.concat(tests,ignore_index=True))
    if task == "abnormal":
        f, e = abnormal(r, c=c)
        return dict(events=f, simultaneous=e)
    if task == "risk":
        f, s = priority(r, "Yield", c["decline_threshold_pct"], "Previous year", c)
        return dict(priority=f, sensitivity=s)
    if task == "segments": return segmentation(r, 2, c)
    if task == "interregional": return {"pairs": interregional(r, "production_change_pct", "Pearson", c["decline_threshold_pct"], c)}
    if task == "decisions":
        b=benchmark(r,c); t=trend_table(r,c); rel=relationship_table(r,c); _,e=abnormal(r,c=c)
        risk,_=priority(r,"Yield",c["decline_threshold_pct"],"Previous year",c); seg=segmentation(r,2,c)
        pair=interregional(r,"production_change_pct","Pearson",c["decline_threshold_pct"],c)
        return {"insights": decisions(b,t,rel,e,risk,seg,pair,c)}
    raise ValueError(task)


TASKS = ["benchmark", "trends", "relationships", "abnormal", "risk", "segments", "interregional", "decisions"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=["all", "prepare"]+TASKS, nargs="?", default="all")
    args = parser.parse_args()
    if args.task in ["all", "prepare"]:
        audit=prepare()
        print(json.dumps({k:audit[k] for k in ["period","province_rows","regional_rows","monthly_rows","incomplete_province_years","incomplete_province_months"]}))
    if args.task == "prepare": return
    c = config(); r,p = load_context(c=c)
    for task in TASKS if args.task == "all" else [args.task]:
        folder = OUT / task; folder.mkdir(parents=True, exist_ok=True)
        manifest = dict(task=task,built_utc=datetime.now(timezone.utc).isoformat(),analysis_period=[2010,2024],
                        reference_period=[2010,2024],region_n=int(r.region.nunique()),observational_units=["regional annual", "province-year pooled" if task=="relationships" else "regional annual"],
                        units=UNITS,parameters=c,tables={},limitations=["Exploratory observational analysis; no causal inference", "Nominal intervals and tests do not fully adjust temporal/pooled dependence"])
        for name, f in run_task(task,r,p,c).items():
            path=folder/(name+".parquet"); f.to_parquet(path,index=False)
            manifest["tables"][name]=dict(rows=len(f),schema={col:str(dtype) for col,dtype in f.dtypes.items()},sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        (folder/"metadata.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"{task}: saved")
    (OUT / "parameters.json").write_text(json.dumps(c, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
