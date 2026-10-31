"""Reproduce a synthetic credit-risk work sample. Run: python -m src.pipeline.

All borrower and macroeconomic observations are simulated. The pipeline contains
no employer material and estimates no real borrower or bank risk.
"""
from __future__ import annotations

import json
from pathlib import Path
import platform
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import norm
from sklearn.calibration import calibration_curve
from sklearn.metrics import (average_precision_score, brier_score_loss,
    confusion_matrix, f1_score, log_loss, precision_recall_curve,
    precision_score, recall_score, roc_auc_score, roc_curve)
from sklearn.tree import DecisionTreeClassifier, export_text

ROOT = Path(__file__).resolve().parents[1]
SEED = 2026
FEATURES = ["leverage", "dscr", "interest_rate_pct", "gdp_growth_pct", "past_due_30d"]
TERMS = ["Intercept"] + FEATURES
SCENARIOS = {
    "Base": {"leverage_add": 0.0, "dscr_multiplier": 1.0, "interest_rate_add_pp": 0.0, "gdp_growth_add_pp": 0.0},
    "Adverse": {"leverage_add": 0.05, "dscr_multiplier": 0.85, "interest_rate_add_pp": 1.0, "gdp_growth_add_pp": -2.0},
    "Severe": {"leverage_add": 0.10, "dscr_multiplier": 0.70, "interest_rate_add_pp": 2.0, "gdp_growth_add_pp": -4.0},
}
LGD = 0.45
COLORS = {"Logistic": "#087F8C", "Decision tree": "#D78A25"}


