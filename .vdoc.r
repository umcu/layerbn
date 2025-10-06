#
#
#
#
#
#
#
#

library(ProjectTemplate)
load.project()

#
#
#

df <- readRDS("data/df.rds")
imp <- readRDS("data/df_imp.rds")

#
#
#

library(NMF)
library(dplyr)
library(tidyverse)
library(broom)
library(officer)
library(flextable)
library(caret)

#
#
#

# Define custom colors from the magma palette for three profiles
magma_colors <- viridis::magma(10)  # Generate a 10-color magma palette
custom_palette <- c(magma_colors[3], magma_colors[6], magma_colors[9])  # Select three distinct colors
custom_palette_2 <- c(magma_colors[2], magma_colors[4], magma_colors[6], 
magma_colors[8], magma_colors[10])

#
#
#

# Step 1: Define the columns to be excluded from FAMD
classCol <- c("Time", "Time_Stroke", "patientID", "Event_Stroke", 
              "Time_MACE","Event_MACE", "CDR_INCR", "T0_WMH", 
              "outcome_composite", "T0_CDR", "T0_neurorad_svd_score", 
              "T0_TBV_ICV", "T0_HV_ICV", "Event", "CDR_Time",
              "T0_i_icbf_GrayMatter_mean_mL100gmin",
              "T0_neurorad_lobar_microbleed_present", 
              "T0_neurorad_non_lobar_microbleed_present",
              "T0_neurorad_moderate_severe_pvs",
              "T0_neurorad_number_of_lacunar_infarcts")

# Step 2: Filter the original dataframe `df_network` excluding the defined columns
df_network <- imp[, !(names(imp) %in% classCol)]
names(df_network) <- sub('T0_', '', names(df_network))

# Step 3: Select only the columns relevant for NMF in `df_network`
df_nmf <- df_network %>% select(Aβ40:NTproBNP)

# Step 4: Convert data to matrix format for NMF
df_nmf_mat <- as.matrix(df_nmf)

process <- preProcess(as.data.frame(df_nmf_mat), method=c("range"))
norm_scale <- predict(process, as.data.frame(df_nmf_mat))
norm_scale <- as.matrix(norm_scale)

nmf_results <- nmf(norm_scale, 2:10, nrun = 100)
plot(nmf_results) # Rank 3: highest cophonetic, dispersion drops IN MANUSCRIPT

# Run NMF on the filtered matrix
rank <- 4
set.seed(1234)
nmf_result <- nmf(norm_scale, rank = rank, 
                  method = "lee", nrun = 300)

# Extract profiles and activations
activations <- basis(nmf_result)  # Patients x NMF components matrix
profiles <- coef(nmf_result)  # Proteins x NMF components matrix

# Bind the patient loadings (activations) to the filtered df_network for downstream analysis
df_with_profiles <- cbind(df, activations)

#
#
#
#
library(pheatmap)

# Generate  for cell profiles vs. hematology variables

pheatmap(activations, 
         cluster_rows = TRUE,       # Cluster cell profiles
         cluster_cols = TRUE,       # Cluster hematology variables
         scale = "column",          # Scale values within each column
         color = viridis::magma(100),
         main = "Heatmap of Protein Profiles",
         fontsize_row = 10,         # Adjust font size for readability
         fontsize_col = 10)

pheatmap(profiles, 
         cluster_rows = FALSE,                    # Cluster patients
         cluster_cols = TRUE,                    # Cluster proteins
         clustering_method = "ward.D2",          # Use Ward's method for clustering
         scale = "column",                       # Scale within each column for comparison
         color = viridis::magma(100),           # Change to plasma color scheme for better contrast
         treeheight_row = 50,                    # Adjust row dendrogram height
         treeheight_col = 30,                    # Adjust column dendrogram height
         main = "Clustered Heatmap of Protein Profiles",
         fontsize_row = 10,                      # Font size adjustments
         fontsize_col = 10)

#
#
#

df_with_profiles <- df_with_profiles %>%
  rename_with(~ c("Profile1", "Profile2", "Profile3", "Profile4"), c(`1`, `2`, `3`, `4`)) %>%
  mutate(Dominant_Profile = max.col(dplyr::select(., Profile1, Profile2, Profile3, Profile4), ties.method = "first"))

#
#
#

activations_long <- df_with_profiles %>%
  pivot_longer(cols = starts_with("Profile"), names_to = "Profile", values_to = "Activation")

#
#
#
#

library(gtsummary)
library(haven)

df_with_profiles$T0_patientengroep_E1_C1 <- 
  as.factor(df_with_profiles$T0_patientengroep_E1_C1)

# Step 2: Select relevant variables and group by Profile
df_analysis <- df_with_profiles %>%
  dplyr::select(Dominant_Profile, T0_Age, Sex, T0_WMH, T0_HV_ICV, T0_TBV_ICV, 
         T0_neurorad_lobar_microbleed_present, 
         T0_neurorad_non_lobar_microbleed_present,
         T0_neurorad_number_of_lacunar_infarcts,
         T0_patientengroep_E1_C1)

# Step 3: Create a summary table with `gtsummary` to compare outcomes across profiles
summary_table <- df_analysis %>%
  tbl_summary(by = Dominant_Profile,  # Compare outcomes across Profile groups
              statistic = list(all_continuous() ~ "{median} ({IQR})", 
                               all_categorical() ~ "{n} / {N} ({p}%)"),
              missing_text = "Missing") %>%
  add_p() %>% 
  add_q()

