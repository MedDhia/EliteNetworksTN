# Build a TERGM-estimable panel for the Tunisian elite network, 2008-2012.
#
# This is NOT the same object as R/build_networkdynamic.R, which stays as the
# descriptive path for tsna. A networkDynamic is a continuous-time object; a
# TERGM wants a discrete list of network objects, one per period, and several
# things a networkDynamic does not carry.
#
#   Rscript R/build_tergm_panel.R [--sample N] [--all-ties]
#
#     --sample N   build on the N highest-degree persons and the organisations
#                  they touch, for a fast structural smoke test
#     --R N        bootstrap replications (default 200)
#     --all-ties   include ambiguous and probable/possible ties (default is
#                  resolved + certain only; see the certainty sensitivity in
#                  docs/TERGM-multiplex-2008-2012.md)
#
# Three design decisions are worth knowing before reading the code.
#
# 1. The risk set is expressed by REMOVING each period's inactive
#    organisations from that period's network and estimating with
#    `offset = TRUE`. This is btergm's own mechanism, and it is worth being
#    explicit that it is the opposite of what it sounds like: `offset = TRUE`
#    does not mean "I supplied an offset term". It means btergm builds the
#    structural-zero matrices itself from the nodes that are *absent* in a
#    period, inflates every object to the largest, and drops those dyads
#    before the pseudolikelihood GLM.
#
#    An earlier version of this script kept the vertex set constant and passed
#    `offset(edgecov(risk))` in the formula, reasoning that a moving vertex set
#    makes `memory()` depend on how btergm matches vertices. That reasoning was
#    sound and the code did not work: tergmprepare() rejects it. Trimming is
#    the supported path, and `network` does correctly adjust the bipartite
#    count when mode-2 vertices are deleted, so the mode split survives.
#
# 2. Dyadic covariates are stored on disk as sparse triplets and densified
#    here, one matrix per covariate per period. At the full universe that is
#    2592 x 2915 integers, about 30 MB each; four covariates over five periods
#    is roughly 600 MB of R memory. Use --sample to work smaller.
#
#    Every covariate matrix carries dimnames -- person node_ids by organisation
#    node_ids. This is not cosmetic. Because the networks are trimmed per
#    period while the covariates span the full universe, btergm aligns them by
#    name; strip the dimnames and tergmprepare() fails.
#
# 3. Only bipartite-valid terms appear in the worked model. `triangle` and
#    `gwesp` count structures that cannot exist in a two-mode network; the
#    two-mode analogues are gwb1degree/gwb2degree, b1star/b2star and cycle(4).

suppressPackageStartupMessages(library(network))

args <- commandArgs(trailingOnly = TRUE)
sample_n <- if ("--sample" %in% args) {
  as.integer(args[which(args == "--sample") + 1L])
} else NA_integer_
all_ties <- "--all-ties" %in% args
R_boot <- if ("--R" %in% args) as.integer(args[which(args == "--R") + 1L]) else 200L

base <- file.path("data", "processed", "multiplex-2008-2012", "exports", "tergm")
rd <- function(f) read.csv(file.path(base, f), stringsAsFactors = FALSE,
                           encoding = "UTF-8")

node_key <- rd("node_key.csv")
edges    <- rd("edges_yearly.csv")
activity <- rd("vertex_activity_yearly.csv")
attrs    <- rd("node_attrs_yearly.csv")
dyads    <- rd("dyad_cov_yearly.csv")

periods <- sort(unique(edges$period))

# --- tie sample -------------------------------------------------------------
# A TERGM treats a tie as certain. 1,527 probable and 323 possible ties, and
# 2,797 whose person could not be pinned to one identity, are therefore excluded
# by default rather than quietly asserted.
if (!all_ties) {
  keep <- edges$link_status == "resolved" & edges$certainty == "certain"
  cat(sprintf("tie sample: resolved + certain, %d of %d ties\n",
              sum(keep), nrow(edges)))
  edges <- edges[keep, ]
} else {
  cat(sprintf("tie sample: ALL %d ties (ambiguous and uncertain included)\n",
              nrow(edges)))
}