def json_save(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def generate_sources(root=ROOT):
    """Generate three source tables with one exact duplicate and two missing cells."""
    rng = np.random.default_rng(SEED)
    dates = pd.date_range("2017-03-31", "2024-12-31", freq="QE")
    n = len(dates) * 200
    q = np.repeat(np.arange(len(dates)), 200)
    # These cycles are invented, not observed Chinese macroeconomic indicators.
    gdp = 5.0 + 1.4*np.sin(np.arange(32)*0.43) - 0.035*np.arange(32)
    base_rate = 4.1 + 0.45*np.cos(np.arange(32)*0.37)
    sector = rng.choice(["Manufacturing", "Wholesale", "Technology", "Transport", "Services"], n,
                        p=[.27, .24, .17, .13, .19])
    lev = np.clip(rng.beta(3.0, 4.0, n) + (sector == "Transport")*.05, .03, .92)
    dscr = np.clip(rng.lognormal(.52, .47, n), .30, 6.0)
    past_due = rng.binomial(1, expit(-3.0 + 1.7*lev - .2*dscr), n)
    rate = base_rate[q] + 1.5*lev + .65*past_due + rng.normal(0, .55, n)
    assets = rng.lognormal(4.45, .82, n)
    debt = lev*assets
    revenue = assets*rng.uniform(.7, 1.8, n)
    ebitda = revenue*rng.uniform(.09, .24, n)
    debt_service = ebitda/dscr
    eta = -2.4 + 3.4*lev - .65*dscr + .22*rate - .12*gdp[q] + 1.2*past_due
    default = rng.binomial(1, expit(eta))
    ids = np.array([f"SYN-{i:06d}" for i in range(1, n+1)])
    snaps = dates[q].strftime("%Y-%m-%d")
    financials = pd.DataFrame({"borrower_id": ids, "snapshot_date": snaps, "sector": sector,
        "revenue_cny_m": revenue, "debt_cny_m": debt, "total_assets_cny_m": assets,
        "ebitda_cny_m": ebitda, "debt_service_cny_m": debt_service,
        "interest_rate_pct": rate}).round(8)
    financials.loc[n-2, "ebitda_cny_m"] = np.nan
    financials.loc[n-1, "debt_service_cny_m"] = np.nan
    financials = pd.concat([financials, financials.iloc[[100]]], ignore_index=True)
    repayments = pd.DataFrame({"borrower_id": ids, "snapshot_date": snaps,
        "past_due_30d": past_due, "default_12m": default,
        "outcome_window_end": (dates[q] + pd.DateOffset(years=1)).strftime("%Y-%m-%d")})
    macro = pd.DataFrame({"snapshot_date": dates.strftime("%Y-%m-%d"),
        "gdp_growth_pct": gdp.round(8), "source": "Synthetic quarterly cycle; not real economic data"})
    raw = root/"data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    financials.to_csv(raw/"financials.csv", index=False)
    repayments.to_csv(raw/"repayments.csv", index=False)
    macro.to_csv(raw/"macro.csv", index=False)


def prepare_data(root=ROOT):
    raw = root/"data/raw"
    f = pd.read_csv(raw/"financials.csv")
    r = pd.read_csv(raw/"repayments.csv")
    m = pd.read_csv(raw/"macro.csv")
    key = ["borrower_id", "snapshot_date"]
    audit = []
    def event(step, count, detail):
        audit.append({"step": step, "count": int(count), "detail": detail})
    event("raw_financial_rows", len(f), "Includes one exact duplicate and two incomplete borrower records")
    duplicate = f.duplicated(keep="first")
    exceptions = f.loc[duplicate, key].copy().assign(reason="Exact duplicate removed")
    event("exact_duplicates_removed", duplicate.sum(), "All columns match; retain first occurrence")
    f = f.loc[~duplicate].copy()
    if f.duplicated(key).any() or r.duplicated(key).any() or m.duplicated("snapshot_date").any():
        raise ValueError("Conflicting duplicate keys must be resolved, not silently discarded")
    joined = f.merge(r, on=key, how="outer", validate="one_to_one", indicator=True)
    if not joined["_merge"].eq("both").all():
        raise ValueError("Financial and repayment source keys do not reconcile")
    joined = joined.drop(columns="_merge").merge(m.drop(columns="source"), on="snapshot_date",
        how="left", validate="many_to_one", indicator=True)
    if not joined["_merge"].eq("both").all():
        raise ValueError("A snapshot date has no macro observation")
    joined = joined.drop(columns="_merge")
    event("matched_borrower_rows", len(joined), "One-to-one borrower/date join; many-to-one macro/date join")
    required = ["revenue_cny_m", "debt_cny_m", "total_assets_cny_m", "ebitda_cny_m",
                "debt_service_cny_m", "interest_rate_pct", "gdp_growth_pct", "past_due_30d", "default_12m"]
    complete = joined[required].notna().all(axis=1)
    excluded = joined.loc[~complete, key].copy().assign(reason="Missing EBITDA or debt service; excluded before modeling")
    exceptions = pd.concat([exceptions, excluded], ignore_index=True)
    event("incomplete_rows_excluded", (~complete).sum(), "Complete-case rule; no label-driven removal or imputation")
    clean = joined.loc[complete].copy()
    if not (clean["total_assets_cny_m"].gt(0).all() and clean["debt_service_cny_m"].gt(0).all()):
        raise ValueError("Invalid ratio denominator")
    if not clean[["past_due_30d", "default_12m"]].isin([0,1]).all().all():
        raise ValueError("Binary fields must be 0 or 1")
    if not clean["borrower_id"].is_unique:
        raise ValueError("This demonstration requires one observation per independent borrower")
    clean["leverage"] = clean["debt_cny_m"] / clean["total_assets_cny_m"]
    clean["dscr"] = clean["ebitda_cny_m"] / clean["debt_service_cny_m"]
    years = pd.to_datetime(clean["snapshot_date"]).dt.year
    clean["split"] = np.select([years<=2019, years.isin([2020, 2022]), years==2021], ["train", "embargo", "validation"], default="test")
    # Outcome window is deliberately excluded from the model frame and predictors.
    clean = clean.drop(columns="outcome_window_end").sort_values(key).reset_index(drop=True)
    event("model_rows", len(clean), "Final complete-case cohort; all outcomes mature by 2025-12-31")
    cols = ["borrower_id", "snapshot_date", "sector", "revenue_cny_m", "debt_cny_m", "total_assets_cny_m",
            "ebitda_cny_m", "debt_service_cny_m", *FEATURES, "default_12m", "split"]
    clean = clean[cols]
    (root/"data/processed").mkdir(parents=True, exist_ok=True)
    (root/"outputs").mkdir(parents=True, exist_ok=True)
    clean.to_csv(root/"data/processed/model_data.csv", index=False)
    pd.DataFrame(audit).to_csv(root/"outputs/data_quality_audit.csv", index=False)
    exceptions.to_csv(root/"outputs/data_quality_exceptions.csv", index=False)
    reconciliation = {"raw_rows": len(pd.read_csv(raw/"financials.csv")), "exact_duplicate_rows": int(duplicate.sum()),
        "unique_borrowers": len(joined), "excluded_incomplete": int((~complete).sum()), "model_rows": len(clean),
        "unique_debt_cny_m": float(joined.debt_cny_m.sum()),
        "excluded_debt_cny_m": float(joined.loc[~complete, "debt_cny_m"].sum()),
        "model_debt_cny_m": float(clean.debt_cny_m.sum())}
    json_save(root/"outputs/reconciliation.json", reconciliation)
    return clean, pd.DataFrame(audit), reconciliation


def design(frame):
    return np.column_stack([np.ones(len(frame)), frame[FEATURES].to_numpy(dtype=float)])


def fit_logistic(frame):
    """Unpenalized MLE with HC1 sandwich: n/(n-k) H^-1 S'S H^-1.

    H=X'WX; observation score S_i=x_i(y_i-p_i). Normal Wald intervals use
    independent-observation asymptotics. This is not clustered or causal inference.
    """
    X = design(frame)
    y = frame.default_12m.to_numpy(dtype=float)
    def objective(beta):
        eta = X@beta
        return float(np.sum(np.logaddexp(0, eta) - y*eta))
    def gradient(beta):
        return X.T@(expit(X@beta)-y)
    def hessian(beta):
        p = expit(X@beta)
        return X.T@((p*(1-p))[:,None]*X)
    initial = np.zeros(X.shape[1])
    initial[0] = np.log(y.mean()/(1-y.mean()))
    result = minimize(objective, initial, method="trust-exact", jac=gradient, hess=hessian,
                      options={"gtol":1e-6, "maxiter":300})
    beta = result.x
    gmax = float(np.max(np.abs(gradient(beta))))
    H = hessian(beta)
    mineig = float(np.linalg.eigvalsh(H).min())
    if gmax > 1e-5 or mineig <= 0 or not np.all(np.isfinite(beta)):
        raise RuntimeError(f"Logistic did not converge: max gradient {gmax}, min Hessian eigenvalue {mineig}")
    p = expit(X@beta)
    score = X*(y-p)[:,None]
    Hinv = np.linalg.inv(H)
    n,k = X.shape
    covariance = (n/(n-k))*(Hinv@(score.T@score)@Hinv)
    se = np.sqrt(np.diag(covariance))
    z = beta/se
    coef = pd.DataFrame({"term":TERMS, "coefficient":beta, "std_error":se,
        "z":z, "p_value":2*norm.sf(np.abs(z)), "ci_lower":beta-1.95996398454*se,
        "ci_upper":beta+1.95996398454*se, "odds_ratio":np.exp(beta)})
    diagnostics = {"n_training":int(n), "n_parameters":int(k), "converged_by_score":True,
        "optimizer_success":bool(result.success), "optimizer_message":str(result.message),
        "max_absolute_score":gmax, "minimum_hessian_eigenvalue":mineig,
        "log_likelihood":-objective(beta), "covariance":"HC1: n/(n-k) times independent-observation score sandwich"}
    return beta, coef, diagnostics


def predict_logistic(frame, beta):
    return expit(design(frame)@np.asarray(beta))


def vif_table(frame):
    values = frame[FEATURES].to_numpy(float)
    rows=[]
    for j, name in enumerate(FEATURES):
        y = values[:,j]
        X = np.column_stack([np.ones(len(y)), np.delete(values,j,axis=1)])
        residual = y-X@np.linalg.lstsq(X,y,rcond=None)[0]
        r2 = 1-np.sum(residual**2)/np.sum((y-y.mean())**2)
        rows.append({"feature":name,"vif":float(1/(1-r2))})
    return pd.DataFrame(rows)


def choose_threshold(y, p):
    """Validation-only F1 on a fixed 0.01..0.80 grid; ties use larger threshold."""
    rows=[{"threshold":float(t),"f1":float(f1_score(y,np.asarray(p)>=t,zero_division=0))}
          for t in np.arange(1,81)/100]
    table=pd.DataFrame(rows)
    chosen=table.sort_values(["f1","threshold"],ascending=[False,False]).iloc[0]
    return float(chosen.threshold), table


def metric_row(name, split, y, p, threshold):
    pred = np.asarray(p)>=threshold
    tn,fp,fn,tp = confusion_matrix(y,pred,labels=[0,1]).ravel()
    return {"model":name,"split":split,"n":int(len(y)),"defaults":int(np.sum(y)),
        "default_rate":float(np.mean(y)),"mean_pd":float(np.mean(p)),
        "roc_auc":float(roc_auc_score(y,p)),"average_precision":float(average_precision_score(y,p)),
        "brier_score":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p)),
        "threshold":float(threshold),"precision":float(precision_score(y,pred,zero_division=0)),
        "recall":float(recall_score(y,pred,zero_division=0)),"f1":float(f1_score(y,pred,zero_division=0)),
        "tn":int(tn),"fp":int(fp),"fn":int(fn),"tp":int(tp)}