# Display the table
summary_table # IN MANUSCRIPT
summary_table <- as.data.frame(summary_table)
# Assuming your dataframe is called final_summary

my_table <- flextable(summary_table) %>%
  autofit() %>%  # Automatically adjust column widths
  set_caption("Summary of Associations Between Profiles and Outcomes") # Add a caption if needed

# Export the flextable to a Word document
doc <- read_docx() %>%
  body_add_flextable(my_table) %>%
  body_add_par("") # Adds a blank line after the table if you need to add more content

# Save the document
print(doc, target = "Profile_Outcome_Summary.docx")

#
#
#
#
#

library(gtsummary)

df_with_profiles$T0_patientengroep_E1_C1 <- 
  as.factor(df_with_profiles$T0_patientengroep_E1_C1)

# Step 2: Select relevant variables and group by Profile
df_analysis <- df_with_profiles %>%
  dplyr::select(Dominant_Profile, T0_Age, Sex, T0_cholesterol_E1_C1, T0_cholesterol_medicatie_E1_C1, 
         T0_bloeddruk_E1_C1, T0_bloeddruk_medicatie_E1_C1, T0_BMI, 
         T0_TIA_E1_C1, T0_hartinfarct_E1_C1, T0_dotter_E1_C1)

# Step 3: Create a summary table with `gtsummary` to compare outcomes across profiles
summary_table <- df_analysis %>%
  tbl_summary(by = Dominant_Profile,  # Compare outcomes across Profile groups
              statistic = list(all_continuous() ~ "{median} ({IQR})", 
                               all_categorical() ~ "{n} / {N} ({p}%)"),
              missing_text = "Missing") %>%
  add_p() %>% 
  add_q()

# Display the table
summary_table # IN MANUSCRIPT

summary_table # IN MANUSCRIPT
summary_table <- as.data.frame(summary_table)
# Assuming your dataframe is called final_summary

my_table <- flextable(summary_table) %>%
  autofit() %>%  # Automatically adjust column widths
  set_caption("Summary of Associations Between Profiles and Characteristics") # Add a caption if needed

# Export the flextable to a Word document
doc <- read_docx() %>%
  body_add_flextable(my_table) %>%
  body_add_par("") # Adds a blank line after the table if you need to add more content

# Save the document
print(doc, target = "Profile_Characteristics_Summary.docx")
#
#
#
#

# Define continuous and binary outcomes
continuous_outcomes <- c("T0_WMH", "T0_HV_ICV", "T0_TBV_ICV", 
                         "T0_neurorad_number_of_lacunar_infarcts")

binary_outcomes <- c("T0_neurorad_lobar_microbleed_present", 
                     "T0_neurorad_non_lobar_microbleed_present")

# Define profiles to scale
profiles_to_scale <- c("Profile1", "Profile2", "Profile3", "Profile4")

df_with_profiles$T0_neurorad_lobar_microbleed_present <- as.factor(df_with_profiles$T0_neurorad_lobar_microbleed_present)
df_with_profiles$T0_non_neurorad_lobar_microbleed_present <- as.factor(df_with_profiles$T0_neurorad_non_lobar_microbleed_present)

# Scale continuous outcomes and profiles
df_with_profiles <- df_with_profiles %>%
  mutate(across(all_of(c(continuous_outcomes, profiles_to_scale)), scale))  # scales both continuous outcomes and profiles

#### Step 2: Calculate Spearman Correlations for Continuous Outcomes

# Create a list to store Spearman correlation results for each profile

spearman_results <- map_dfr(continuous_outcomes, function(outcome) {
  map_dfr(c("Profile1", "Profile2", "Profile3", "Profile4"), function(profile) {
    cor_test <- cor.test(df_with_profiles[[profile]], df_with_profiles[[outcome]], 
                         method = "spearman")
    tibble(Outcome = outcome, 
           Profile = profile, 
           Estimate = cor_test$estimate, 
           p_value = cor_test$p.value)
  })
})

# Adjust p-values for multiple testing (Spearman Correlations)
spearman_results <- spearman_results %>%
  group_by(Outcome) %>%
  mutate(q_value = p.adjust(p_value, method = "BH")) %>%
  ungroup()

#### Step 3: Logistic Regression for Binary Outcomes

# Run logistic regression for each binary outcome
logistic_results <- map_dfr(binary_outcomes, function(outcome) {
  map_dfr(c("Profile1", "Profile2", "Profile3", "Profile4"), function(profile) {
    model <- glm(reformulate(profile, outcome), 
                 data = df_with_profiles, 
                 family = binomial)
    model_summary <- tidy(model, conf.int = TRUE)
    tibble(Outcome = outcome, 
           Profile = profile, 
           Estimate = model_summary$estimate[2], 
           conf.low = model_summary$conf.low[2], 
           conf.high = model_summary$conf.high[2],
           p_value = model_summary$p.value[2])
  })
})

# Adjust p-values for multiple testing (Logistic Regression)
logistic_results <- logistic_results %>%
  group_by(Outcome) %>%
  mutate(q_value = p.adjust(p_value, method = "BH")) %>%
  ungroup()

#### Step 4: Combine Results into a Summary Table

# Format Spearman correlations
spearman_summary <- spearman_results %>%
  mutate(Statistic = "Spearman Correlation",
         Result = sprintf("%.2f (p = %.3g, q = %.3g)", Estimate, p_value, q_value)) %>%
  dplyr::select(Outcome, Profile, Statistic, Result)

