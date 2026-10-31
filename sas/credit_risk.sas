/* Synthetic corporate-credit portfolio: independent SAS/STAT replication.
   Set ROOT to the repository directory on your SAS host, including when using
   SAS Studio. Forward slashes work for SAS on Windows as well as Linux.
   Requires Base SAS and SAS/STAT. This script was not executed during creation.
   It fits logistic regression only; the Python pipeline owns the tree benchmark.
*/
%let root=/absolute/path/to/corporate-credit-risk-analytics;
%let outdir=&root./outputs/sas;
options nodate nonumber;

/* The outputs parent is created by the Python pipeline. Create its sas child. */
data _null_;
  length target $1024;
  target=dcreate('sas', "&root./outputs");
run;
libname result "&outdir.";
ods html path="&outdir." (url=none) file="analysis.html" style=HTMLBlue;
title 'Synthetic credit risk: independent SAS logistic replication';

proc import datafile="&root./data/processed/model_data.csv"
    out=work.model_data dbms=csv replace;
  guessingrows=max;
run;

/* Reject incomplete model rows rather than silently changing the sample. */
data _null_;
  set work.model_data;
  if cmiss(borrower_id, split, leverage, dscr, interest_rate_pct,
           gdp_growth_pct, past_due_30d, default_12m, debt_cny_m)>0
      or default_12m not in (0,1)
      or split not in ('train','validation','test','embargo') then do;
    put 'ERROR: Invalid input record at row ' _n_;
    abort cancel;
  end;
run;
proc sql noprint;
  select count(*)-count(distinct borrower_id) into :duplicates trimmed
  from work.model_data;
quit;
%macro reject_duplicate;
  %if &duplicates. ne 0 %then %do;
    %put ERROR: Duplicate borrower_id values in the input data.;
    %abort cancel;
  %end;
%mend;
%reject_duplicate;

data work.train work.validation work.test;
  set work.model_data;
  if split='train' then output work.train;
  else if split='validation' then output work.validation;
  else if split='test' then output work.test;
  /* Embargo years are intentionally excluded. */
run;

/* EVENT='1' makes P_1 the default probability. No class weighting, oversampling,
   standardization, regularization, variable selection or held-out refitting. */
ods output ParameterEstimates=result.parameter_estimates
           ConvergenceStatus=result.convergence;
proc logistic data=work.train outmodel=result.logistic_model
              outest=work.logistic_estimates;
  model default_12m(event='1') = leverage dscr interest_rate_pct
    gdp_growth_pct past_due_30d / clodds=wald gconv=1e-10 maxiter=100;
  score data=work.validation out=work.validation_scored;
  score data=work.test out=work.test_scored fitstat;
run;

/* Stop if the optimizer did not converge; success must not be inferred from
   the presence of an ODS table. SAS reports zero for successful convergence. */
data _null_;
  set result.convergence;
  if Status ne 0 then do;
    put 'ERROR: Logistic fitting failed to converge.';
    abort cancel;
  end;
run;

data result.logistic_coefficients;
  set work.logistic_estimates;
  where _TYPE_='PARMS';
  length term $32;
  array estimates[6] Intercept leverage dscr interest_rate_pct
                     gdp_growth_pct past_due_30d;
  array terms[6] $32 _temporary_ ('intercept' 'leverage' 'dscr'
                     'interest_rate_pct' 'gdp_growth_pct' 'past_due_30d');
  do i=1 to dim(estimates);
    term=terms[i]; coefficient=estimates[i]; output;
  end;
  keep term coefficient;
run;

/* VIF measures dependence among predictor columns. PROC REG's target is used
   only to expose its design-matrix diagnostics; it is not a default model. */
title 'Training design-matrix multicollinearity diagnostics';
ods output ParameterEstimates=result.vif_diagnostics;
proc reg data=work.train;
  model default_12m = leverage dscr interest_rate_pct
        gdp_growth_pct past_due_30d / vif;
run;
quit;

/* Validation-only threshold grid. The largest threshold wins exact F1 ties. */
data work.threshold_long;
  set work.validation_scored;
  do grid=1 to 80;
    threshold=grid/100;
    tp=(P_1>=threshold and default_12m=1);
    fp=(P_1>=threshold and default_12m=0);
    fn=(P_1<threshold and default_12m=1);
    output;
  end;
