# Build a networkDynamic object for the Tunisian elite network, 2008-2012.
#
# Time is integer days since 2008-01-01 (see CODEBOOK.md). Censored endpoints
# are -Inf and Inf, which networkDynamic accepts natively: a right-censored
# spell is a tie we observed starting and never observed ending, and that is a
# different claim from a tie that ended on 2012-12-31.
#
#   Rscript R/build_networkdynamic.R

suppressPackageStartupMessages({
  library(networkDynamic)
  library(tsna)
})

base <- file.path("data", "processed", "multiplex-2008-2012", "exports", "rnd")
T0   <- as.Date("2008-01-01")

edge_spells   <- read.csv(file.path(base, "edge_spells.csv"),   stringsAsFactors = FALSE)
vertex_spells <- read.csv(file.path(base, "vertex_spells.csv"), stringsAsFactors = FALSE)
node_key      <- read.csv(file.path(base, "node_key.csv"),      stringsAsFactors = FALSE)

num <- function(x) suppressWarnings(as.numeric(x))   # "-Inf"/"Inf" parse directly
edge_spells$onset      <- num(edge_spells$onset)
edge_spells$terminus   <- num(edge_spells$terminus)
vertex_spells$onset    <- num(vertex_spells$onset)
vertex_spells$terminus <- num(vertex_spells$terminus)

nd <- networkDynamic(
  edge.spells   = edge_spells[, c("onset", "terminus", "tail", "head")],
  vertex.spells = vertex_spells[, c("onset", "terminus", "vertex.id")]
)

# Attach identities and static edge attributes.
node_key <- node_key[order(node_key$vertex.id), ]
network::set.vertex.attribute(nd, "node_id",   node_key$node_id)
network::set.vertex.attribute(nd, "label",     node_key$label)
network::set.vertex.attribute(nd, "node_type", node_key$node_type)
network::set.edge.attribute(nd, "role",        edge_spells$role)
network::set.edge.attribute(nd, "layer",       edge_spells$layer)
network::set.edge.attribute(nd, "link_status", edge_spells$link_status)

cat("networkDynamic built\n")
cat("  vertices:", network::network.size(nd), "\n")
cat("  edge spells:", nrow(edge_spells), "\n")
cat("  right-censored spells:", sum(is.infinite(edge_spells$terminus)), "\n")
cat("  left-censored spells: ", sum(is.infinite(edge_spells$onset)), "\n")

# Year boundaries in the same integer-day units.
year_starts <- as.numeric(as.Date(paste0(2008:2013, "-01-01")) - T0)

cat("\nEdges active per year:\n")
for (i in seq_len(length(year_starts) - 1)) {
  n <- network.edgecount.active(nd, onset = year_starts[i], terminus = year_starts[i + 1])
  cat(sprintf("  %d: %d\n", 2007 + i, n))
}

# Time-varying degree: the point of the exercise.
cat("\nMean degree by year (tsna):\n")
deg <- tSnaStats(nd, snafun = "degree", start = year_starts[1],
                 end = tail(year_starts, 1), time.interval = 365,
                 aggregate.dur = 365)
print(round(apply(deg, 1, mean, na.rm = TRUE), 3))

saveRDS(nd, file.path(base, "elite_networkdynamic.rds"))
cat("\nsaved", file.path(base, "elite_networkdynamic.rds"), "\n")