# Format Logistic regression results
logistic_summary <- logistic_results %>%
  mutate(Statistic = "Logistic Regression (OR)",
         Result = sprintf("%.2f (95%% CI: %.2f - %.2f, p = %.3g, q = %.3g)", 
                          exp(Estimate), exp(conf.low), exp(conf.high), p_value, q_value)) %>%
  dplyr::select(Outcome, Profile, Statistic, Result)

# Combine both tables
final_summary <- bind_rows(spearman_summary, logistic_summary) %>%
  pivot_wider(names_from = Profile, values_from = Result) %>%
  arrange(Outcome, Statistic)

# Display the final summary table
final_summary
final_summary <- as.data.frame(final_summary)
# Assuming your dataframe is called final_summary

my_table <- flextable(final_summary) %>%
  autofit() %>%  # Automatically adjust column widths
  set_caption("Statistics of Associations Between Profiles and Outcomes") # Add a caption if needed

# Export the flextable to a Word document
doc <- read_docx() %>%
  body_add_flextable(my_table) %>%
  body_add_par("") # Adds a blank line after the table if you need to add more content

# Save the document
print(doc, target = "Profile_Outcome_Statistics.docx")
#
#
#
#
#
library(ggstatsplot)

# Plot 1: T0_WMH by Profile using ggbetweenstats
ggbetweenstats(
  data = df_with_profiles,
  x = Dominant_Profile,
  y = T0_WMH,
  ggtheme = theme_minimal(),
  title = "Comparison of WMH by Profile",
  type = "nonparametric"
) +
  scale_color_manual(values = custom_palette)

# Plot 2: Profile by T0_neurorad_lobar_microbleed_present using ggbarstats
ggbarstats(
  data = df_with_profiles,
  x = T0_neurorad_lobar_microbleed_present,
  y = Dominant_Profile,
  ggtheme = theme_minimal(),
  type = "nonparametric",
  title = "Lobar Microbleeds by Profile"
) +
  scale_fill_manual(values = custom_palette)

# Plot 3: Profile by T0_neurorad_non_lobar_microbleed_present using ggbarstats
ggbarstats(
  data = df_with_profiles,
  x = T0_neurorad_non_lobar_microbleed_present,
  y = Dominant_Profile,
  ggtheme = theme_minimal(),
  type = "nonparametric",
  title = "Non-lobar Microbleeds by Profile"
) +
  scale_fill_manual(values = custom_palette)

# Plot 4: T0_neurorad_number_of_lacunar_infarcts by Profile using ggbetweenstats
ggbetweenstats(
  data = df_with_profiles,
  x = Dominant_Profile,
  y = T0_neurorad_number_of_lacunar_infarcts,
  ggtheme = theme_minimal(),
  type = "nonparametric",
  title = "Number of Lacunar Infarcts by Profile"
) +
  scale_color_manual(values = custom_palette)

# Plot 5: T0_neurorad_svd_score by Profile using ggbarstats
ggbarstats(
  data = df_with_profiles,
  x = Dominant_Profile,
  y = T0_neurorad_svd_score,
  type = "nonparametric",
  ggtheme = theme_minimal(),
  title = "SVD Score by Profile"
) +
  scale_fill_manual(values = custom_palette)

#Plot 5: T0_neurorad_svd_score by Profile using ggbarstats
ggbarstats(
  data = df_with_profiles,
  x = T0_patientengroep_E1_C1,
  y = Dominant_Profile,
  type = "nonparametric",
  ggtheme = theme_minimal(),
  title = "SVD Score by Profile"
) +
  scale_fill_manual(values = custom_palette_2)

#
#
#
#
#
library(rstatix)

# Define the profiles matrix (assuming rows are profiles and columns are proteins)
profiles_df <- as.data.frame(t(profiles))
colnames(profiles_df) <- c("Profile1", "Profile2", "Profile3")

# Calculate fold change for each profile compared to the average of the other profiles
profiles_df <- profiles_df %>%
  rownames_to_column(var = "Protein") %>%
  mutate(
    FC_Profile1 = Profile1 / ((Profile2 + Profile3) / 2),
    FC_Profile2 = Profile2 / ((Profile1 + Profile3) / 2),
    FC_Profile3 = Profile3 / ((Profile1 + Profile2) / 2)
  )

# Select top 20 proteins for each profile based on fold change
top_proteins_profile1 <- profiles_df %>% arrange(desc(FC_Profile1)) %>% 
  slice_head(n = 30) %>% pull(Protein)

top_proteins_profile2 <- profiles_df %>% arrange(desc(FC_Profile2)) %>% 
  slice_head(n = 30) %>% pull(Protein)

top_proteins_profile3 <- profiles_df %>% arrange(desc(FC_Profile3)) %>% 
  slice_head(n = 30) %>% pull(Protein)
#
#
#
#

model <- glm(T0_WMH ~ Profile1, df_with_profiles, family = "gaussian")
summary(model) # Age-related changes!
model <- glm(T0_WMH ~ Profile2, df_with_profiles, family = "gaussian")
summary(model) # Age-related changes!
model <- glm(T0_WMH ~ Profile3, df_with_profiles, family = "gaussian")
summary(model) # Age-related changes!

model <- glm(T0_WMH ~ Profile1 + T0_Age, df_with_profiles, 
             family = "gaussian")