def risk_band(probability):
    return pd.cut(probability,[-np.inf,.05,.15,.30,np.inf],right=False,
                  labels=["Low","Moderate","Elevated","High"]).astype(str)


def stress_frame(frame, scenario):
    out=frame.copy()
    out["leverage"]=(out.leverage+scenario["leverage_add"]).clip(0,1)
    out["dscr"]=out.dscr*scenario["dscr_multiplier"]
    out["interest_rate_pct"]=out.interest_rate_pct+scenario["interest_rate_add_pp"]
    out["gdp_growth_pct"]=out.gdp_growth_pct+scenario["gdp_growth_add_pp"]
    return out


def build_charts(root, test, metrics, coef, scenarios):
    out=root/"outputs/charts"
    out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,
        "axes.spines.right":False,"axes.titleweight":"bold","axes.labelcolor":"#34465B",
        "text.color":"#172B45","axes.edgecolor":"#BBC6D2","savefig.facecolor":"white"})
    y=test.default_12m
    fig, axs=plt.subplots(1,3,figsize=(14,4.6),layout="constrained")
    for name,col in [("Logistic","pd_logistic"),("Decision tree","pd_tree")]:
        p=test[col]
        fpr,tpr,_=roc_curve(y,p)
        precision,recall,_=precision_recall_curve(y,p)
        fraction,mean=calibration_curve(y,p,n_bins=8,strategy="quantile")
        axs[0].plot(fpr,tpr,color=COLORS[name],lw=2,label=f"{name} (AUC {roc_auc_score(y,p):.3f})")
        axs[1].plot(recall,precision,color=COLORS[name],lw=2,label=f"{name} (AP {average_precision_score(y,p):.3f})")
        axs[2].plot(mean,fraction,"o-",color=COLORS[name],lw=2,label=name)
    axs[0].plot([0,1],[0,1],"--",c="#C2CBD4",lw=1)
    axs[1].axhline(y.mean(),ls="--",c="#9DAAB8",label=f"Prevalence {y.mean():.1%}")
    axs[2].plot([0,1],[0,1],"--",c="#C2CBD4",lw=1)
    for ax,title,xlabel,ylabel in zip(axs,["Discrimination","Precision–recall","Calibration"],
            ["False positive rate","Recall","Mean predicted probability"],
            ["True positive rate","Precision","Observed default rate"]):
        ax.set(title=title,xlabel=xlabel,ylabel=ylabel,xlim=(0,1),ylim=(0,1)); ax.legend(fontsize=8,loc="lower right" if title=="Discrimination" else "best"); ax.grid(alpha=.15)
    fig.suptitle("Held-out borrowers · 2023–2024",fontsize=16,fontweight="bold")
    fig.savefig(out/"model_validation.png",dpi=160); plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),layout="constrained")
    for ax,field,title in [(axs[0],"mean_pd","Mean default probability"),(axs[1],"ecl_proxy_cny_m","12-month loss proxy (CNY million)")]:
        bars=ax.bar(scenarios.scenario,scenarios[field],color=["#087F8C","#D78A25","#AE4C53"],width=.58)
        for b,v in zip(bars,scenarios[field]):
            ax.text(b.get_x()+b.get_width()/2,b.get_height(),f"{v:.1%}" if field=="mean_pd" else f"{v:,.1f}",ha="center",va="bottom",fontweight="bold")
        ax.set_title(title); ax.set_ylim(0,scenarios[field].max()*1.2); ax.grid(axis="y",alpha=.15)
        if field=="mean_pd": ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    fig.suptitle("Illustrative conditional shocks · frozen test cohort",fontsize=15,fontweight="bold")
    fig.savefig(out/"stress_scenarios.png",dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.4,4.3),layout="constrained")
    c=coef.iloc[1:].iloc[::-1]
    labels={"leverage":"Leverage (per 1.0 debt/assets)","dscr":"Debt-service coverage (per 1.0x)",
        "interest_rate_pct":"Interest rate (per 1 percentage point)","gdp_growth_pct":"GDP growth (per 1 percentage point)","past_due_30d":"Past-due flag (0 → 1)"}
    ax.errorbar(c.coefficient,[labels[x] for x in c.term],xerr=[c.coefficient-c.ci_lower,c.ci_upper-c.coefficient],fmt="o",c="#087F8C",capsize=4)
    ax.axvline(0,c="#9DAAB8",ls="--"); ax.set(xlabel="Log-odds coefficient (95% HC1 Wald interval)",title="Training-only logistic regression"); ax.grid(axis="x",alpha=.15)
    fig.savefig(out/"coefficient_intervals.png",dpi=160); plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(9,4),layout="constrained")
    for ax,name in zip(axs,["Logistic","Decision tree"]):
        row=metrics[(metrics.model==name)&(metrics.split=="test")].iloc[0]
        a=np.array([[row.tn,row.fp],[row.fn,row.tp]],dtype=int)
        ax.imshow(a,cmap="Blues")
        for (i,j),v in np.ndenumerate(a): ax.text(j,i,str(v),ha="center",va="center",color="white" if v>a.max()/2 else "#172B45",fontsize=18)
        ax.set_xticks([0,1],["Non-default","Default"]); ax.set_yticks([0,1],["Non-default","Default"])
        ax.set(xlabel="Predicted",ylabel="Observed",title=f"{name} · threshold {row.threshold:.2f}")
    fig.suptitle("Held-out confusion matrices",fontweight="bold")
    fig.savefig(out/"confusion_matrices.png",dpi=160); plt.close(fig)


