# Load the Tunisian listed-firm multiplex into igraph and run the standard
# longitudinal multilayer diagnostics.
#
#   source("R/load_bourse_multiplex.R")
#   mx <- load_bourse_multiplex()            # observed ties only
#   mx <- load_bourse_multiplex(panel = TRUE) # carried-forward panel
#
# Requires: igraph, data.table.

suppressPackageStartupMessages({
  library(igraph)
  library(data.table)
})

PROC <- file.path("data", "processed", "bourse")

#' Read the edge list and entity table.
#'
#' @param panel  use the carried-forward panel instead of observed ties only.
#' @param layers restrict to these layers (default: all).
#' @param years  restrict to these years (default: all).
load_bourse_multiplex <- function(panel = FALSE, layers = NULL, years = NULL) {
  f <- if (panel) "multiplex_edges_panel.csv.gz" else "multiplex_edges_observed.csv.gz"
  e <- fread(file.path(PROC, f), encoding = "UTF-8")
  yr <- if (panel) "panel_year" else "year"
  setnames(e, yr, "year_", skip_absent = TRUE)
  e <- e[!is.na(year_)]
  if (!is.null(layers)) e <- e[layer %in% layers]
  if (!is.null(years))  e <- e[year_ %in% years]

  nodes <- fread(file.path(PROC, "entities.csv"), encoding = "UTF-8")
  list(edges = e, nodes = nodes,
       layers = sort(unique(e$layer)), years = sort(unique(e$year_)))
}

#' Build one igraph per (year, layer). Ownership layers stay directed; board and
#' interlock layers are undirected, matching the `directed` flag in the data.
as_graphs <- function(mx) {
  out <- list()
  for (y in mx$years) {
    for (l in mx$layers) {
      sub <- mx$edges[year_ == y & layer == l]
      if (nrow(sub) == 0) next
      directed <- as.logical(max(sub$directed, na.rm = TRUE))
      ids <- union(sub$source_id, sub$target_id)
      g <- graph_from_data_frame(
        sub[, .(from = source_id, to = target_id, weight, role, doc_url)],
        directed = directed,
        vertices = mx$nodes[entity_id %in% ids,
                            .(name = entity_id, label = canonical_name,
                              entity_type, is_bvmt_listed, isin)]
      )
      out[[paste(y, l, sep = "|")]] <- g
    }
  }
  out
}

#' Collapse the multiplex to a single weighted firm-firm graph per year.
#'
#' Layer weights let you state explicitly how much an ownership tie counts
#' relative to a shared director. They are a modelling choice, so they are a
#' parameter here rather than baked into the data.
collapse_year <- function(mx, year, layer_weights = NULL) {
  sub <- mx$edges[year_ == year]
  if (is.null(layer_weights)) {
    layer_weights <- setNames(rep(1, length(mx$layers)), mx$layers)
  }
  sub[, w := weight * layer_weights[layer]]
  agg <- sub[, .(weight = sum(w, na.rm = TRUE), n_layers = uniqueN(layer)),
             by = .(source_id, target_id)]
  ids <- union(agg$source_id, agg$target_id)
  graph_from_data_frame(
    agg, directed = TRUE,
    vertices = mx$nodes[entity_id %in% ids,
                        .(name = entity_id, label = canonical_name, entity_type)]
  )
}

#' Per-year, per-layer summary: size, density and weighted degree centralisation.
layer_summary <- function(mx) {
  gs <- as_graphs(mx)
  rbindlist(lapply(names(gs), function(k) {
    parts <- strsplit(k, "|", fixed = TRUE)[[1]]
    g <- gs[[k]]
    data.table(
      year = as.integer(parts[1]), layer = parts[2],
      n_nodes = vcount(g), n_edges = ecount(g),
      density = edge_density(g),
      mean_strength = mean(strength(g, mode = "all")),
      components = components(g)$no
    )
  }))
}

#' Entities present in more than one layer in a given year - the actors who
#' actually make the structure multiplex rather than a set of parallel graphs.
multiplex_actors <- function(mx, year) {
  sub <- mx$edges[year_ == year]
  long <- rbind(sub[, .(id = source_id, layer)], sub[, .(id = target_id, layer)])
  res <- long[, .(n_layers = uniqueN(layer),
                  layers = paste(sort(unique(layer)), collapse = ", ")), by = id]
  merge(res[n_layers > 1][order(-n_layers)],
        mx$nodes[, .(id = entity_id, canonical_name, entity_type)], by = "id")
}

if (sys.nframe() == 0) {
  mx <- load_bourse_multiplex()
  cat("layers:", paste(mx$layers, collapse = ", "), "\n")
  cat("years :", paste(range(mx$years), collapse = "-"), "\n")
  print(layer_summary(mx))
}
