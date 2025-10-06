reduce.mri <- function(df)
{
  
  # Data
  vars <- df %>% 
    select(starts_with("T0_i_ic")) %>% 
    names()
  
  # Build tree
  df.mri <- df %>%
    dplyr::select(patientID, all_of(
      vars
    )
    ) %>% 
    na.omit()

  id <- df.mri %>%
    dplyr::select(
      patientID
    )
  
  df.mri <- df.mri[,-nearZeroVar(df.mri)]
  
  df.mri <- as.matrix(df.mri)
  df.mri <- scale(df.mri)
  
  tree <- hclustvar(df.mri[, -1])
  
  # Bootstrapping
  stab <- stability(tree, B=20, graph=TRUE)
  stab$meanCR
  max(stab$meanCR) # 35 clusters - highest Rand criterion
  
  # Play with the k to 
  # Cut tree
  P507 <- cutreevar(obj = tree, k = 507)
  clus = cutree(tree, 507)
  n <- 507
  palette <- distinctColorPalette(n)
  
  #pdf(width = 64, height = 36 ,onefile = T)
  #plot(as.phylo(tree), type = "fan", tip.color = palette[clus], cex = 0.9)
  
  # Extract clusters
  cluster <- as.data.frame(P507$cluster)
  cluster <- rownames_to_column(cluster, var='variable')
  names(cluster)[names(cluster) == 'P507$cluster'] <- 'cluster'
  cluster.mapping <- arrange(cluster, cluster)
  
  save(cluster.mapping, file = "./data/mapping_mri_clusters.Rdata")
  
  # Create data frame with synthetic scores and outcomes
  PCA <- as.matrix(P507$scores)
  mri.clusters <- cbind(id, PCA)
  
  loadings <- P507$var
  
  mri.clusters <- mri.clusters %>% 
    mutate(cluster85 = cluster85*-1,
           cluster93 = cluster93*-1,
           cluster102 = cluster102*-1,
           cluster103 = cluster103*-1,
           cluster108 = cluster108*-1,
           cluster109 = cluster109*-1,
           cluster116 = cluster116*-1,
           cluster117 = cluster117*-1,
           cluster120 = cluster120*-1,
           cluster121 = cluster121*-1,
           cluster133 = cluster133*-1,
           cluster134 = cluster134*-1,
           cluster135 = cluster135*-1,
           cluster145 = cluster145*-1,
           cluster148 = cluster148*-1,
           cluster149 = cluster149*-1,
           cluster152 = cluster152*-1,
           cluster153 = cluster153*-1,
           cluster154 = cluster154*-1,
           cluster155 = cluster155*-1  
    )
  # Save
  save(mri.clusters, file = "./data/processed/mri.clusters.Rdata")
  return(mri.clusters)
}

reduce.cognition <- function(df)
{
  
  # Data
  vars <- df %>% 
    select(starts_with("T0_i_ic")) %>% 
    names()
  
  # Build tree
  df.mri <- df %>%
    dplyr::select(patientID, all_of(
      vars
    )
    ) %>% 
    na.omit()
  
  id <- df.mri %>%
    dplyr::select(
      patientID
    )
  
  df.mri <- df.mri[,-nearZeroVar(df.mri)]
  
  df.mri <- as.matrix(df.mri)
  df.mri <- scale(df.mri)
  
  tree <- hclustvar(df.mri[, -1])
  
  # Bootstrapping
  stab <- stability(tree, B=20, graph=TRUE)
  stab$meanCR
  max(stab$meanCR) # 35 clusters - highest Rand criterion
  
  # Play with the k to 
  # Cut tree
  P507 <- cutreevar(obj = tree, k = 507)
  clus = cutree(tree, 507)
  n <- 507
  palette <- distinctColorPalette(n)
  
  #pdf(width = 64, height = 36 ,onefile = T)
  #plot(as.phylo(tree), type = "fan", tip.color = palette[clus], cex = 0.9)
  
  # Extract clusters
  cluster <- as.data.frame(P507$cluster)
  cluster <- rownames_to_column(cluster, var='variable')
  names(cluster)[names(cluster) == 'P507$cluster'] <- 'cluster'
  cluster.mapping <- arrange(cluster, cluster)
  
  save(cluster.mapping, file = "./data/mapping_mri_clusters.Rdata")
  
  # Create data frame with synthetic scores and outcomes
  PCA <- as.matrix(P507$scores)
  mri.clusters <- cbind(id, PCA)
  
  loadings <- P507$var
  
  mri.clusters <- mri.clusters %>% 
    mutate(cluster85 = cluster85*-1,
           cluster93 = cluster93*-1,
           cluster102 = cluster102*-1,
           cluster103 = cluster103*-1,
           cluster108 = cluster108*-1,
           cluster109 = cluster109*-1,
           cluster116 = cluster116*-1,
           cluster117 = cluster117*-1,
           cluster120 = cluster120*-1,
           cluster121 = cluster121*-1,
           cluster133 = cluster133*-1,
           cluster134 = cluster134*-1,
           cluster135 = cluster135*-1,
           cluster145 = cluster145*-1,
           cluster148 = cluster148*-1,
           cluster149 = cluster149*-1,
           cluster152 = cluster152*-1,
           cluster153 = cluster153*-1,
           cluster154 = cluster154*-1,
           cluster155 = cluster155*-1  
    )
  # Save
  save(mri.clusters, file = "./data/processed/mri.clusters.Rdata")
  return(mri.clusters)
}