summary(model)

model <- glm(T0_WMH ~ Profile2 + T0_Age, df_with_profiles, 
             family = "gaussian")
summary(model)

model <- glm(T0_WMH ~ Profile3 + T0_Age, df_with_profiles, 
             family = "gaussian")
summary(model)

#
#
#

library(survival)
library(survminer)

# Ensure Dominant_Profile is treated as a factor
df_with_profiles$Dominant_Profile <- as.factor(df_with_profiles$Dominant_Profile)

# Cox proportional hazards model with Profile as predictor
cox_model <- coxph(Surv(Time_MACE, Event_MACE) ~ Dominant_Profile + T0_Age, data = df_with_profiles)
summary(cox_model)

# Fit Kaplan-Meier curves for visualization
fit <- survfit(Surv(Time_MACE, Event_MACE) ~ Dominant_Profile, data = df_with_profiles)

# Cox proportional hazards model with Profile as predictor
cox_model <- coxph(Surv(Time_Stroke, Event_Stroke) ~ Dominant_Profile + T0_Age, data = df_with_profiles)
summary(cox_model)

#
#
#
#
patient_loadings <- basis(nmf_result)  # This matrix has patients as rows and NMF components as columns
protein_controbutions <- coef(nmf_result)  # This matrix has patients as rows and NMF components as columns

#
#
#



#
#
#
#
#
# The basis (W) matrix represents cell signatures (marker profiles)
profiles <- basis(nmf_result)

# The coefficient (H) matrix represents activations for each sample
activations <- coef(nmf_result)
#
#
#
#
#
#
#
#
#
#
#

olink <- imp %>% 
  dplyr::select(T0_TNFRSF14:T0_NTproBNP)

olink_pca <- PCA(olink, ncp=10)
var <- get_pca_var(olink_pca)
get_eig(olink_pca)
fviz_screeplot(olink_pca, addlabels=TRUE)

chosen_dims <- olink_pca$ind$coord[, 1:10] # Keeping 5 dimensions as an example

#
#
#
#

# Calculate the variable contributions to the dimensions
var_contrib <- get_pca_var(olink_pca)$contrib

# Select top contributing variables for each dimension
top_contrib <- function(contrib, dimension, top_n = 10){
  contrib[order(-contrib[, dimension]), ][1:top_n, dimension, drop = FALSE]
}


top_contrib_vars <- lapply(1:10, function(dim) {
  top_contrib(var_contrib, dim)
})

# Create a data frame for top variable contributions for each dimension
top_contrib_df <- do.call(rbind, lapply(seq_along(top_contrib_vars), function(dim) {
  df <- data.frame(variable = rownames(top_contrib_vars[[dim]]), 
                   contribution = top_contrib_vars[[dim]][, 1], 
                   dimension = paste("Dim", dim, sep = "."))
  rownames(df) <- NULL
  return(df)
}))

top_contrib_df$variable <- sub('T0_', '', top_contrib_df$variable)

# Plot the top contributions
ggplot(top_contrib_df, aes(x = reorder(variable, -contribution), 
                           y = contribution, fill = dimension)) + 
  geom_bar(stat = 'identity') + 
  coord_flip() + 
  facet_wrap(~dimension, scales = "free") + 
  theme_minimal() + 
  labs(title = "Top-20 Variable Contributions to Dimensions", 
       x = "Variable", y = "Contribution")

#
#
#
#

df_network <- df_network %>% 
  dplyr::select(-TNFRSF14:-NTproBNP)

df_network <- cbind(df_network, chosen_dims)

#
#
#
#

# Perform FAMD
famd <- FAMD(df_network, ncp=10)
var <- get_famd_var(famd)
print(var)
get_eig(famd)
fviz_screeplot(famd, addlabels=TRUE)

fviz_famd_var(famd, "var", col.var = "contrib")

chosen_dims <- famd$ind$coord

# Determine the optimal number of clusters
elbow_plot <- fviz_nbclust(chosen_dims, stats::kmeans, method = "wss")
print(elbow_plot)

#
#
#
#
# # Perform K-means clustering (choose optimal_k based on plots)
# optimal_k <- 5
# kmeans <- kmeans(chosen_dims, centers = optimal_k)
# # Visualize the clusters
# cluster_plot <- fviz_cluster(kmeans, data = chosen_dims, geom = "point",
#                              ellipse.type = "convex", palette = "Reds",
#                              ggtheme = theme_pubclean(),
#                              main = paste("K-means Clustering with k =",
#                                           optimal_k))
# print(cluster_plot)
# 
# # Add cluster assignment to the original data
# df_network$cluster <- as.factor(kmeans$cluster)

#
#
#
#

library(dbscan)

db <- hdbscan(chosen_dims, minPts = 1)
db

pairs(chosen_dims, col = db$cluster + 1L)
plot(chosen_dims, col=db$cluster+1, pch=20)

print(db$cluster_scores)
head(db$membership_prob)

plot(chosen_dims, col=db$cluster+1, 
       pch=ifelse(db$cluster == 0, 8, 1), # Mark noise as star
       cex=ifelse(db$cluster == 0, 0.5, 0.75), # Decrease size of noise
       xlab=NA, ylab=NA)
colors <- sapply(1:length(db$cluster), 
                   function(i) adjustcolor(palette()[(db$cluster+1)[i]], alpha.f = db$membership_prob[i]))
  points(db, col=colors, pch=20)

