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
#     --all-ties   include ambiguous and probable/possible ties (default is
#                  resolved + certain only; see the certainty sensitivity in
#                  docs/TERGM-multiplex-2008-2012.md)
#
# Three design decisions are worth knowing before reading the code.
#
# 1. The vertex set is CONSTANT across periods and the risk set is expressed as
#    a structural-zero offset, rather than by deleting inactive vertices. The
#    `network` package does adjust the bipartite count when vertices are
#    deleted, so deletion is safe in that narrow sense -- but it makes the
#    vertex set differ between periods, and `memory()` then depends on how
#    btergm matches vertices across unequal networks. An offset states the same
#    claim with no such dependency: a dyad involving an organisation that did
#    not yet exist is impossible, not merely unobserved.
#
# 2. Dyadic covariates are stored on disk as sparse triplets and densified
#    here, one matrix per covariate per period. At the full universe that is
#    2592 x 2915 integers, about 30 MB each: three covariates over four lagged
#    periods plus the offsets comes to roughly half a gigabyte of R memory.
#    That is the honest cost of the full risk set. Use --sample to work smaller.
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

# --- structural zeros: the risk set -----------------------------------------
# Every person is at risk in every period (the gazette records appointments,
# not births), so the impossible dyads are exactly the columns of organisations
# outside their own lifecycle. Built column-wise for that reason.
offsets <- list()
for (p in periods) {
  act <- activity[activity$period == p, ]
  act <- act[match(node_key$vertex_id, act$vertex_id), ]
  inactive_org <- which(act$active == 0L & node_key$mode == 2L) - n1
  m <- matrix(0L, nrow = n1, ncol = n2)
  if (length(inactive_org)) m[, inactive_org] <- 1L
  offsets[[as.character(p)]] <- m
}

# --- dyadic covariates ------------------------------------------------------
# kin_in_org, owner_of and prior_comembership are lagged to t-1 by
# construction, which is what keeps them exogenous to the tie being modelled;
# they are all zero in period 1, which has no lag. is_shareholder is read from
# the undated seed sheet, so it is exogenous without a lag and is populated in
# every period, period 1 included.
densify <- function(field, p) {
  m <- matrix(0L, nrow = n1, ncol = n2)
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
cat("\nper-period structure:\n")
for (p in periods) {
  net <- nets[[as.character(p)]]
  cat(sprintf("  %s  size %d  bipartite %s  edges %5d  impossible dyads %7d\n",
              p, network.size(net),
              ifelse(is.bipartite(net), as.character(net %n% "bipartite"), "NO"),
              network.edgecount(net), sum(offsets[[as.character(p)]])))
}
stopifnot(all(vapply(nets, is.bipartite, logical(1))))
stopifnot(all(vapply(nets, network.size, numeric(1)) == n))

# A smoke subset is not the dataset, so it must not be saved over it.
out <- file.path(base, if (is.na(sample_n) && !all_ties) "tergm_panel.rds"
                       else sprintf("tergm_panel_%s%s.rds",
                                    if (is.na(sample_n)) "full" else
                                      paste0("sample", sample_n),
                                    if (all_ties) "_allties" else ""))
saveRDS(list(networks = nets, offsets = offsets, dyad_cov = dyad_cov,
             node_key = node_key, n1 = n1, n2 = n2, periods = periods),
        out)
cat("\nsaved", out, "\n")

# --- worked model: FORMATION ONLY -------------------------------------------
# 82% of dated spells are right-censored, because the gazette publishes
# arrivals far more reliably than departures. A dissolution or persistence
# parameter fitted here would describe when an exit gets *printed*, not when a
# tie ends, so this specification models formation and does not interpret the
# other side. Read docs/TERGM-multiplex-2008-2012.md before changing that.
if (!requireNamespace("btergm", quietly = TRUE)) {
  cat("\nbtergm is not installed; the panel above is built and saved.\n")
  cat("install.packages(\"btergm\") to estimate, then:\n\n")
} else {
  cat("\nestimating (formation only, bipartite terms)\n")
}
cat("  library(btergm)\n",
    "  p  <- readRDS(\"", out, "\")\n",
    "  ns <- p$networks; off <- p$offsets; dc <- p$dyad_cov\n",
    "  ix <- 2:length(ns)   # period 1 carries no lag\n",
    "  m <- btergm(ns[ix] ~ edges +\n",
    "        gwb1degree(0.5, fixed = TRUE) + gwb2degree(0.5, fixed = TRUE) +\n",
    "        b1star(2) + b2star(2) + cycle(4) +\n",
    "        nodefactor(\"node_type\") + nodecov(\"cum_degree_lag\") +\n",
    "        nodecov(\"kin_degree\") +\n",
    "        edgecov(lapply(dc, `[[`, \"kin_in_org\")) +\n",
    "        edgecov(lapply(dc, `[[`, \"owner_of\")) +\n",
    "        edgecov(lapply(dc, `[[`, \"prior_comembership\")) +\n",
    "        edgecov(lapply(dc, `[[`, \"is_shareholder\")) +\n",
    "        memory(type = \"stability\") +\n",
    "        offset(edgecov(off[ix])),\n",
    "      offset = TRUE, R = 500)\n",
    "  summary(m)\n", sep = "")