reduce.mri <- function(df)
{
  
  # Data
  vars <- df %>% 
    select(starts_with("T0_i_ic")) %>% 
    names()
  
  # Build tree
  df.mri <- df %>%
    dplyr::select(patientID, all_of(
      vars
    )
    ) %>% 
    na.omit()
  
  id <- df.mri %>%
    dplyr::select(
      patientID
    )
  
  df.mri <- df.mri[,-nearZeroVar(df.mri)]
  
  df.mri <- as.matrix(df.mri)
  df.mri <- scale(df.mri)
  
  tree <- hclustvar(df.mri[, -1])
  
  # Bootstrapping
  stab <- stability(tree, B=20, graph=TRUE)
  stab$meanCR
  max(stab$meanCR) # 35 clusters - highest Rand criterion
  
  # Play with the k to 
  # Cut tree
  P507 <- cutreevar(obj = tree, k = 507)
  clus = cutree(tree, 507)
  n <- 507
  palette <- distinctColorPalette(n)
  
  #pdf(width = 64, height = 36 ,onefile = T)
  #plot(as.phylo(tree), type = "fan", tip.color = palette[clus], cex = 0.9)
  
  # Extract clusters
  cluster <- as.data.frame(P507$cluster)
  cluster <- rownames_to_column(cluster, var='variable')
  names(cluster)[names(cluster) == 'P507$cluster'] <- 'cluster'
  cluster.mapping <- arrange(cluster, cluster)
  
  save(cluster.mapping, file = "./data/mapping_mri_clusters.Rdata")
  
  # Create data frame with synthetic scores and outcomes
  PCA <- as.matrix(P507$scores)
  mri.clusters <- cbind(id, PCA)
  
  loadings <- P507$var
  
  mri.clusters <- mri.clusters %>% 
    mutate(cluster85 = cluster85*-1,
           cluster93 = cluster93*-1,
           cluster102 = cluster102*-1,
           cluster103 = cluster103*-1,
           cluster108 = cluster108*-1,
           cluster109 = cluster109*-1,
           cluster116 = cluster116*-1,
           cluster117 = cluster117*-1,
           cluster120 = cluster120*-1,
           cluster121 = cluster121*-1,
           cluster133 = cluster133*-1,
           cluster134 = cluster134*-1,
           cluster135 = cluster135*-1,
           cluster145 = cluster145*-1,
           cluster148 = cluster148*-1,
           cluster149 = cluster149*-1,
           cluster152 = cluster152*-1,
           cluster153 = cluster153*-1,
           cluster154 = cluster154*-1,
           cluster155 = cluster155*-1  
    )
  # Save
  save(mri.clusters, file = "./data/processed/mri.clusters.Rdata")
  return(mri.clusters)
}

reduce.protein <- function(df)
{
  
  # Data
  vars <- df  %>% 
    dplyr::select(T0_TNFRSF14:T0_NTproBNP, T0_CRP_E1_C6, T0_eGFR_E1_C6) %>% 
    dplyr::select(where(is.numeric)) %>% 
    names()
  
  # Build tree
  df.olink<- df %>%
    dplyr::select(patientID, all_of(
      vars
    )
    ) %>% 
    na.omit()
  
  id <- df.olink %>%
    dplyr::select(
      patientID
    )
  
  df.olink <- as.matrix(df.olink)
  df.olink <- scale(df.olink)
  
  tree <- hclustvar(df.olink[, -1])
  
  # Bootstrapping
  stab <- stability(tree, B=20, graph=TRUE)
  stab$meanCR
  max(stab$meanCR) # 35 clusters - highest Rand criterion
  
  # Play with the k to 
  # Cut tree
  P89 <- cutreevar(obj = tree, k = 89)
  clus = cutree(tree, 89)
  n <- 89
  palette <- distinctColorPalette(n)
  
  #pdf(width = 64, height = 36 ,onefile = T)
  #plot(as.phylo(tree), type = "fan", tip.color = palette[clus], cex = 0.9)
  
  # Extract clusters
  cluster <- as.data.frame(P89$cluster)
  cluster <- rownames_to_column(cluster, var='variable')
  names(cluster)[names(cluster) == 'P89$cluster'] <- 'cluster'
  cluster.mapping <- arrange(cluster, cluster)
  
  save(cluster.mapping, file = "./data/mapping_olink_clusters.Rdata")
  
  # Create data frame with synthetic scores and outcomes
  PCA <- as.matrix(P89$scores)
  olink.clusters <- cbind(id, PCA)
  
  loadings <- P89$var
  
  olink.clusters <- olink.clusters %>% 
    mutate(cluster85 = cluster85*-1,
           cluster93 = cluster93*-1,
           cluster102 = cluster102*-1,
           cluster103 = cluster103*-1,
           cluster108 = cluster108*-1,
           cluster109 = cluster109*-1,
           cluster116 = cluster116*-1,
           cluster117 = cluster117*-1,
           cluster120 = cluster120*-1,
           cluster121 = cluster121*-1,
           cluster133 = cluster133*-1,
           cluster134 = cluster134*-1,
           cluster135 = cluster135*-1,
           cluster145 = cluster145*-1,
           cluster148 = cluster148*-1,
           cluster149 = cluster149*-1,
           cluster152 = cluster152*-1,
           cluster153 = cluster153*-1,
           cluster154 = cluster154*-1,
           cluster155 = cluster155*-1  
    )
  # Save
  save(olink.clusters, file = "./data/processed/mri.clusters.Rdata")
  return(mri.clusters)
}