#
#
#
#
library(mclust)

# Fit GMM
gmm_result <- Mclust(chosen_dims)
summary(gmm_result)

# Accessing the predicted cluster for each patient
clusters <- gmm_result$classification

# Accessing the uncertainty of cluster assignments
uncertainties <- gmm_result$uncertainty

# Identifying noise points (e.g., uncertainty > 0.5)
noise_points <- which(uncertainties > 0.5)

# Add cluster and uncertainty to the original data
#chosen_dims$cluster <- as.factor(clusters)
#chosen_dims$uncertainty <- uncertainties

chosen_dims <- cbind(chosen_dims, cluster=as.factor(clusters))
chosen_dims <- cbind(chosen_dims, uncertainty=uncertainties)

# Plot clusters with noise highlighted
ggplot(chosen_dims, aes(x = Dim.1, y = Dim.2, color = as.factor(cluster))) +
  geom_point(size = 2) +
  labs(title = "GMM Clustering with Noise Patients Highlighted",
       x = "FAMD Dimension 1", 
       y = "FAMD Dimension 2") +
  scale_shape_manual(values = c(16, 1), labels = c("Clustered", "Noise")) +
  scale_color_brewer(palette="Reds")+
  theme_minimal()

ggplot(chosen_dims, aes(x = Dim.1, y = Dim.2, color = uncertainty)) +
  geom_point(size = 2) +
  scale_color_gradient(low = "blue", high = "red") +
  labs(title = "GMM Clustering Uncertainty",
       x = "FAMD Dimension 1", 
       y = "FAMD Dimension 2",
       color = "Uncertainty") +
  theme_minimal()

#
#
#
#
# Calculate the variable contributions to the dimensions
var_contrib <- get_famd_var(famd)$contrib

# Select top contributing variables for each dimension
top_contrib <- function(contrib, dimension, top_n = 20){
  contrib[order(-contrib[, dimension]), ][1:top_n, dimension, drop = FALSE]
}


top_contrib_vars <- lapply(1:2, function(dim) {
  top_contrib(var_contrib, dim)
})

# Create a data frame for top variable contributions for each dimension
top_contrib_df <- do.call(rbind, lapply(seq_along(top_contrib_vars), function(dim) {
  df <- data.frame(variable = rownames(top_contrib_vars[[dim]]), 
                   contribution = top_contrib_vars[[dim]][, 1], 
                   dimension = paste("Dim", dim, sep = "."))
  rownames(df) <- NULL
  return(df)
}))

top_contrib_df$variable <- sub('T0_', '', top_contrib_df$variable)

# Plot the top contributions
ggplot(top_contrib_df, aes(x = reorder(variable, -contribution), 
                           y = contribution, fill = dimension)) + 
  geom_bar(stat = 'identity') + 
  coord_flip() + 
  facet_wrap(~dimension, scales = "free") + 
  theme_minimal() + 
  labs(title = "Top-20 Variable Contributions to Dimensions", 
       x = "Variable", y = "Contribution")+
  scale_fill_brewer(palette="Reds")

# Compare the averages across the distributions
#kmeans_clusters <- imp_famd %>%s
#  mutate(CDR_INCR = as.factor(df$CDR_INCR), 
#         Event_Stroke = df$Event_Stroke,
#         Event_MACE = df$Event_MACE,
#         Stroke_Time = df$Time_Stroke, 
#         MACE_Time=df$Time_MACE,
#         PT_group=df_fu_5$T0_patientengroep_E1_C1,
#         CDR = df$T0_CDR,
#         SVD = df$T0_neurorad_svd_score)



#
#
#
df_network$cluster <- as.factor(clusters)

#
#
#
library(fmsb)

# Assuming binary factors are coded as "Yes"/"No" or similar.
df_perc <- df_network %>%
  group_by(cluster) %>%
  summarise(across(where(is.factor), 
                   ~ mean(as.numeric(.x == levels(.x)[2]), 
                          na.rm = TRUE) * 100)) %>%
  pivot_longer(-cluster, names_to = "Variable", values_to = "Percentage")

# Calculate mean for each variable per cluster
plot_data_cat <- df_perc %>%
  group_by(cluster, Variable) %>%
  summarise(Value = median(Percentage, na.rm = TRUE))

# Modify your plotting code
ggplot(plot_data_cat, aes(x = reorder_within(Variable, Value, cluster), y = Value, color = as.factor(cluster))) +
  geom_segment(aes(x = reorder_within(Variable, Value, cluster), xend = reorder_within(Variable, Value, cluster), 
                   y = 0, yend = Value), color = "grey") +
  geom_point(size = 4) +
  labs(title = "Lollipop Chart Showing Differences in Percentages",
       x = "Variable", y = "Percentage", color = "Cluster") +
  theme_minimal() +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1, size = 8),  # Adjust text size and angle
    strip.text.x = element_text(size = 10)  # Adjust facet label size
  ) +
  scale_color_brewer(palette = "Reds") +
  facet_wrap(~ cluster, scales = "free_x") +  # Free scales for x-axis in each facet
  scale_x_reordered(labels = function(x) str_wrap(x, width = 10))  # Wrap long labels



#
#
#
library(ggpubr)
library(rstatix)

df_cont <- df_network %>%
  group_by(cluster) %>%
  select(where(is.numeric)) %>% 
  filter(Dim.1 > -25) %>% 
  pivot_longer(-cluster, names_to = "Variable", values_to = "Value")