run;
proc sql;
  create table work.threshold_totals as
  select threshold, sum(tp) as tp, sum(fp) as fp, sum(fn) as fn
  from work.threshold_long group by threshold;
quit;
data result.threshold_search;
  set work.threshold_totals;
  if 2*tp+fp+fn>0 then validation_f1=2*tp/(2*tp+fp+fn);
  else validation_f1=0;
run;
proc sort data=result.threshold_search out=work.threshold_order;
  by descending validation_f1 descending threshold;
run;
data _null_;
  set work.threshold_order(obs=1);
  call symputx('threshold',threshold,'G');
run;

data result.predictions;
  set work.test_scored;
  pd_logistic=P_1;
  keep borrower_id pd_logistic;
run;

/* Rank-based test AUC handles tied predicted probabilities exactly. */
proc rank data=work.test_scored out=work.test_ranked ties=mean;
  var P_1;
  ranks pd_rank;
run;
proc sql;
  create table work.test_stats as
  select count(*) as n, sum(default_12m=1) as positives,
    sum(default_12m=0) as negatives,
    sum(case when default_12m=1 then pd_rank else 0 end) as positive_rank_sum,
    mean((P_1-default_12m)**2) as brier, mean(P_1) as mean_pd,
    mean(default_12m) as observed_default_rate,
    sum(P_1>=&threshold. and default_12m=1) as tp,
    sum(P_1>=&threshold. and default_12m=0) as fp,
    sum(P_1<&threshold. and default_12m=1) as fn,
    sum(P_1<&threshold. and default_12m=0) as tn
  from work.test_ranked;
quit;
data result.model_metrics;
  set work.test_stats;
  length model $12 split $12;
  model='logistic'; split='test'; threshold=&threshold.;
  if positives=0 or negatives=0 then do;
    put 'ERROR: AUC requires both outcomes in test.'; abort cancel;
  end;
  roc_auc=(positive_rank_sum-positives*(positives+1)/2)/(positives*negatives);
  if 2*tp+fp+fn>0 then f1=2*tp/(2*tp+fp+fn); else f1=0;
  drop positive_rank_sum;
run;

/* Conditional sensitivity: the frozen test cohort and debt exposure stay fixed.
   Macroeconomic shocks are illustrative assumptions, not a regulatory stress. */
data work.scenario_inputs;
  set work.test;
  length scenario $8;
  orig_leverage=leverage; orig_dscr=dscr;
  orig_rate=interest_rate_pct; orig_gdp=gdp_growth_pct;
  scenario='base'; output;
  scenario='adverse';
  leverage=min(1,max(0,orig_leverage+.05)); dscr=orig_dscr*.85;
  interest_rate_pct=orig_rate+1; gdp_growth_pct=orig_gdp-2;
  output;
  scenario='severe';
  leverage=min(1,max(0,orig_leverage+.10)); dscr=orig_dscr*.70;
  interest_rate_pct=orig_rate+2; gdp_growth_pct=orig_gdp-4;
  output;
  drop orig_:;
run;
proc logistic inmodel=result.logistic_model;
  score data=work.scenario_inputs out=work.scenario_scored;
run;
proc sql;
  create table result.scenario_summary as
  select scenario, count(*) as borrowers, mean(P_1) as mean_pd,
    sum(debt_cny_m*P_1)/sum(debt_cny_m) as debt_weighted_pd,
    sum(debt_cny_m) as ead_proxy_cny_m, .45 as lgd,
    sum(debt_cny_m*P_1*.45) as ecl_proxy_cny_m
  from work.scenario_scored group by scenario;
quit;

%macro export(dataset,filename);
  proc export data=result.&dataset.
    outfile="&outdir./&filename..csv" dbms=csv replace;
  run;
%mend;
%export(logistic_coefficients,logistic_coefficients);
%export(predictions,predictions);
%export(model_metrics,model_metrics);
%export(threshold_search,threshold_search);
%export(scenario_summary,scenario_summary);
%export(parameter_estimates,parameter_estimates_model_based_se);
%export(vif_diagnostics,vif_diagnostics);
title;
ods html close;
/* After successful execution, from the repository root:
   python r/compare_outputs.py --engine sas
   SAS's default SEs above are model-based, not the Python/R HC1 SEs.
*/