def run(root=ROOT):
    generate_sources(root)
    data,audit,recon=prepare_data(root)
    train=data[data.split=="train"].copy(); valid=data[data.split=="validation"].copy(); test=data[data.split=="test"].copy()
    beta,coef,fit_diag=fit_logistic(train)
    coef.to_csv(root/"outputs/coefficients.csv",index=False)
    vif=vif_table(train); vif.to_csv(root/"outputs/vif.csv",index=False)
    log_t,log_grid=choose_threshold(valid.default_12m,predict_logistic(valid,beta))
    log_grid.assign(model="Logistic").to_csv(root/"outputs/threshold_search_logistic.csv",index=False)
    candidates=[]; trees=[]
    for depth in [2,3,4,5]:
        for leaf in [40,80,120]:
            tree=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=leaf,random_state=SEED)
            tree.fit(train[FEATURES],train.default_12m)
            p=tree.predict_proba(valid[FEATURES])[:,1]
            candidates.append({"max_depth":depth,"min_samples_leaf":leaf,"validation_roc_auc":roc_auc_score(valid.default_12m,p),"validation_brier":brier_score_loss(valid.default_12m,p)})
            trees.append(tree)
    # Max validation AUC; deterministic ties prefer shallower trees, then larger leaves.
    chosen=sorted(range(len(candidates)),key=lambda i:(-candidates[i]["validation_roc_auc"],candidates[i]["max_depth"],-candidates[i]["min_samples_leaf"]))[0]
    tree=trees[chosen]
    pd.DataFrame(candidates).to_csv(root/"outputs/tree_validation_search.csv",index=False)
    tree_t,tree_grid=choose_threshold(valid.default_12m,tree.predict_proba(valid[FEATURES])[:,1])
    tree_grid.assign(model="Decision tree").to_csv(root/"outputs/threshold_search_tree.csv",index=False)
    (root/"outputs/decision_tree_rules.txt").write_text(export_text(tree,feature_names=FEATURES,decimals=4),encoding="utf-8")
    allmetrics=[]
    for split,frame in [("train",train),("validation",valid),("test",test)]:
        for name,p,t in [("Logistic",predict_logistic(frame,beta),log_t),("Decision tree",tree.predict_proba(frame[FEATURES])[:,1],tree_t)]:
            allmetrics.append(metric_row(name,split,frame.default_12m,p,t))
    metrics=pd.DataFrame(allmetrics)
    metrics.to_csv(root/"outputs/model_metrics.csv",index=False)
    test["pd_logistic"]=predict_logistic(test,beta); test["pd_tree"]=tree.predict_proba(test[FEATURES])[:,1]
    test["risk_band"]=risk_band(test.pd_logistic)
    test["ecl_proxy_cny_m"]=test.debt_cny_m*LGD*test.pd_logistic
    test.to_csv(root/"outputs/test_predictions.csv",index=False)
    scenario_rows=[]; scenario_predictions=[]
    for name,shock in SCENARIOS.items():
        changed=stress_frame(test,shock); p=predict_logistic(changed,beta)
        scenario_rows.append({"scenario":name,"n":len(test),"mean_pd":float(p.mean()),
            "exposure_weighted_pd":float(np.average(p,weights=test.debt_cny_m)),
            "ead_proxy_cny_m":float(test.debt_cny_m.sum()),"lgd":LGD,
            "ecl_proxy_cny_m":float(np.sum(p*test.debt_cny_m*LGD)),"high_risk_count":int(np.sum(p>=.30)),**shock})
        scenario_predictions.append(pd.DataFrame({"borrower_id":test.borrower_id,"scenario":name,"pd":p,
            "ead_proxy_cny_m":test.debt_cny_m,"ecl_proxy_cny_m":p*test.debt_cny_m*LGD}))
    scenarios=pd.DataFrame(scenario_rows)
    scenarios["pd_change_pp"]=(scenarios.mean_pd-scenarios.mean_pd.iloc[0])*100
    scenarios["ecl_change_cny_m"]=scenarios.ecl_proxy_cny_m-scenarios.ecl_proxy_cny_m.iloc[0]
    scenarios.to_csv(root/"outputs/scenario_summary.csv",index=False)
    pd.concat(scenario_predictions).to_csv(root/"outputs/scenario_predictions.csv",index=False)
    support=[]
    for name,shock in SCENARIOS.items():
        changed=stress_frame(test,shock)
        for feature in FEATURES:
            low=float(train[feature].min()); high=float(train[feature].max())
            outside=(changed[feature]<low)|(changed[feature]>high)
            support.append({"scenario":name,"feature":feature,"training_min":low,"training_max":high,
                "outside_training_range_n":int(outside.sum()),"outside_training_range_share":float(outside.mean())})
    pd.DataFrame(support).to_csv(root/"outputs/scenario_support.csv",index=False)
    sector=test.groupby("sector",observed=True).agg(n=("borrower_id","size"),defaults=("default_12m","sum"),
        default_rate=("default_12m","mean"),mean_pd=("pd_logistic","mean"),ead_proxy_cny_m=("debt_cny_m","sum"),ecl_proxy_cny_m=("ecl_proxy_cny_m","sum")).reset_index()
    sector["exposure_weighted_pd"]=sector.ecl_proxy_cny_m/(LGD*sector.ead_proxy_cny_m)
    sector.to_csv(root/"outputs/sector_summary.csv",index=False)
    splits=data.groupby("split",sort=False).agg(n=("borrower_id","size"),defaults=("default_12m","sum"),
        default_rate=("default_12m","mean"),min_date=("snapshot_date","min"),max_date=("snapshot_date","max")).reset_index()
    splits.to_csv(root/"outputs/split_summary.csv",index=False)
    summary={"seed":SEED,"dataset":"Entirely synthetic independent borrowers and macro observations",
        "n_model_rows":len(data),"split_summary":splits.to_dict("records"),"features":FEATURES,
        "thresholds":{"Logistic":log_t,"Decision tree":tree_t},"selected_tree":candidates[chosen],
        "logistic_fit":fit_diag,"test_metrics":metrics[metrics.split=="test"].to_dict("records"),
        "scenarios":scenarios.to_dict("records"),"reconciliation":recon,"maximum_training_vif":float(vif.vif.max()),
        "lgd":LGD,"outcome_maturity":"2025-12-31","training_end":"2019-12-31",
        "validation_end":"2021-12-31","test_end":"2024-12-31",
        "embargo_years":[2020,2022],"model_fit_asof":"2021-01-01","selection_asof":"2023-01-01"}
    json_save(root/"outputs/metrics.json",summary)
    params={"features":FEATURES,"terms":TERMS,"coefficients":dict(zip(TERMS,map(float,beta))),
        "threshold":log_t,"risk_bands":{"Low":"0 <= p < 0.05","Moderate":"0.05 <= p < 0.15","Elevated":"0.15 <= p < 0.30","High":"0.30 <= p <= 1"},
        "scenarios":SCENARIOS,"lgd":LGD,"fitted_on":"train only; no refit after validation"}
    json_save(root/"outputs/model_parameters.json",params)
    json_save(root/"outputs/workbook_data.json",{"summary":summary,"coefficients":coef.to_dict("records"),
        "metrics":metrics.to_dict("records"),"test_predictions":test.to_dict("records"),
        "scenarios":scenarios.to_dict("records"),"sectors":sector.to_dict("records"),"audit":audit.to_dict("records"),"vif":vif.to_dict("records")})
    build_charts(root,test,metrics,coef,scenarios)
    # Portable validation tables for third-party cross-tool comparisons.
    valid.assign(pd_logistic=predict_logistic(valid,beta)).to_csv(root/"outputs/validation_predictions.csv",index=False)
    calibration=[]
    for name,col in [("Logistic","pd_logistic"),("Decision tree","pd_tree")]:
        group=pd.qcut(test[col],q=8,duplicates="drop")
        for interval,g in test.groupby(group,observed=True):
            calibration.append({"model":name,"bin":str(interval),"n":len(g),"mean_pd":float(g[col].mean()),"observed_default_rate":float(g.default_12m.mean())})
    pd.DataFrame(calibration).to_csv(root/"outputs/calibration_bins.csv",index=False)
    import scipy, sklearn
    json_save(root/"outputs/run_environment.json",{"python":platform.python_version(),"numpy":np.__version__,"pandas":pd.__version__,
        "scipy":scipy.__version__,"scikit_learn":sklearn.__version__,"matplotlib":matplotlib.__version__,
        "note":"Executed reference implementation; R, SAS and Excel native feature execution are documented separately."})
    print(json.dumps({"model_rows":len(data),"test_metrics":summary["test_metrics"],"scenarios":summary["scenarios"]},indent=2))


if __name__=="__main__":
    run()