grouped_ggbetweenstats(df_cont,
                       x=cluster, 
                       y=Value, 
                       grouping.var=Variable,
                       pairwise.display="s",
                       type="nonparametric",
                       results.subtitle="FALSE",
                       centrality.plotting="FALSE")


# Assuming binary factors are coded as "Yes"/"No" or similar.# Ascluster()suming binary factors are coded as "Yes"/"No" or similar.
df_cont <- df_network %>%
  group_by(cluster) %>%
  select(where(is.numeric)) %>% 
  filter(Dim.1 > -25) %>% 
  pivot_longer(-cluster, names_to = "Variable", values_to = "Value")


# Boxplot with facets
ggplot(df_cont, aes(x = as.factor(cluster), y = Value, fill = as.factor(cluster))) +
  geom_boxplot() +
  facet_wrap(~ Variable, scales = "free") +  # Facet by variable with free y-scales
  labs(title = "Boxplots of Continuous Variables Across Clusters",
       x = "Cluster", y = "Value", fill = "Cluster") +
  theme_minimal() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
  scale_fill_brewer(palette="Reds")



#
#
#
outcomes <- imp %>% 
  mutate(T0_neurorad_lacunar_infarcts_present=ifelse(
    T0_neurorad_number_of_lacunar_infarcts > 0, 1, 0
  ))

outcomes <- cbind(outcomes, cluster = kmeans$cluster)

tbl_summary(
    outcomes,
    include = c(T0_Age, Sex, T0_WMH, T0_neurorad_svd_score, 
                T0_neurorad_lobar_microbleed_present,
                T0_neurorad_non_lobar_microbleed_present,
                T0_neurorad_moderate_severe_pvs,
                T0_neurorad_lacunar_infarcts_present),
    by = cluster, # split table by group
    missing = "no" # don't list missing data separately
  ) |> 
  add_n() |> # add column with total number of non-missing observations
  add_p() |> # test for a difference between groups
  modify_header(label = "**Variable**") |> # update the column header
  bold_labels()
  #as_gt()|>
  #gt::gtsave(filename = tf)

#
#
#
#
library(GGally)

# Plot parallel coordinates
ggparcoord(df_network_scaled_num, 
           columns = c(2:5), 
           groupColumn = 1, 
           scale = "globalminmax",
           alphaLines = 0.8) +
  labs(title = "Parallel Coordinates Plot for Cluster Comparison",
       x = "Variables",
       y = "Standardized Value") +
  theme_minimal(base_size = 15)

#
#
#

ggplot(df_long_num, aes(x = Value, y = reorder(Variable, Value), color = Value)) +
  geom_jitter(alpha = 0.7) +
  facet_wrap(~ cluster, scales = "free_y") +
  scale_color_gradient(low = "purple", high = "orange") +
  labs(title = "Continuous Variables Distribution per Cluster",
       x = "Value",
       y = "Variable") +
  theme_minimal() +
  theme(strip.text = element_text(size = 12, face = "bold"))

df_long_factor <- df_network %>%
  select(cluster, where(is.factor)) %>%
  pivot_longer(cols = -cluster, names_to = "Variable", values_to = "Value")

ggplot(df_long_factor, aes(x = factor(Value), y = reorder(Variable, Value), color = factor(Value))) +
  geom_point(alpha = 0.7) +
  facet_wrap(~ cluster, scales = "free_y") +
  scale_color_viridis_d() +
  labs(title = "Discrete Variables Distribution per Cluster",
       x = "Value",
       y = "Variable") +
  theme_minimal() +
  theme(strip.text = element_text(size = 12, face = "bold"))


#
#
#
#
#
#
#
# Statistical comparisons of most influential variables on Dim 1 and 2