# --- optional smoke subset --------------------------------------------------
if (!is.na(sample_n)) {
  deg <- sort(table(edges$tail), decreasing = TRUE)
  keep_p <- as.integer(names(deg)[seq_len(min(sample_n, length(deg)))])
  edges <- edges[edges$tail %in% keep_p, ]
  keep_o <- sort(unique(edges$head))
  node_key <- node_key[node_key$vertex_id %in% c(keep_p, keep_o), ]
  cat(sprintf("smoke subset: %d persons, %d organisations, %d ties\n",
              length(keep_p), length(keep_o), nrow(edges)))
}

# --- re-index to a contiguous mode-blocked 1..n ------------------------------
# Subsetting leaves gaps in vertex_id. A bipartite network object requires all
# mode-1 vertices to occupy 1..n1, so the ids are compacted here, preserving the
# mode block order that the exporter guarantees.
node_key <- node_key[order(node_key$mode, node_key$vertex_id), ]
n1 <- sum(node_key$mode == 1L)
n  <- nrow(node_key)
stopifnot(n1 > 0, n > n1)
new_id <- setNames(seq_len(n), as.character(node_key$vertex_id))
remap <- function(v) unname(new_id[as.character(v)])

edges$tail_i <- remap(edges$tail)
edges$head_i <- remap(edges$head)
stopifnot(all(edges$tail_i <= n1), all(edges$head_i > n1))

n2 <- n - n1
cat(sprintf("vertices: %d persons (mode 1) + %d organisations (mode 2)\n", n1, n2))

# --- per-period networks ----------------------------------------------------
attrs  <- attrs[!is.na(remap(attrs$vertex_id)), ]
activity <- activity[!is.na(remap(activity$vertex_id)), ]

nets <- list()
for (p in periods) {
  net <- network.initialize(n, bipartite = n1, directed = FALSE)
  network.vertex.names(net) <- node_key$node_id

  e <- edges[edges$period == p, ]
  if (nrow(e)) add.edges(net, e$tail_i, e$head_i)

  a <- attrs[attrs$period == p, ]
  a <- a[match(node_key$vertex_id, a$vertex_id), ]
  set.vertex.attribute(net, "node_type",     a$node_type)
  set.vertex.attribute(net, "is_seed",       as.integer(a$is_seed))
  set.vertex.attribute(net, "seed_degree",   as.numeric(a$seed_degree))
  set.vertex.attribute(net, "kin_degree",    as.numeric(a$kin_degree))
  set.vertex.attribute(net, "ped_degree",    as.numeric(a$pedagogic_degree))
  # The LAGGED degree, not the contemporaneous one: a covariate measured at t
  # is a function of the very ties being modelled at t.
  set.vertex.attribute(net, "cum_degree_lag", as.numeric(a$cum_degree_lag))
  set.vertex.attribute(net, "label_suspect",
                       as.integer(node_key$label_suspect))

  nets[[as.character(p)]] <- net
}

# --- the risk set: trim each period to its active vertices -------------------
# Every person is at risk in every period (the gazette records appointments,
# not births), so what gets removed is exactly the organisations outside their
# own lifecycle. Deleting mode-2 vertices leaves the bipartite count correct,
# which is asserted below rather than assumed.
nets_full <- nets
trimmed <- list()
dropped <- integer(0)
for (i in seq_along(periods)) {
  p <- periods[i]
  net <- nets[[as.character(p)]]
  a <- activity[activity$period == p, ]
  a <- a[match(node_key$vertex_id, a$vertex_id), ]
  drop <- which(a$active == 0L)
  if (length(drop)) delete.vertices(net, drop)
  dropped[as.character(p)] <- length(drop)
  trimmed[[as.character(p)]] <- net
}

# --- dyadic covariates ------------------------------------------------------
# kin_in_org, owner_of and prior_comembership are lagged to t-1 by
# construction, which is what keeps them exogenous to the tie being modelled;
# they are all zero in period 1, which has no lag. is_shareholder is read from
# the undated seed sheet, so it is exogenous without a lag and is populated in
# every period, period 1 included.
#
# Built on the FULL universe and carrying dimnames, so btergm can align them
# against the trimmed networks by name.
pnames <- node_key$node_id[node_key$mode == 1L]
onames <- node_key$node_id[node_key$mode == 2L]
densify <- function(field, p) {
  m <- matrix(0L, nrow = n1, ncol = n2, dimnames = list(pnames, onames))
  d <- dyads[dyads$period == p & dyads[[field]] == 1L, ]
  if (nrow(d)) {
    ti <- remap(d$tail); hi <- remap(d$head)
    ok <- !is.na(ti) & !is.na(hi)
    if (any(ok)) m[cbind(ti[ok], hi[ok] - n1)] <- 1L
  }
  m
}
cov_fields <- c("kin_in_org", "owner_of", "prior_comembership",
                "is_shareholder")
