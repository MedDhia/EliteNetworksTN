# Build the organisation-to-organisation ownership network, 1957-2026.
#
#   Rscript R/build_org_ownership.R [--all-relations] [--include-seed]
#
#     --all-relations  include the audit, branch and membership relations
#                      alongside ownership (default: ownership only)
#     --include-seed   include the undated seed-sheet ties as a static overlay
#
# This is a ONE-MODE network, and that is the whole reason it is a separate
# layer rather than extra rows in the person-organisation panel. Two things
# follow that do not hold on the bipartite panel:
#
#  * The ordinary closure terms are valid here. `triangle`, `gwesp` and
#    `kstar` count structures that cannot exist in a two-mode graph, which is
#    why docs/TERGM-multiplex.md forbids them there. On an org-org ownership
#    network they are exactly the interesting terms: a triangle is a
#    cross-holding triad, and transitivity is what a pyramid looks like.
#  * Ties are DIRECTED. A holds a stake in B is not B holds a stake in A, and
#    collapsing the direction would turn a pyramid into a clique.
#
# Read docs/ORG-TIES-multiplex.md before modelling. The short version: the
# dominant clause in the register confirms a standing holding at a filing date
# rather than dating its start, so onsets here are heavily left-censored and a
# duration model over them measures filing frequency, not ownership tenure.

suppressPackageStartupMessages(library(network))

args <- commandArgs(trailingOnly = TRUE)
all_relations <- "--all-relations" %in% args
include_seed  <- "--include-seed"  %in% args

base <- file.path("data", "processed", "multiplex")
rd <- function(f) read.csv(file.path(base, f), stringsAsFactors = FALSE)

spells <- rd("org_tie_spells.csv")
panel  <- rd("panel_org_ties_yearly.csv")

if (!all_relations) {
  spells <- spells[spells$is_ownership == 1, ]
  panel  <- panel[panel$is_ownership == 1, ]
}
if (!include_seed) {
  spells <- spells[spells$evidence_tier == "gazette_dated", ]
}

cat(sprintf("org-org spells: %d (%s relations, seed %s)\n", nrow(spells),
            if (all_relations) "all" else "ownership only",
            if (include_seed) "included" else "excluded"))
cat(sprintf("  left-censored onsets: %d (%.0f%%)\n",
            sum(spells$left_censored == "True"),
            100 * mean(spells$left_censored == "True")))

# --- vertex set -------------------------------------------------------------
# Fixed across periods, as on the bipartite panel and for the same reason: a
# firm with no ownership tie in a given year is an isolate that year, not an
# absent vertex, and building each period from its own edge list would let the
# vertex set drift.
orgs <- sort(unique(c(panel$from_node_id, panel$to_node_id)))
n <- length(orgs)
vid <- setNames(seq_len(n), orgs)
cat(sprintf("vertices: %d organisations\n", n))

labels <- unique(rbind(
  data.frame(id = spells$holder_id, label = spells$holder_label),
  data.frame(id = spells$target_id, label = spells$target_label)))
labels <- labels[!duplicated(labels$id), ]
rownames(labels) <- labels$id

periods <- sort(unique(panel$panel_id))

# --- one network per period -------------------------------------------------
nets <- list()
for (p in periods) {
  e <- panel[panel$panel_id == p, ]
  net <- network.initialize(n, directed = TRUE)   # direction is substantive
  network.vertex.names(net) <- orgs
  if (nrow(e)) {
    add.edges(net, unname(vid[e$from_node_id]), unname(vid[e$to_node_id]))
  }
  set.vertex.attribute(net, "label",
                       ifelse(orgs %in% labels$id, labels[orgs, "label"], orgs))
  nets[[p]] <- net
}

cat("\nper-period structure:\n")
for (p in periods) {
  net <- nets[[p]]
  if (network.edgecount(net) == 0) next
  cat(sprintf("  %-14s edges %5d  density %.5f\n", p,
              network.edgecount(net),
              network.edgecount(net) / (n * (n - 1))))
}

out <- file.path(base, "exports",
                 sprintf("org_ownership%s%s.rds",
                         if (all_relations) "_all" else "",
                         if (include_seed) "_seed" else ""))
dir.create(dirname(out), showWarnings = FALSE, recursive = TRUE)
saveRDS(list(networks = nets, orgs = orgs, periods = periods,
             spells = spells), out)
cat("\nsaved", out, "\n")

cat("\nTo model (one-mode, so closure terms apply):\n")
cat('  library(btergm)\n',
    '  p <- readRDS("', out, '")\n',
    '  ix <- which(sapply(p$networks, network.edgecount) > 0)\n',
    '  m <- btergm(p$networks[ix] ~ edges + mutual +\n',
    '        gwidegree(0.5, fixed = TRUE) + gwodegree(0.5, fixed = TRUE) +\n',
    '        gwesp(0.5, fixed = TRUE) +          # valid here, not on the bipartite panel\n',
    '        memory(type = "stability"),\n',
    '      R = 200)\n',
    '  summary(m)\n', sep = "")