# Create the initial plot with ggbetweenstats
a <- ggbetweenstats(
  data = df_famd, 
  x = cluster, 
  y = Aβ40, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
b <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = creatinine_E1_C6, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")



# Create the initial plot with ggbetweenstats
c <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = cholesterol_totaal_E1_C6, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")



# Create the initial plot with ggbetweenstats
d <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = Aβ42, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
e <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = cholesterol_LDL_E1_C6, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
f <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = Dim.1, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


(a+b+c)/(d+e+f)

#------------------------------------------------------------------------------#

#------------------------------------------------------------------------------#
# Statistical comparisons of most influential variables on Dim 1 and 2

# Create the initial plot with ggbetweenstats
a <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = hemoglobine_E1_C6, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
b <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = hematocriet_E1_C6, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
#c <- ggbarstats(
#  data = imp_famd, 
#  x = cluster, 
#  y = Sex, 
#  type = "nonparametric", 
#  results.subtitle = FALSE, 
#  ggtheme = theme_minimal(),
#)+
#  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
d <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = Dim.3, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
e <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = Dim.7, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
f <- ggbetweenstats(
  data = imp_famd, 
  x = cluster, 
  y = DIASBP, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


(a+b+d)/(e+f)

#------------------------------------------------------------------------------#


df_fu_5$LDL10 <- 10*df_fu_5$T0_cholesterol_LDL_E1_C6
df_fu_5$highLDL <- ifelse(df_fu_5$LDL10 > 35,1,0)

df_fu_5 <- df_fu_5 %>% 
  mutate(
    sysBP = (T0_systolisch_a_E1_C1 + T0_systolisch_b_E1_C1)/2
  ) %>% 
  mutate(
    sysBP140 = ifelse(sysBP >= 140, 1, 0)
  ) %>% 
  mutate(
    diasBP = (T0_Diastolisch_a_E1_C1 + T0_Diastolisch_b_E1_C1)/2
  ) %>% 
  mutate(
    diasBP90 = ifelse(diasBP >= 90, 1, 0)
  ) %>% 
  mutate(
    HT_examination = ifelse(sysBP140==1 | diasBP90 ==1, 1, 0)
  ) %>% 
  mutate(
    Hypertension = ifelse(is.na(HT_examination) & is.na(T0_bloeddruk_E1_C1) &
                            is.na(T0_bloeddruk_medicatie_E1_C1), NA, 0)
  ) %>% 
  mutate(
    Hypertension = ifelse(HT_examination == 1 | T0_bloeddruk_E1_C1 == 1|
                            T0_bloeddruk_medicatie_E1_C1 == 1, 1, 
                          Hypertension)
  ) %>% 
  mutate(
    Currentsmoker = ifelse(T0_roken_E1_C1 == 1, 1, 0)
  ) %>% 
  mutate(
    Diabetes = ifelse(T0_diabetes_E1_C1 == 1|
                        T0_diabetes_E1_C1 == 2|
                        T0_diabetes_E1_C1 == 3, 1, 0)
  ) %>% 
  mutate(
    Hypercholesterolemia = ifelse(T0_cholesterol_E1_C1 == 1|
                                    highLDL==1, 1, 0)
  ) %>% 
  mutate(
    BMI = T0_gewicht_E1_C1/((T0_lengte_E1_C1/100)*(T0_lengte_E1_C1/100))
  ) %>% 
  mutate(
    Obese = ifelse(BMI >= 30, 1, 0)
  ) %>% 
  mutate(
    Ischemicheartdisease = ifelse(T0_hartinfarct_E1_C1 == 1 |
                                    T0_dotter_E1_C1 == 1 |
                                    T0_bypass_E1_C1 ==1, 1, 0)
  ) %>% 
  mutate(
    Tia = ifelse(T0_TIA_E1_C1 == 1, 1, 0)
  ) %>% 
  mutate(
    Stroke = ifelse(T0_CVA_E1_C1 == "1" |
                      T0_CVA_E1_C1 == "2" |
                      T0_CVA_E1_C1 == "3", 1, 0)
  ) %>% 
  mutate(
    Hartfalen = ifelse(T0_patientengroep_E1_C1 == 0, 1, 0)
  ) %>% 
  mutate(
    VCI = ifelse(T0_patientengroep_E1_C1 == 1, 
                 1, 0)
  ) %>% 
  mutate(
    COD = ifelse(T0_patientengroep_E1_C1 == 2, 1, 0)
  ) %>% 
  mutate(
    Controle = ifelse(T0_patientengroep_E1_C1 == 3, 1, 0)
  )

vars = c('patientID', 'T0_Age', 'Sex', 'T0_opleidingsjaren_E1_C1',
         'Hypertension','Hypercholesterolemia',
         'Diabetes', 'Currentsmoker', 'Stroke', 'Obese', 
         'Ischemicheartdisease', 'Tia', 'Hartfalen', 'VCI', 
         'COD', 'Controle')

table.vars <- df_fu_5 %>% 
  dplyr::select(all_of(vars))

table.vars <- table.vars %>% 
  filter(patientID %in% df$patientID)

#remove 1st, 2nd, and 4th row
df <- df[-c(1, 459, 413), ]

df <- df %>% 
  dplyr::select(-cluster)

df <- cbind(df, cluster = kmeans$cluster)

cluster_df <- df %>% 
  dplyr::select(patientID, cluster)

#table.vars <- table.vars[-c(1, 459, 413), ]

table.vars <- table.vars %>% 
  left_join(cluster_df)

vars = c('Age', 'Sex', 'T0_opleidingsjaren_E1_C1',
         'Hypertension','Hypercholesterolemia',
         'Diabetes', 'Currentsmoker', 'Stroke', 'Obese', 
         'Ischemicheartdisease', 'Tia', 'Hartfalen', 'VCI', 
         'COD', 'Controle')

tbl_summary(
  table.vars,
  by = cluster, # split table by group
  missing = "no" # don't list missing data separately
) |> 
  add_n() |> # add column with total number of non-missing observations
  add_p() |>
  add_q() |> # test for a difference between groups
  modify_header(label = "**Variable**") |> # update the column header
  bold_labels()
#as_gt()|>
#gt::gtsave(filename = tf)
table2

#------------------------------------------------------------------------------#


# Calculate mean and IQR values of top contributing variables for each cluster
top_vars <- unique(top_contrib_df$variable)
cluster_stats <- imp_famd %>%
  dplyr::select(all_of(top_vars), cluster) %>%
  group_by(cluster) %>%
  summarise(across(where(is.numeric), list(median = ~ median(.x, na.rm = TRUE),
                                      IQR = ~ IQR(.x, na.rm = TRUE)), 
                   .names = "{.col}_{.fn}"))


tf <- tempfile("table_cluster_outcome", 
               tmpdir = "L:/laupodteam/AIOS/Malin/projects/02_HARTBREIN/04_NETWORK",
               fileext = ".docx")


df <- df %>% 
  mutate(T0_neurorad_lacunar_infarcts_present=ifelse(
    T0_neurorad_number_of_lacunar_infarcts > 0, 1, 0
  ))

tbl_summary(
    df,
    include = c(T0_Age, Sex, T0_WMH, T0_neurorad_svd_score, 
                T0_neurorad_lobar_microbleed_present,
                T0_neurorad_non_lobar_microbleed_present,
                T0_neurorad_moderate_severe_pvs,
                T0_neurorad_lacunar_infarcts_present),
    by = cluster, # split table by group
    missing = "no" # don't list missing data separately
  ) |> 
  add_n() |> # add column with total number of non-missing observations
  add_p() |> # test for a difference between groups
  modify_header(label = "**Variable**") |> # update the column header
  bold_labels()
  #as_gt()|>
  #gt::gtsave(filename = tf)

# Create the initial plot with ggbetweenstats
ggbetweenstats(
  data = df, 
  x = cluster, 
  y = T0_WMH, 
  type = "nonparametric", 
  results.subtitle = FALSE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_color_brewer(palette="Reds")


# Create the initial plot with ggbetweenstats
p1 <- ggbarstats(
  data = df, 
  x = T0_neurorad_non_lobar_microbleed_present, 
  y = cluster, 
  type = "nonparametric", 
  results.subtitle = TRUE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_fill_manual(values = 
                                c("#cb181d", "darkred"))



# Create the initial plot with ggbetweenstats
p2 <- ggbarstats(
  data = df, 
  x = T0_neurorad_lobar_microbleed_present, 
  y = cluster, 
  type = "nonparametric", 
  results.subtitle = TRUE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_fill_manual(values = 
                                c("#cb181d", "darkred"))

# Create the initial plot with ggbetweenstats
p3 <- ggbarstats(
  data = df, 
  x = T0_neurorad_moderate_severe_pvs, 
  y = cluster, 
  type = "nonparametric", 
  results.subtitle = TRUE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_fill_manual(values = 
                                c("#cb181d", "darkred"))

# Create the initial plot with ggbetweenstats
p4 <- ggbarstats(
  data = df, 
  x = T0_neurorad_lacunar_infarcts_present, 
  y = cluster, 
  type = "nonparametric", 
  results.subtitle = TRUE, 
  ggtheme = theme_minimal(),
)+
  ggplot2::scale_fill_manual(values = 
                                c("#cb181d", "darkred"))


(p1+p2)/(p3+p4)

# Create the initi

top_vars_dim1 <- top_contrib_df %>% 
  filter(dimension=="Dim.1")
  
tf <- tempfile("dim1_vars", 
               tmpdir = "L:/laupodteam/AIOS/Malin/projects/02_HARTBREIN/04_NETWORK",
               fileext = ".docx")
tbl_summary(
  imp_famd,
  include = all_of(top_vars_dim1$variable),
  by = cluster, # split table by group
  missing = "no" # don't list missing data separately
) |> 
  add_n() |> # add column with total number of non-missing observations
  add_p() |> # test for a difference between groups
  add_q() |> # add column with total number of non-missing observations
  modify_header(label = "**Variable**") |> # update the column header
  bold_labels()|> 
  as_gt() |> 
  gt::gtsave(filename = tf)

top_vars_dim2 <- top_contrib_df %>% 
  filter(dimension=="Dim.2")

tf <- tempfile("dim2_vars", 
               tmpdir = "L:/laupodteam/AIOS/Malin/projects/02_HARTBREIN/04_NETWORK",
               fileext = ".docx")

tbl_summary(
  imp_famd,
  include = all_of(top_vars_dim2$variable),
  by = cluster, # split table by group
  missing = "no" # don't list missing data separatel y
) |> 
  add_n() |> # add column with total number of non-missing observations
  add_p() |> # test for a difference between groups
  add_q() |> # add column with total number of non-missing observations
  modify_header(label = "**Variable**") |> # update the column header
  bold_labels()|>
  as_gt() |> 
  gt::gtsave(filename = tf)


# Data filtering and transformation for survival analysis
kmeans_clusters <- kmeans_clusters %>%
  mutate(Time = ifelse(Time > 5, 5, Time), 
         CDR_INCR = as.numeric(as.character(CDR_INCR)))

# Survival analysis
fit <- survfit(Surv(Time_MACE, Event_MACE) ~ cluster, data = df)
summary(fit)


# Survival analysis
fit <- coxph(Surv(Time_MACE, Event_MACE) ~ cluster, data = df)
summary(fit)

# Survival analysis
fit <- coxph(Surv(Time_Stroke, Event_Stroke) ~ cluster, data = df)
summary(fit)

# Survival plot
ggsurvplot(fit, pval = TRUE, conf.int = TRUE, risk.table = TRUE, 
           risk.table.col = "strata", linetype = "strata", 
           surv.median.line = "hv", ggtheme = theme_pubclean(), palette="Reds"
)


fit <- pairwise_survdiff(Surv(MACE_Time, Event_MACE) ~ cluster, data = kmeans_clusters,
                         p.adjust.method = "fdr")


# Survival analysis
fit <- survfit(Surv(CDR_Time, CDR_INCR) ~ cluster, data = kmeans_clusters)
print(fit)


# Survival plot
ggsurvplot(fit, pval = TRUE, conf.int = TRUE, risk.table = TRUE, 
           risk.table.col = "strata", linetype = "strata", 
           surv.median.line = "hv", ggtheme = theme_pubclean(), palette="Reds"
)



#
#
#
#
#
