"""Independent checks of modeling, reconciliation and temporal integrity.

Run after python -m src.pipeline with: python -m unittest discover -s tests -v
"""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression

from src.pipeline import (ROOT, FEATURES, TERMS, SCENARIOS, LGD, choose_threshold,
                          design, fit_logistic, predict_logistic, prepare_data,
                          risk_band, stress_frame)


class CreditPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=pd.read_csv(ROOT/"data/processed/model_data.csv")
        cls.train=cls.data[cls.data.split=="train"].copy()
        cls.valid=cls.data[cls.data.split=="validation"].copy()
        cls.test=pd.read_csv(ROOT/"outputs/test_predictions.csv")
        cls.metrics=pd.read_csv(ROOT/"outputs/model_metrics.csv")
        cls.params=json.loads((ROOT/"outputs/model_parameters.json").read_text())
        cls.beta=np.array([cls.params["coefficients"][k] for k in TERMS])

    def test_temporal_maturity_and_disjoint_borrowers(self):
        self.assertTrue(self.data.borrower_id.is_unique)
        self.assertEqual(set(self.train.snapshot_date.str[:4]),{"2017","2018","2019"})
        embargo=self.data[self.data.split=="embargo"]
        self.assertEqual(set(embargo.snapshot_date.str[:4]),{"2020","2022"})
        self.assertEqual(set(self.valid.snapshot_date.str[:4]),{"2021"})
        self.assertEqual(set(self.test.snapshot_date.str[:4]),{"2023","2024"})
        self.assertLess(pd.to_datetime(self.train.snapshot_date).max()+pd.DateOffset(years=1),pd.to_datetime(self.valid.snapshot_date).min())
        self.assertLess(pd.to_datetime(self.valid.snapshot_date).max()+pd.DateOffset(years=1),pd.to_datetime(self.test.snapshot_date).min())
        self.assertLessEqual(pd.to_datetime(self.test.snapshot_date).max()+pd.DateOffset(years=1),pd.Timestamp("2025-12-31"))
        for a,b in [(self.train,self.valid),(self.train,self.test),(self.valid,self.test)]:
            self.assertTrue(set(a.borrower_id).isdisjoint(b.borrower_id))

    def test_reconciliation_preserves_source_exposure(self):
        r=json.loads((ROOT/"outputs/reconciliation.json").read_text())
        self.assertEqual(r["raw_rows"]-r["exact_duplicate_rows"]-r["excluded_incomplete"],len(self.data))
        self.assertEqual((r["raw_rows"],r["exact_duplicate_rows"],r["excluded_incomplete"]),(6401,1,2))
        self.assertAlmostEqual(r["unique_debt_cny_m"]-r["excluded_debt_cny_m"],self.data.debt_cny_m.sum(),places=6)
        self.assertTrue(np.allclose(self.data.leverage,self.data.debt_cny_m/self.data.total_assets_cny_m))
        self.assertTrue(np.allclose(self.data.dscr,self.data.ebitda_cny_m/self.data.debt_service_cny_m))

    def test_logistic_matches_independent_sklearn_solver(self):
        model=LogisticRegression(C=np.inf,solver="newton-cholesky",tol=1e-10,max_iter=300)
        model.fit(self.train[FEATURES],self.train.default_12m)
        other=np.r_[model.intercept_,model.coef_[0]]
        np.testing.assert_allclose(other,self.beta,rtol=1e-6,atol=1e-6)
        np.testing.assert_allclose(model.predict_proba(self.test[FEATURES])[:,1],self.test.pd_logistic,rtol=1e-6,atol=1e-7)

    def test_mle_score_and_covariance(self):
        beta,coef,diag=fit_logistic(self.train)
        X=design(self.train); y=self.train.default_12m.to_numpy(); p=expit(X@beta)
        self.assertLess(np.abs(X.T@(y-p)).max(),1e-5)
        self.assertTrue(diag["optimizer_success"])
        self.assertGreater(diag["minimum_hessian_eigenvalue"],0)
        # Recompute HC1 from a direct outer-product sum, independently of the vectorized code.
        H=X.T@np.diag(p*(1-p))@X
        scores=[np.outer(x*(yi-pi),x*(yi-pi)) for x,yi,pi in zip(X,y,p)]
        inv=np.linalg.inv(H)
        cov=len(y)/(len(y)-X.shape[1])*inv@sum(scores)@inv
        np.testing.assert_allclose(np.sqrt(np.diag(cov)),coef.std_error,rtol=1e-9)

    def test_predictors_exclude_outcomes_and_require_no_fitted_preprocessing(self):
        self.assertNotIn("default_12m",FEATURES)
        self.assertNotIn("split",FEATURES)
        self.assertNotIn("snapshot_date",FEATURES)
        changed=self.test.copy()
        changed["default_12m"]=1-changed.default_12m
        np.testing.assert_array_equal(design(self.test),design(changed))
        np.testing.assert_allclose(predict_logistic(changed,self.beta),self.test.pd_logistic,atol=1e-14)
        self.assertFalse(self.data[FEATURES].isna().any().any())
        self.assertTrue(np.isfinite(self.data[FEATURES]).all().all())

    def test_threshold_selected_only_from_validation(self):
        valid=pd.read_csv(ROOT/"outputs/validation_predictions.csv")
        threshold,_=choose_threshold(valid.default_12m,valid.pd_logistic)
        self.assertEqual(threshold,self.params["threshold"])
        # All thresholds <=0.4 give the same perfect classification; highest wins.
        threshold,_=choose_threshold(np.array([0,0,1,1]),np.array([0,0,.4,.4]))
        self.assertEqual(threshold,.4)

    def test_auc_independent_rank_formula_and_confusion_totals(self):
        for name,col in [("Logistic","pd_logistic"),("Decision tree","pd_tree")]:
            y=self.test.default_12m.to_numpy(); p=self.test[col].to_numpy()
            n1=y.sum(); n0=len(y)-n1
            auc=(rankdata(p)[y==1].sum()-n1*(n1+1)/2)/(n1*n0)
            row=self.metrics[(self.metrics.model==name)&(self.metrics.split=="test")].iloc[0]
            self.assertAlmostEqual(auc,row.roc_auc,places=12)
            pred=p>=row.threshold
            self.assertEqual(row.tp,int(np.sum(pred&(y==1))))
            self.assertEqual(row.fp,int(np.sum(pred&(y==0))))
            self.assertEqual(row.tn,int(np.sum(~pred&(y==0))))
            self.assertEqual(row.fn,int(np.sum(~pred&(y==1))))
            self.assertEqual(row.tp+row.fp+row.tn+row.fn,len(y))
            self.assertAlmostEqual(np.mean((y-p)**2),row.brier_score,places=12)

    def test_scenario_shocks_preserve_cohort_and_ead(self):
        scenario=pd.read_csv(ROOT/"outputs/scenario_summary.csv")
        for name,shock in SCENARIOS.items():
            changed=stress_frame(self.test,shock)
            self.assertTrue(changed.borrower_id.equals(self.test.borrower_id))
            np.testing.assert_array_equal(changed.debt_cny_m,self.test.debt_cny_m)
            np.testing.assert_array_equal(changed.past_due_30d,self.test.past_due_30d)
            p=predict_logistic(changed,self.beta)
            row=scenario[scenario.scenario==name].iloc[0]
            self.assertAlmostEqual(p.mean(),row.mean_pd,places=12)
            self.assertAlmostEqual(np.sum(p*changed.debt_cny_m*LGD),row.ecl_proxy_cny_m,places=7)
            if name=="Base": np.testing.assert_allclose(p,self.test.pd_logistic,atol=1e-14)
        upper=self.test.iloc[[0]].copy(); upper["leverage"]=.99
        self.assertEqual(stress_frame(upper,SCENARIOS["Severe"]).leverage.iloc[0],1)

    def test_risk_band_boundaries(self):
        values=pd.Series([0,.04999,.05,.14999,.15,.29999,.30,1])
        self.assertEqual(list(risk_band(values)),["Low","Low","Moderate","Moderate","Elevated","Elevated","High","High"])

    def test_conflicting_keys_fail_instead_of_silent_deduplication(self):
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td); raw=temp/"data/raw"; raw.mkdir(parents=True)
            for name in ["financials.csv","repayments.csv","macro.csv"]:
                table=pd.read_csv(ROOT/"data/raw"/name)
                if name=="financials.csv": table.loc[len(table)-1,"revenue_cny_m"]+=1
                table.to_csv(raw/name,index=False)
            with self.assertRaisesRegex(ValueError,"Conflicting duplicate keys"):
                prepare_data(temp)


if __name__=="__main__":
    unittest.main()