dyad_cov <- list()
for (p in periods) {
  dyad_cov[[as.character(p)]] <- lapply(setNames(cov_fields, cov_fields),
                                        densify, p = p)
}

# --- structural report ------------------------------------------------------
cat("\nper-period structure (full universe -> trimmed to the risk set):\n")
for (p in periods) {
  f <- nets_full[[as.character(p)]]; tn <- trimmed[[as.character(p)]]
  cat(sprintf("  %s  size %4d -> %4d  (%4d organisations not yet or no longer "
              , p, network.size(f), network.size(tn), dropped[[as.character(p)]]))
  cat(sprintf("extant)  bipartite %s  edges %5d\n",
              ifelse(is.bipartite(tn), as.character(tn %n% "bipartite"), "NO"),
              network.edgecount(tn)))
}
stopifnot(all(vapply(trimmed, is.bipartite, logical(1))))
# Only mode-2 vertices are ever removed, so the person block is untouched.
stopifnot(all(vapply(trimmed, function(x) x %n% "bipartite", numeric(1)) == n1))
stopifnot(all(vapply(nets_full, network.size, numeric(1)) == n))

out <- file.path(base, if (is.na(sample_n) && !all_ties) "tergm_panel.rds"
                       else sprintf("tergm_panel_%s%s.rds",
                                    if (is.na(sample_n)) "full" else
                                      paste0("sample", sample_n),
                                    if (all_ties) "_allties" else ""))
saveRDS(list(networks = trimmed, networks_full = nets_full,
             dyad_cov = dyad_cov, node_key = node_key, activity = activity,
             n1 = n1, n2 = n2, periods = periods),
        out)
cat("\nsaved", out, "\n")

# --- worked model: FORMATION ONLY -------------------------------------------
# 82% of dated spells are right-censored, because the gazette publishes
# arrivals far more reliably than departures. A dissolution or persistence
# parameter fitted here would describe when an exit gets *printed*, not when a
# tie ends, so this specification models formation and does not interpret the
# other side. memory("stability") is a nuisance control, not a finding. Read
# docs/TERGM-multiplex-2008-2012.md before changing that.
#
# Period 1 is consumed by the lag, so estimation runs on periods 2..T.
if (!requireNamespace("btergm", quietly = TRUE)) {
  cat("\nbtergm is not installed; the panel above is built and saved.\n",
      "install.packages(\"btergm\") and re-run to estimate.\n", sep = "")
} else {
  suppressPackageStartupMessages(library(btergm))
  # ALL periods are handed over, not periods 2..T. memory() takes its lag from
  # the previous element of the list it is given, so slicing the first period
  # off here would cost a transition: 2008 is consumed as the lag for 2009
  # rather than being modelled. The covariate list is sliced the same way by
  # btergm, and each period's matrices are already lagged to t-1, so outcome
  # year t is paired with covariates measured at t-1 as intended.
  ix <- seq_along(trimmed)
  dc <- dyad_cov[ix]
  kin <- lapply(dc, `[[`, "kin_in_org")
  own <- lapply(dc, `[[`, "owner_of")
  com <- lapply(dc, `[[`, "prior_comembership")
  shr <- lapply(dc, `[[`, "is_shareholder")

  # length(ix) periods, one of which is consumed as memory()'s lag.
  cat("\nestimating formation-only TERGM:", length(ix) - 1, "transitions,",
      R_boot, "bootstrap replications\n")
  fit <- btergm(trimmed[ix] ~ edges +
                  gwb1degree(0.5, fixed = TRUE) +
                  gwb2degree(0.5, fixed = TRUE) +
                  b1star(2) + b2star(2) +
                  nodecov("cum_degree_lag") + nodecov("kin_degree") +
                  edgecov(kin) + edgecov(own) + edgecov(com) + edgecov(shr) +
                  memory(type = "stability"),
                offset = TRUE, R = R_boot, verbose = FALSE)
  print(summary(fit))
  saveRDS(fit, sub("\\.rds$", "_fit.rds", out))
  cat("\nsaved", sub("\\.rds$", "_fit.rds", out), "\n")
}
