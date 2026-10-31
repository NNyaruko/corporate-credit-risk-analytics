#!/usr/bin/env Rscript
# Independent replication using base R. Synthetic portfolio only.
# From the repository root: Rscript r/credit_risk.R
# Optional first argument: absolute repository path.
args <- commandArgs(trailingOnly = TRUE)
root <- if (length(args)) normalizePath(args[1], mustWork = TRUE) else getwd()
out <- file.path(root, "outputs", "r")
dir.create(out, recursive = TRUE, showWarnings = FALSE)
options(stringsAsFactors = FALSE, digits = 16)
d <- read.csv(file.path(root, "data", "processed", "model_data.csv"),
              check.names = FALSE)
features <- c("leverage", "dscr", "interest_rate_pct", "gdp_growth_pct", "past_due_30d")
required <- c("borrower_id", "snapshot_date", features, "default_12m", "split", "debt_cny_m")
stopifnot(all(required %in% names(d)), !anyDuplicated(d$borrower_id),
          all(complete.cases(d[, required])), all(d$default_12m %in% c(0, 1)),
          all(d$split %in% c("train", "validation", "test", "embargo")))
d$snapshot_date <- as.Date(d$snapshot_date)
train <- d[d$split == "train", ]
validation <- d[d$split == "validation", ]
test <- d[d$split == "test", ]
stopifnot(nrow(train) > 0, nrow(validation) > 0, nrow(test) > 0,
          max(train$snapshot_date) < min(validation$snapshot_date),
          max(validation$snapshot_date) < min(test$snapshot_date),
          length(unique(train$default_12m)) == 2,
          length(unique(validation$default_12m)) == 2,
          length(unique(test$default_12m)) == 2)

# No feature scaling, selection, imputation, or refitting on validation/test.
formula <- reformulate(features, response = "default_12m")
fit <- glm(formula, data = train, family = binomial(link = "logit"),
           na.action = na.fail, x = TRUE, y = TRUE, singular.ok = FALSE,
           control = glm.control(epsilon = 1e-12, maxit = 100))
stopifnot(fit$converged, all(is.finite(coef(fit))))
X <- fit$x
prob <- fitted(fit)
n <- nrow(X)
k <- ncol(X)
# HC1 sandwich: n/(n-k) H^-1 (sum_i score_i score_i') H^-1.
# Independent-observation robust SE; this is not a clustered macro-panel model.
H <- crossprod(X, X * as.vector(prob * (1 - prob)))
scores <- X * as.vector(fit$y - prob)
Hinv <- solve(H)
V <- (n / (n - k)) * Hinv %*% crossprod(scores) %*% Hinv
se <- sqrt(diag(V))
b <- coef(fit)
z <- b / se
terms <- names(b)
terms[terms == "(Intercept)"] <- "intercept"
coefficients <- data.frame(term = terms, coefficient = as.vector(b),
  std_error = se, z = z, p_value = 2 * pnorm(-abs(z)),
  ci_lower = b - qnorm(.975) * se, ci_upper = b + qnorm(.975) * se,
  odds_ratio = exp(b), row.names = NULL)
write.csv(coefficients, file.path(out, "logistic_coefficients.csv"), row.names = FALSE)

vif <- sapply(features, function(target) {
  aux <- lm(reformulate(setdiff(features, target), response = target), data = train)
  1 / (1 - summary(aux)$r.squared)
})
write.csv(data.frame(feature = names(vif), vif = unname(vif)),
          file.path(out, "vif.csv"), row.names = FALSE)

auc <- function(y, p) {
  n1 <- sum(y == 1); n0 <- sum(y == 0)
  stopifnot(n1 > 0, n0 > 0)
  (sum(rank(p, ties.method = "average")[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}
counts <- function(y, p, threshold) {
  predicted <- p >= threshold
  c(tn = sum(!predicted & y == 0), fp = sum(predicted & y == 0),
    fn = sum(!predicted & y == 1), tp = sum(predicted & y == 1))
}
f1_at <- function(y, p, threshold) {
  q <- counts(y, p, threshold)
  denominator <- 2 * q["tp"] + q["fp"] + q["fn"]
  if (denominator == 0) 0 else unname(2 * q["tp"] / denominator)
}
p_validation <- predict(fit, newdata = validation, type = "response")
thresholds <- (1:80) / 100
f1_values <- vapply(thresholds, function(t) f1_at(validation$default_12m, p_validation, t), 0.0)
# Same fixed grid as Python; the largest threshold wins an exact F1 tie.
threshold <- thresholds[tail(which(f1_values == max(f1_values)), 1)]
write.csv(data.frame(threshold = thresholds, validation_f1 = f1_values),
          file.path(out, "threshold_search.csv"), row.names = FALSE)

metrics <- function(part, p, split) {
  q <- counts(part$default_12m, p, threshold)
  data.frame(model = "logistic", split = split, n = nrow(part),
    roc_auc = auc(part$default_12m, p), brier = mean((p - part$default_12m)^2),
    observed_default_rate = mean(part$default_12m), mean_pd = mean(p), threshold = threshold,
    tn = q["tn"], fp = q["fp"], fn = q["fn"], tp = q["tp"],
    f1 = f1_at(part$default_12m, p, threshold), row.names = NULL)
}
p_test <- predict(fit, newdata = test, type = "response")
stopifnot(all(is.finite(p_test)), all(p_test > 0 & p_test < 1))
write.csv(rbind(metrics(validation, p_validation, "validation"), metrics(test, p_test, "test")),
          file.path(out, "model_metrics.csv"), row.names = FALSE)
write.csv(data.frame(borrower_id = test$borrower_id, pd_logistic = unname(p_test)),
          file.path(out, "predictions.csv"), row.names = FALSE)

# Same frozen test population and exposure proxy for every conditional scenario.
# Rate and GDP shocks are percentage points; leverage is a proportion.
scenarios <- data.frame(scenario = c("base", "adverse", "severe"),
  leverage_add = c(0, .05, .10), dscr_factor = c(1, .85, .70),
  rate_add_pp = c(0, 1, 2), gdp_add_pp = c(0, -2, -4))
scenario_results <- lapply(seq_len(nrow(scenarios)), function(i) {
  s <- scenarios[i, ]; stressed <- test
  stressed$leverage <- pmin(1, pmax(0, stressed$leverage + s$leverage_add))
  stressed$dscr <- stressed$dscr * s$dscr_factor
  stressed$interest_rate_pct <- stressed$interest_rate_pct + s$rate_add_pp
  stressed$gdp_growth_pct <- stressed$gdp_growth_pct + s$gdp_add_pp
  pd <- predict(fit, newdata = stressed, type = "response")
  data.frame(scenario = s$scenario, borrowers = nrow(test), mean_pd = mean(pd),
    debt_weighted_pd = weighted.mean(pd, test$debt_cny_m),
    ead_proxy_cny_m = sum(test$debt_cny_m), lgd = .45,
    ecl_proxy_cny_m = sum(test$debt_cny_m * pd * .45))
})
write.csv(do.call(rbind, scenario_results), file.path(out, "scenario_summary.csv"), row.names = FALSE)
capture.output(sessionInfo(), file = file.path(out, "sessionInfo.txt"))
cat("R outputs written to", out, "\n")
cat("Run: python r/compare_outputs.py --engine r\n")
