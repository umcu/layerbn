library(haven)
library(dplyr)
library(fastDummies)
library(ggstatsplot)
library(ClustOfVar)
library(caret)
library(randomcoloR)
library(ape)
library(corrplot)
library(mice)
library(tibble)
library(tidyr)
library(caret)
library(lubridate)
library(tidyverse)
library(FactoMineR)
library(factoextra)
library(ggpubr)
library(gtsummary)
library(mclust) # For Gaussian Mixture Models
library(gtsummary) # For summarizing tables
library(ggeffects) # For exploring interactions
library(dbscan)
library(plotly)
library(naniar)
library(networkD3)
library(easyalluvial)
library(viridis)
library(ggsankey)
library(readxl)
library(arrow)
library(stringr)
library(RiskScorescvd)
library(tableone)

setwd("<PROJECT_ROOT>/04_NETWORK")

df_bl <- read_sav("./data/df.sav")
#df_fu_2 <- read_sav("./data/fu.sav")
df_fu_5 <- read_sav("./data/fu_2.sav")
cs_1 <- read_excel("<PROJECT_ROOT>/01_SVD/data/clean/compound_score.xlsx")
cs_2 <- read.csv("<PROJECT_ROOT>/02_CBF/data/clean/cs_cleaned_final.csv", sep=";", dec=",")

# ---------------------------------------------------------------------------- #
cs_1$patientID <- as.numeric(cs_1$patientID)
cs_2$patientID <- as.numeric(cs_2$patientID)

df_fu_5 <- df_fu_5 %>% 
  left_join(cs_1) %>% 
  left_join(cs_2)

# ---------------------------------------------------------------------------- #

# Create outcome variables

df_outcomes <- df_fu_5 %>% 
  select(patientID, T0_datumbaselinebezoek_E1_C1, T2_datumfu2bezoek_E3_C10, 
         T4_datum_tel_int_E4_C12, T0_CDR_E1_C1,
         T2_CDR_E3_C10, T2_CDR_E3_C11, T4_CDR_E4_C12, 
         T2_reden_geen_deelname_E3_C11, T4_reden_geen_deelname_E4_C12,
         
         T0_CVA_E1_C1, T0_hartinfarct_E1_C1, T0_dotter_E1_C1, 
         T0_dotter_stent_E1_C1, T0_bypass_E1_C1, T0_etalagebenen_E1_C1,
         T0_TIA_E1_C1,
         
         T2_CVA_E3_C10, T2_CVA_E3_C11, T2_CVA_datum_E3_C10, T2_CVA_datum_E3_C11,
         T2_CVA_type_E3_C10, T2_CVA_type_E3_C11, T2_CVA_type_overig_E3_C10,
         
         T2_cardio_E3_C10, T2_cardio_E3_C11, T2_cardio_type_E3_C10,
         T2_cardio_type_E3_C11,
         T2_cardio_type_overig_E3_C10, T2_cardio_type_overig_E3_C11,
         T2_cardio_datum_E3_C10, T2_cardio_datum_E3_C11, 
         T2_cardio_type_overig_E3_C11,
         
         T2_1_datum_overlijden_E3_C11,T2_1_oorzaak_overlijden_E3_C11, 
         
         T4_CVA_E4_C12, T4_CVA_datum_E4_C12,T4_CVA_type_overig_E4_C12,
         T4_cardio_E4_C12, T4_cardio_type_E4_C12, T4_cardio_type_overig_E4_C12,
         T4_cardio_datum_E4_C12,
         
         T4_1_datum_overlijden_E4_C12, T4_1_oorzaak_overlijden_E4_C12
        )

# Clean

df_outcomes <- df_outcomes %>% 
  mutate(
    across(contains("datum"), ymd),
    T4_CDR_E4_C12 = as.numeric(T4_CDR_E4_C12),
    T2_CDR_E3_C10 = ifelse(is.na(T2_CDR_E3_C10), T2_CDR_E3_C11, T2_CDR_E3_C10)
  ) %>% 
  dplyr::select(-T2_CDR_E3_C11) %>%
  rename(T0_CDR = T0_CDR_E1_C1, T2_CDR = T2_CDR_E3_C10, 
         T4_CDR = T4_CDR_E4_C12) %>%
  mutate(
    across(c(T4_CDR, T2_CDR), ~case_when(
      . == 1 ~ 0.5,
      . == 2 ~ 1,
      . == 3 ~ 2,
      . == 4 ~ 3,
      TRUE ~ .
    ))
  )


df_outcomes <- df_outcomes %>%
  mutate(
    T2_CVA = coalesce(T2_CVA_E3_C10, T2_CVA_E3_C11),
    T2_CVA_type = coalesce(T2_CVA_type_E3_C10, T2_CVA_type_E3_C11),
    T2_CVA_datum = coalesce(T2_CVA_datum_E3_C10, T2_CVA_datum_E3_C11),
    T2_cardio = coalesce(T2_cardio_E3_C10, T2_cardio_E3_C11),
    T2_cardio_type = coalesce(T2_cardio_type_E3_C10, T2_cardio_type_E3_C11),
    T2_cardio_type_overig = coalesce(T2_cardio_type_overig_E3_C10, 
                                     T2_cardio_type_overig_E3_C11),
    T2_cardio_datum = coalesce(T2_cardio_datum_E3_C10, T2_cardio_datum_E3_C11)
  ) %>%
  dplyr::select(-T2_CVA_E3_C10, -T2_CVA_E3_C11,
                -T2_CVA_type_E3_C10, -T2_CVA_type_E3_C11,
                -T2_CVA_datum_E3_C10, -T2_CVA_datum_E3_C11,
                -T2_cardio_E3_C10, -T2_cardio_E3_C11,
                -T2_cardio_type_E3_C10, -T2_cardio_type_E3_C11,
                -T2_cardio_type_overig_E3_C10,-T2_cardio_type_overig_E3_C11,
                -T2_cardio_datum_E3_C10, -T2_cardio_datum_E3_C11
                # Continue with the rest of the columns that were coalesced
  ) %>% 
  # Ensure unique column names
  rename_with(~make.unique(.), .cols = everything())

names(df_outcomes) <- gsub("_E3_C10", "", names(df_outcomes))
names(df_outcomes) <- gsub("_E3_C11", "", names(df_outcomes))
names(df_outcomes) <- gsub("_E4_C12", "", names(df_outcomes))

# ---------------------------------------------------------------------------- #

# STROKE 

df_outcomes$T0_CVA_E1_C1 <- as.numeric(as.character(df_outcomes$T0_CVA_E1_C1))

df_outcomes <- df_outcomes %>%
  mutate(
    T0_Event_Stroke = ifelse(
      (T0_CVA_E1_C1==1 | T0_CVA_E1_C1==2 | T0_CVA_E1_C1==3), 1,0
    ),
    T2_Event_Stroke = ifelse(
      (T2_CVA==1 | T2_CVA==2|
      grepl("CVA", T2_1_oorzaak_overlijden, 
            ignore.case = TRUE) |
        grepl("herseninfarct", T2_1_oorzaak_overlijden, 
              ignore.case = TRUE) |
        grepl("hersenbloeding", T2_1_oorzaak_overlijden, 
              ignore.case = TRUE)), 1, 0),
    T4_Event_Stroke = ifelse((
      T4_CVA == 1 | T4_CVA==2|
        grepl("CVA", T4_1_oorzaak_overlijden, ignore.case = TRUE) |
        grepl("herseninfarct", T4_1_oorzaak_overlijden, 
              ignore.case = TRUE)|
        grepl("hersenbloeding", T4_1_oorzaak_overlijden, 
            ignore.case = TRUE)),1, 0),
    Event_Stroke = ifelse(
      T2_Event_Stroke == 1 | T4_Event_Stroke == 1, 
      1, 0)
    )

# ---------------------------------------------------------------------------- #

# MACE 
df_outcomes <- df_outcomes %>%
  mutate(
    T0_Event_MACE = case_when(
      T0_CVA_E1_C1 %in% c(1, 2, 3) |
        T0_hartinfarct_E1_C1 == 1 |
        T0_dotter_E1_C1 == 1 |
        T0_dotter_stent_E1_C1 == 1 |
        T0_bypass_E1_C1 == 1 |
        T0_etalagebenen_E1_C1 == 1 ~ 1,
      
      !is.na(T0_CVA_E1_C1) | !is.na(T0_hartinfarct_E1_C1) |
        !is.na(T0_dotter_E1_C1) | !is.na(T0_dotter_stent_E1_C1) |
        !is.na(T0_bypass_E1_C1) | !is.na(T0_etalagebenen_E1_C1) ~ 0,
      
      TRUE ~ NA_real_
    ),
    T2_Event_MACE = ifelse(
      (T2_CVA == 1|T2_CVA==2|T2_cardio==1|T2_cardio==2|
         grepl("myocardinfarct|hersenbloeding|aneurysma", 
               T2_1_oorzaak_overlijden, ignore.case=TRUE)), 
      1, 0),
    T4_Event_MACE = ifelse(
      (T4_CVA == 1|T4_CVA==2|
         T4_cardio==1|T4_cardio==2|        
         grepl("CVA|herseninfarct|vaatlijden|subarachnoïdale|hartstilstand
               |cardiac arrest|decompensatio cordis|hartfalen|
               hersenbloeding|vasculaire|myocardinfarct", 
               T4_1_oorzaak_overlijden,
               ignore.case = TRUE)),
      1, 0),
    OUTCOME_MACE = ifelse(
      T2_Event_MACE == 1 | T4_Event_MACE == 1, 
      1, 0
    )
    )

# ---------------------------------------------------------------------------- #

# COGNITIVE DECLINE
df_outcomes$T2_dropout_reason <- factor(df_outcomes$T2_reden_geen_deelname, 
                               levels = 0:5, labels = c("Untraceable", 
                                                        "Deceased", 
                                                        "Too Ill",
                                                        "Moved to Nursing Home", 
                                                        "Refusal", 
                                                        "Other"))

df_outcomes$T4_dropout_reason <- factor(df_outcomes$T4_reden_geen_deelname, 
                               levels = 0:5, 
                               labels = c("Untraceable", 
                                          "Deceased", 
                                          "Too Ill",
                                          "Moved to Nursing Home", 
                                          "Refusal", 
                                          "Other"))


df_outcomes$T2_cognitive_dropout <- with(df_outcomes, T2_dropout_reason %in% 
                                           c("Moved to Nursing Home"))

df_outcomes$T4_cognitive_dropout <- with(df_outcomes, T4_dropout_reason %in% 
                                  c("Moved to Nursing Home"))

df_outcomes <- df_outcomes %>% 
  mutate(OUTCOME_CDR_INCREASE = ifelse(T2_CDR > T0_CDR | T4_CDR > T0_CDR | T4_CDR > T2_CDR |
                             T2_cognitive_dropout == TRUE | 
                             T4_cognitive_dropout == TRUE, 1, 0)) %>% 
  mutate(OUTCOME_CDR_INCREASE = ifelse(
    (is.na(OUTCOME_CDR_INCREASE) & (T4_CDR > T0_CDR)), 1, OUTCOME_CDR_INCREASE
  ),
  CDR_INCR = ifelse(
    (is.na(OUTCOME_CDR_INCREASE) & (T2_CDR > T0_CDR)), 1, OUTCOME_CDR_INCREASE
  )
  )

# ---------------------------------------------------------------------------- #

# OUTCOMES 

df_outcomes_sub <- df_outcomes %>% 
  select(patientID, T0_CDR, OUTCOME_MACE, OUTCOME_CDR_INCREASE)

# ---------------------------------------------------------------------------- #

df_outcomes <- df_outcomes %>%
  mutate(
    T2_dropout_reason = as.character(T2_dropout_reason),
    T4_dropout_reason = as.character(T4_dropout_reason)
  ) %>%
  mutate(
    T2_dropout_reason = coalesce(T2_dropout_reason, "No dropout"),
    T4_dropout_reason = coalesce(T4_dropout_reason, "No dropout")
  ) %>%
  mutate(
    T2_dropout_reason = factor(T2_dropout_reason, 
                               levels = c(levels(df_outcomes$T2_dropout_reason), 
                                          "No dropout")),
    T4_dropout_reason = factor(T4_dropout_reason, 
                               levels = c(levels(df_outcomes$T4_dropout_reason), 
                                          "No dropout"))
  )

# ---------------------------------------------------------------------------- #

# PLOT FLOW CDR INCREASE 

df_sankey <- df_outcomes %>% 
  make_long(T0_CDR, T2_dropout_reason, T2_CDR,T4_dropout_reason, T4_CDR) 

df_clean <- df_outcomes %>%
  mutate(
    T0_CDR = factor(T0_CDR),
    T2_dropout_reason = factor(T2_dropout_reason),
    T2_CDR = factor(T2_CDR),
    T4_dropout_reason = factor(T4_dropout_reason),
    T4_CDR = factor(T4_CDR)
  )

# Helper function to reorder factor levels based on frequencies
reorder_levels_by_freq <- function(df, vars) {
  df_clean %>%
    mutate(across(all_of(vars), ~ fct_infreq(as.factor(.x))))
}

df_clean <- reorder_levels_by_freq(
  df_clean,
  vars = c("T0_CDR", "T2_dropout_reason", "T2_CDR", "T4_dropout_reason", "T4_CDR")
)

# Lump small categories first
df_clean <- df_clean %>%
  mutate(
    T0_CDR = factor(T0_CDR, levels = c("0", "0.5", "1", "2", "3")),
    #T2_dropout_reason = fct_lump_min(factor(T2_dropout_reason), min = 10),
    T2_CDR = factor(T2_CDR, levels = c("0", "0.5", "1", "2", "3")),
    #T4_dropout_reason = fct_lump_min(factor(T4_dropout_reason), min = 10),
    T4_CDR = factor(T4_CDR, levels = c("0", "0.5", "1", "2", "3"))
  )

# Aggregate similar paths
df_aggregated <- df_clean %>%
  group_by(T0_CDR, T2_dropout_reason, T2_CDR, T4_dropout_reason, T4_CDR) %>%
  summarise(count = n(), .groups = 'drop')  %>%
  filter(count >= 5)   # Keep only paths with at least 5 patients

# Now expand back into repeated rows for plotting
df_plot <- df_aggregated %>%
  uncount(count)

colors <- c(
  "#1B0C41",
  "#781C6D",
  "#F1605D"  
)
# Now plot
p <- alluvial_wide(
  df_plot,
  fill_by = 'first_variable',
  NA_label = 'Missing',
  col_vector_flow = colors,
  col_vector_value = colors
  )

p +
  theme_minimal() +
  theme(
    legend.position = "none",
    plot.title = element_text(hjust = .5),
    axis.text.y = element_text(size = 8)
  ) +
  ggtitle("Clinical Dementia Rating (CDR) shift over time") +
  #scale_fill_viridis_d(option = "F", alpha = 0.95) +
  guides(fill = guide_legend(override.aes = list(size = 30)))  # Thicker lines

# ---------------------------------------------------------------------------- #

# PLOT FLOW MACE

df_sankey <- df_outcomes %>% 
  make_long(T0_Event_MACE, T2_dropout_reason, T2_Event_MACE,  
            T4_dropout_reason, T4_Event_MACE) 

df_clean <- df_outcomes %>%
  mutate(
    T0_Event_MACE = factor(T0_Event_MACE),
    T2_dropout_reason = factor(T2_dropout_reason),
    T2_Event_MACE = factor(T2_Event_MACE),
    T4_dropout_reason = factor(T4_dropout_reason),
    T4_Event_MACE = factor(T4_Event_MACE)
  )

# Helper function to reorder factor levels based on frequencies
reorder_levels_by_freq <- function(df, vars) {
  df_clean %>%
    mutate(across(all_of(vars), ~ fct_infreq(as.factor(.x))))
}

df_clean <- reorder_levels_by_freq(
  df_clean,
  vars = c("T0_Event_MACE", "T2_dropout_reason", "T2_Event_MACE", 
           "T4_dropout_reason", "T4_Event_MACE")
)

# Aggregate similar paths
df_aggregated <- df_clean %>%
  group_by(T0_Event_MACE, T2_dropout_reason, T2_Event_MACE, 
           T4_dropout_reason, T4_Event_MACE) %>%
  summarise(count = n(), .groups = 'drop')  %>%
  filter(count >= 5)   # Keep only paths with at least 5 patients

# Now expand back into repeated rows for plotting
df_plot <- df_aggregated %>%
  uncount(count)

colors <- c(
  "#1B0C41",
  "#781C6D",
  "#F1605D"  
)
# Now plot
p <- alluvial_wide(
  df_plot,
  fill_by = 'first_variable',
  NA_label = 'Missing',
  col_vector_flow = colors,
  col_vector_value = colors
)

p +
  theme_minimal() +
  theme(
    legend.position = "none",
    plot.title = element_text(hjust = .5),
    axis.text.y = element_text(size = 8)
  ) +
  ggtitle("Major Adverse Cardiovascular Events (MACE) over time") +
  #scale_fill_viridis_d(option = "F", alpha = 0.95) +
  guides(fill = guide_legend(override.aes = list(size = 30)))  # Thicker lines


# ---------------------------------------------------------------------------- #

saveRDS(df_outcomes,"./data/outcomes_meta.RDS")

df_outcomes$T2_dropout_reason <- as.character(df_outcomes$T2_dropout_reason)
df_outcomes$T4_dropout_reason <- as.character(df_outcomes$T4_dropout_reason)


df_outcomes <- df_outcomes %>% 
  mutate(OUTCOME_CDR_INCREASE = ifelse(OUTCOME_CDR_INCREASE == "0", "No", 
                                       OUTCOME_CDR_INCREASE),
         OUTCOME_CDR_INCREASE = ifelse(OUTCOME_CDR_INCREASE == "1", "Yes",
                                       OUTCOME_CDR_INCREASE),
         OUTCOME_CDR_INCREASE = ifelse(is.na(OUTCOME_CDR_INCREASE), "Unobserved",
                                       OUTCOME_CDR_INCREASE))

df_outcomes <- df_outcomes %>% 
  mutate(OUTCOME_MACE = ifelse(OUTCOME_MACE == "0", "No", 
                                       OUTCOME_MACE),
         OUTCOME_MACE = ifelse(OUTCOME_MACE == "1", "Yes",
                                       OUTCOME_MACE),
         OUTCOME_MACE = ifelse(is.na(OUTCOME_MACE), "Unobserved",
                              OUTCOME_MACE))

df_outcomes <- df_outcomes %>%
  mutate(
    T4_dropout_reason = case_when(
      T4_dropout_reason == "No dropout" & OUTCOME_CDR_INCREASE == "Unobserved" ~ T2_dropout_reason,
      T4_dropout_reason == "No dropout" & OUTCOME_MACE == "Unobserved" ~ T2_dropout_reason,
      TRUE ~ T4_dropout_reason
    )
  )
# Fill missing OUTCOME_CDR_INCREASE with T4_dropout_reason
df_outcomes_sub <- df_outcomes %>% 
  select(patientID, T4_dropout_reason, OUTCOME_MACE, OUTCOME_CDR_INCREASE)

saveRDS(df_outcomes_sub,"./data/outcomes.RDS")

# ---------------------------------------------------------------------------- #

bn_vars <- read_excel("<HOME>/Library/CloudStorage/OneDrive-UMCUtrecht/BAYESIAN_NETWORK/HBC_CODEBOOK_LABELS.xlsx", sheet = "Items")

# ---------------------------------------------------------------------------- #

bn_vars_filter <- bn_vars %>% 
  filter(!is.na(LAYER)) %>% 
  select(LAYER, `VARIABLE NAME`)

# Example: manual extra variables you want to include
extra_vars <- c("patientID", "T0_patientengroep_E1_C1", "Sex", "T0_Age",
                "T0_pTau181", "T0_NfL", "T0_GFAP", "T0_Aβ40", "T0_Aβ42") 

# 1. Get the variable names from df_bl
all_cols <- names(df_fu_5)

# 2. Remove suffix like _E1_C1 to get base names
# (Assuming suffix always follows pattern: _E<number>_C<number>)
base_names <- sub("_E[0-9]+_C[0-9]+$", "", all_cols)

# 3. Keep columns whose base names are in bn_vars$VARIABLE_NAME
matched_cols <- all_cols[base_names %in% bn_vars_filter$`VARIABLE NAME`]

# 4. Add extra columns manually
final_cols <- unique(c(extra_vars, matched_cols))

# 5. Subset the original dataframe
df_subset <- df_fu_5[, final_cols, drop = FALSE]

# ---------------------------------------------------------------------------- #

# Create features 
df_subset <- df_subset %>% 
  mutate(T0_SYS_BP = (T0_systolisch_a_E1_C1 + T0_systolisch_b_E1_C1) / 2,
         T0_DIAS_BP = (T0_Diastolisch_a_E1_C1 + T0_Diastolisch_b_E1_C1) / 2,
         T0_HV_ICV = ((T0_i_ic_gm_Hippocampus_left_volume_ml + 
                         T0_i_ic_gm_Hippocampus_right_volume_ml) / 
                        T0_q_ic_tissue_total_intracranial_volume_ml) * 100,
         T0_TBV_ICV = (T0_q_ic_tissue_total_brain_volume_ml / 
                         T0_q_ic_tissue_total_intracranial_volume_ml) *100,
         T0_CBF =  T0_i_ic_cbf_GrayMatter_mean_mL100gmin,
         T0_roken_hoeveel_jaar_a_E1_C1 = ifelse(is.na(T0_roken_hoeveel_jaar_a_E1_C1) & 
                                                  !is.na(T0_roken_hoeveel_jaar_b_E1_C1),
                                                T0_roken_hoeveel_jaar_b_E1_C1, 
                                                T0_roken_hoeveel_jaar_a_E1_C1),
         T0_roken_hoeveel_jaar_a_E1_C1 = ifelse(is.na(T0_roken_hoeveel_jaar_a_E1_C1),
                                                0, T0_roken_hoeveel_jaar_a_E1_C1),
         T0_roken_hoeveel_per_dag_a_E1_C1 = ifelse(is.na(T0_roken_hoeveel_per_dag_a_E1_C1) &
                                                     !is.na(T0_roken_hoeveel_per_dag_b_E1_C1),
                                                   T0_roken_hoeveel_per_dag_b_E1_C1,
                                                   T0_roken_hoeveel_per_dag_a_E1_C1),
         T0_roken_hoeveel_per_dag_a_E1_C1 = ifelse(is.na(T0_roken_hoeveel_per_dag_a_E1_C1),
                                                   0, T0_roken_hoeveel_per_dag_a_E1_C1),
         T0_CAD = ifelse((T0_bypass_E1_C1==1 | T0_dotter_E1_C1==1 | T0_hartinfarct_E1_C1 ==1), 1, 0),
         T0_PAD = ifelse((T0_etalagebenen_E1_C1 == 1), 1, 0)) %>% 
  select(-T0_roken_hoeveel_jaar_b_E1_C1, -T0_roken_hoeveel_per_dag_b_E1_C1,
         -T0_etalagebenen_E1_C1, -T0_hartinfarct_E1_C1, -T0_bypass_E1_C1, 
         -T0_dotter_E1_C1)

df_subset <- df_subset %>% 
  mutate(MACE = ifelse(T0_CAD==1 | T0_PAD==1, 1, 0))

df_subset <- df_subset %>% 
  select(-T0_PAD, -T0_CAD)

# ---------------------------------------------------------------------------- #
df_final <- df_subset %>% 
  left_join(df_outcomes_sub)

bn_vars_filter$`VARIABLE NAME` <- gsub("T0_", "", 
                                       bn_vars_filter$`VARIABLE NAME`)

names(df_final) <- gsub("_E1_C1", "", names(df_final))
names(df_final) <- gsub("_E1_C6", "", names(df_final))
names(df_final) <- gsub("T0_", "", names(df_final))

# ---------------------------------------------------------------------------- #

names(df_final) <- gsub("β", "B", names(df_final))

names(df_final) <- toupper(names(df_final))
bn_vars_filter$`VARIABLE NAME` <- toupper(bn_vars_filter$`VARIABLE NAME`)

bn_vars_filter <- bn_vars_filter %>% 
  add_row(LAYER='L2 – Cardiovascular risk factors', 
          `VARIABLE NAME`="SYS_BP") %>%   
  add_row(LAYER='L2 – Cardiovascular risk factors', 
          `VARIABLE NAME`="DIAS_BP") %>%  
  add_row(LAYER='L5 - Imaging markers of neurovascular damage',
          `VARIABLE NAME`="HV_ICV") %>% 
  add_row(LAYER='L5 - Imaging markers of neurovascular damage',
          `VARIABLE NAME`="TBV_ICV") %>% 
  add_row(LAYER='L4 – Potential disease process markers',
          `VARIABLE NAME`="CBF") %>% 
  add_row(LAYER='L8 – Outcomes',
          `VARIABLE NAME`="OUTCOME_CDR_INCREASE") %>% 
  add_row(LAYER='L8 – Outcomes',
          `VARIABLE NAME`="T4_DROPOUT_REASON") %>% 
  add_row(LAYER='L8 – Outcomes',
          `VARIABLE NAME`="OUTCOME_MACE") %>% 
  add_row(LAYER="L0 – Unmodifiable demographics",
          `VARIABLE NAME`="AGE") %>% 
  add_row(LAYER="L0 – Unmodifiable demographics",
          `VARIABLE NAME`="SEX") %>%
  add_row(LAYER="L4 – Potential disease process markers",
          `VARIABLE NAME`="PTAU181") %>% 
  add_row(LAYER="L4 – Potential disease process markers",
          `VARIABLE NAME`="NFL") %>%
  add_row(LAYER="L4 – Potential disease process markers",
          `VARIABLE NAME`="GFAP") %>% 
  add_row(LAYER="L6 – Current and previous cardiovascular diagnoses / Vascular interventions",
          `VARIABLE NAME`="PATIENTENGROEP") %>% 
  add_row(LAYER="L4 – Potential disease process markers",
          `VARIABLE NAME`="AB40")%>% 
  add_row(LAYER="L4 – Potential disease process markers",
          `VARIABLE NAME`="AB42")%>% 
  add_row(LAYER="L6 – Current and previous cardiovascular diagnoses / Vascular interventions",
          `VARIABLE NAME`="MACE") %>% 
  add_row(LAYER="L2 – Cardiovascular risk factors",
          `VARIABLE NAME`="SCORE_2")

# ---------------------------------------------------------------------------- #

# Convert all haven-labelled variables to factors
df_clean <- df_final %>%
  mutate(across(where(haven::is.labelled), haven::as_factor))

names(df_clean) <- gsub("β", "B", names(df_clean))

df_clean <- df_clean %>%
  mutate(across(
    where(is.factor),
    ~ factor(str_to_sentence(as.character(.)))
  ))


df_clean$NEURORAD_SVD_SCORE <- 
  as.factor(df_clean$NEURORAD_SVD_SCORE)

df_clean$CDR <- as.factor(df_clean$CDR)

df_clean <- df_clean %>% 
  select(-Q_IC_TISSUE_TOTAL_INTRACRANIAL_VOLUME_ML, 
         -Q_IC_TISSUE_TOTAL_BRAIN_VOLUME_ML,
         -I_IC_CBF_GRAYMATTER_MEAN_ML100GMIN,
         -DIASTOLISCH_A, 
         -DIASTOLISCH_B,
         -SYSTOLISCH_A,
         -SYSTOLISCH_B)

df_clean <- df_clean %>% 
  select(-PATIENTID)

# ---------------------------------------------------------------------------- #

# Calculate SCORE

df_clean_score <- df_clean %>%
  mutate(
    SEX_SCORE = ifelse(is.na(SEX), NA, 
                       ifelse(SEX == "Female", "female", "male")),
    ROKEN_SCORE = ifelse(is.na(ROKEN), NA, 
                         ifelse(ROKEN == "Ja", 1, 0)),
    DIABETES_SCORE = ifelse(is.na(DIABETES), NA, 
                            ifelse(DIABETES == "Nee", 0, 1))
  )

df_clean_score <- df_clean_score %>%
  rowwise() %>%
  mutate(SCORE_2 = SCORE2(
    Risk.region = "Low",
    Age = AGE,
    Gender = SEX_SCORE,
    smoker = ROKEN_SCORE,
    systolic.bp = SYS_BP,
    diabetes = DIABETES_SCORE,
    total.chol = CHOLESTEROL_TOTAAL,
    total.hdl = CHOLESTEROL_HDL,
    classify = FALSE
  )) %>% 
  ungroup()

# ---------------------------------------------------------------------------- #

table1(~AGE + SYS_BP + TIA, 
       DIABETES_SCORE | SEX_SCORE, df_clean_score)

vars <- c("AGE", "SEX", "DIABETES", "ROKEN","SYS_BP", "CHOLESTEROL_LDL",
          "SCORE_2","BLOEDDRUK_MEDICATIE", "TIA", "CVA", "PATIENTENGROEP")
tableOne <- CreateTableOne(vars = vars, data = df_clean_score)

print(tableOne, nonnormal = c("AGE","SYS_BP", "CHOLESTEROL_LDL", "SCORE_2"),
      exact = c("SEX","ROKEN_SCORE", "BLOEDDRUK_MEDICATIE", 
                "TIA", "CVA", "PATIENTENGROEP"), smd = TRUE,
      quote=TRUE)

# ---------------------------------------------------------------------------- #


df_clean_reduced <- df_clean_score %>% 
  select(AGE, SEX, PTAU181, NFL, GFAP, AB40, AB42,
         MMSE_TOTAAL, STARKSTEIN, CDR, CVA, NEURORAD_SVD_SCORE, 
         BCS_1, BCS_2, HV_ICV, TBV_ICV, CBF, MACE, OUTCOME_MACE, 
         OUTCOME_CDR_INCREASE, T4_DROPOUT_REASON, SCORE_2, PATIENTENGROEP)

bn_vars_filter_2 <- bn_vars_filter %>% 
  filter(`VARIABLE NAME` %in% names(df_clean_reduced))

# Maak een named vector met de Nederlandse naam als name en de Engelse naam als waarde
# Maak een vector met mapping van oude naar nieuwe namen
name_mapping <- c(
  "MMSE_TOTAAL" = "MINI MENTAL STATE EXAMINATION",
  "STARKSTEIN" = "STARKSTEIN SCORE",
  "CDR" = "BASELINE CDR",
  "CVA" = "STROKE HISTORY",
  "BCS_1" = "BIOMARKER SCORE 1",
  "BCS_2" = "BIOMARKER SCORE 2",
  "NEURORAD_SVD_SCORE" = "SMALL VESSEL DISEASE SCORE",
  "HV_ICV" = "HIPPOCAMPUS/INTRACRANIAL VOLUME",
  "TBV_ICV" = "BRAIN/INTRACRANIAL VOLUME",
  "CBF" = "CEREBRAL BLOOD FLOW",
  "EVENT_MACE" = "OUTCOME_MACE",
  "CDR_INCR" = "OUTCOME_CDR_INCREASE",
  "T4_DROPOUT_REASON" = "DROPOUT REASON",
  "AGE" = "AGE",
  "SEX" = "SEX",
  "PTAU181" = "PTAU181",
  "NFL" = "NFL",
  "GFAP" = "GFAP",
  "PATIENTENGROEP" = "PATIENT GROUP",
  "MACE" = "ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY",
  "SCORE_2" = "VASCULAR RISK SCORE"
)

# Pas de mapping toe op de kolom VARIABLE_NAME
bn_vars_filter_2 <- bn_vars_filter_2 %>%
  mutate(`VARIABLE NAME` = recode(`VARIABLE NAME`, !!!name_mapping))

#write_parquet(df_with_missing_indicators, "./data/df_missing_ind.parquet")
write_parquet(df_clean_reduced, "./data/df.parquet")
write_parquet(bn_vars_filter_2, "./data/bn_vars.parquet")

# ---------------------------------------------------------------------------- #
df_clean_reduced <- mice(df_clean_reduced, m=5, method="pmm", seed=1234)
imp <- complete(df_clean_reduced, 1)

# ---------------------------------------------------------------------------- #

# Kolomnamen vertalen
colname_translation <- c(
  "MMSE_TOTAAL" = "MINI MENTAL STATE EXAMINATION",
  "STARKSTEIN" = "STARKSTEIN SCORE",
  "CDR" = "BASELINE CDR",
  "CVA" = "STROKE HISTORY",
  "BCS_1" = "BIOMARKER SCORE 1",
  "BCS_2" = "BIOMARKER SCORE 2",
  "NEURORAD_SVD_SCORE" = "SMALL VESSEL DISEASE SCORE",
  "HV_ICV" = "HIPPOCAMPUS/INTRACRANIAL VOLUME",
  "TBV_ICV" = "BRAIN/INTRACRANIAL VOLUME",
  "CBF" = "CEREBRAL BLOOD FLOW",
  "EVENT_MACE" = "OUTCOME_MACE",
  "CDR_INCR" = "OUTCOME_CDR_INCREASE",
  "T4_DROPOUT_REASON" = "DROPOUT REASON",
  "AGE" = "AGE",
  "SEX" = "SEX",
  "PTAU181" = "PTAU181",
  "NFL" = "NFL",
  "GFAP" = "GFAP",
  "PATIENTENGROEP" = "PATIENT GROUP",
  "MACE" = "ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY",
  "SCORE_2" = "VASCULAR RISK SCORE"
)

# Pas kolomnamen aan
colnames(imp) <- ifelse(colnames(imp) %in% names(colname_translation),
                       colname_translation[colnames(imp)],
                       toupper(colnames(imp))) 
imp$`ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY` <- 
  as.character(imp$`ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY`)

# Labels vertalen
label_translation <- list(
  `STROKE HISTORY` = c(
    "Ja, hersenbloeding" = "Yes, hemorrhagic stroke",
    "Ja, herseninfarct" = "Yes, ischemic stroke",
    "Ja, type onbekend" = "Yes, type unknown",
    "Nee" = "No"
  ),
  `PATIENT GROUP` = c(
    "Carotid occlusive disease" = "Carotid occlusive disease",
    "Controle" = "Reference",
    "Hartfalen" = "Heart failure",
    "Vascular cognitive impairment" = "Vascular cognitive impairment"
  ),
  `ATHEROSCLEROTIC CARDIOVASCULAR DISEASE HISTORY`= c(
    "0" = "No",
    "1" = "Yes"
))


# Labels aanpassen
for (var in names(label_translation)) {
  if (var %in% colnames(imp)) {
    imp[[var]] <- as.character(imp[[var]])
    imp[[var]] <- label_translation[[var]][imp[[var]]]
    imp[[var]] <- factor(imp[[var]])
  }
}

write_parquet(imp, "data/df_imp.parquet")

#write_parquet(bn_vars_filter_2, "./data/bn_vars.parquet")

# ---------------------------------------------------------------------------- #

# numeric_vars <- df_clean %>%
#   select(where(~ is.numeric(.) && !is.factor(.)))
# 
# # Discretize only numeric columns
# df_final_numeric <- bnlearn::discretize(numeric_vars, method = "hartemink",
#                                         breaks=4, , ibreaks = 5)
# 
# sapply(df_final_numeric, function(x) any(grepl("nan", levels(x))))

# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #




































# Select variables

df <- df %>% 
  dplyr::select(patientID,
                T0_datumbaselinebezoek_E1_C1,
                T0_patientengroep_E1_C1,
                
                T0_Age, # Demografie
                Sex, # Demografie
                T0_opleiding_E1_C1, 
                T0_leefsituatie_E1_C1,
                
                T0_MMSE_totaal_E1_C1,
                

                T0_WMH,
                T0_HV_ICV, # Brain damage
                T0_TBV_ICV, # Brain damage
                T0_neurorad_lobar_microbleed_present,
                T0_neurorad_non_lobar_microbleed_present,
                T0_neurorad_moderate_severe_pvs,
                #T0_neurorad_number_of_lacunar_infarcts,
                T0_neurorad_svd_score,
                T0_CBF,
              
                T0_TIA_E1_C1, # CV hersenen
                T0_CVA_E1_C1, # CV hersenen
                
                T0_hartinfarct_E1_C1, # CV hart
                T0_bypass_E1_C1, # CV hart
                T0_dotter_E1_C1, # CV hart

                T0_diabetes_E1_C1,
                T0_cholesterol_E1_C1,
                T0_cholesterol_medicatie_E1_C1,
                T0_bloeddruk_E1_C1,
                T0_bloeddruk_medicatie_E1_C1,
                T0_OSAS_E1_C1, 
                T0_nierfunctie_E1_C1,
                T0_schildklier_E1_C1,
                T0_BMI,
                T0_roken_E1_C1,
                T0_Alcohol_E1_C1,
                
                T0_depressie_E1_C1,
                
                T0_PWV, # Hemo
                T0_hartfreq, # Hemo
                T0_SYSBP, # Hemo
                T0_DIASBP, # Hemo

                T0_creatinine_E1_C6, # Lab
                T0_natrium_E1_C6, # Lab
                T0_kalium_E1_C6, # Lab
                T0_hemoglobine_E1_C6, # Lab
                T0_hematocriet_E1_C6, # Lab
                T0_CRP_E1_C6, # Lab
                T0_Aβ40, # Lab
                T0_Aβ42, # Lab
                T0_pTau181, # Lab
                T0_NfL, # Lab
                T0_triglyceriden_E1_C6,
                T0_cholesterol_totaal_E1_C6,
                T0_cholesterol_LDL_E1_C6,
                T0_cholesterol_HDL_E1_C6,
                T0_HbA1c_E1_C6,
                T0_GFAP,
            
                T0_TNFRSF14:T0_NTproBNP, # Olink
                
                T2_CVA_E3_C10, # Outcomes
                T2_CVA_type_E3_C10, # Outcomes
                T2_CVA_datum_E3_C10, # Outcomes
                T2_CVA_type_overig_E3_C10, # Outcomes
                T2_CVA_E3_C11, # Outcomes
                T2_CVA_type_E3_C11, # Outcomes
                T2_CVA_datum_E3_C11, # Outcomes
                
                T2_cardio_E3_C10, # Outcomes
                T2_cardio_type_E3_C10, # Outcomes
                T2_cardio_datum_E3_C10, # Outcomes
                T2_cardio_type_overig_E3_C10, # Outcomes
                T2_cardio_E3_C11, # Outcomes
                T2_cardio_type_E3_C11, # Outcomes
                T2_cardio_datum_E3_C11, # Outcomes
                T2_cardio_type_overig_E3_C11, # Outcomes
                
                T4_CVA_E4_C12, # Outcomes
                T4_CVA_type_E4_C12, # Outcomes
                T4_CVA_datum_E4_C12, # Outcomes
                T4_CVA_type_overig_E4_C12, # Outcomes
                
                T4_cardio_E4_C12, # Outcomes
                T4_cardio_type_E4_C12, # Outcomes
                T4_cardio_datum_E4_C12, # Outcomes
                T4_cardio_type_overig_E4_C12, # Outcomes
                
                T0_CDR_E1_C1, # Outcomes
                T2_CDR_E3_C10, # Outcomes
                T2_CDR_E3_C11, # Outcomes
                T4_CDR_E4_C12, # Outcomes
                
                T2_1_oorzaak_overlijden_E3_C11, # Outcomes
                T2_1_datum_overlijden_E3_C11, # Outcomes
                T4_1_oorzaak_overlijden_E4_C12, # Outcomes
                T4_1_datum_overlijden_E4_C12, # Outcomes 
                
               ) 

# ---------------------------------------------------------------------------- #



df <- df %>% filter(!is.na(T0_TNFRSF14))

df <- df %>% 
  dplyr::select(-T2_dropout_reason, -T5_dropout_reason, -T2_CDR, -T4_CDR)

# Convert all haven_labelled columns to factors
df <- df %>%
  mutate(across(where(is.labelled), as_factor))

cap_first <- function(x) {
  # For each string in x, change the first character to uppercase
  paste0(toupper(substring(x, 1, 1)), substring(x, 2))
}

df[] <- lapply(df, function(col) {
  if (is.factor(col)) {
    # Update the levels by applying cap_first to each level
    levels(col) <- cap_first(levels(col))
    col
  } else {
    col
  }
})

start_col <- match("T0_TNFRSF14", names(df))
end_col   <- match("T0_CCL16", names(df))

# Check if both columns were found
if (is.na(start_col) || is.na(end_col)) {
  stop("One or both of the specified columns (T0_TNFRSF14, T0_CCL16) could not be found in 'data'.")
}

# Create an index vector for these columns
pca_cols <- start_col:end_col

# Extract just the columns you wish to reduce
pca_data <- df[, pca_cols]

# Perform PCA on the selected columns.
# We use center = TRUE and scale. = TRUE to standardize the variables before PCA.
pca_result <- prcomp(pca_data, center = TRUE, scale. = TRUE)

# Optional: Review the PCA result summary to inspect the variance explained by each component.
summary(pca_result)

# Compute variance explained by each component
explained_variance <- summary(pca_result)$importance[2, ]

# Compute cumulative variance
cumulative_variance <- cumsum(explained_variance)

# Print cumulative variance explained - keep 80%
print(cumulative_variance)

# For illustration, we decide to keep the first two principal components.
num_components <- 23

# Extract the scores (the principal component values for each observation)
pcs <- pca_result$x[, 1:num_components, drop = FALSE]
colnames(pcs) <- paste0("Olink_PC", 1:num_components)

# Option 1: Remove the original columns and then append the PCA components at the end.
df <- cbind(df[, -pca_cols], pcs)

# ---------------------------------------------------------------------------- #

# Convert integer columns to numeric
df[] <- lapply(df, function(x) if(is.integer(x)) as.numeric(x) else x)

df$T0_neurorad_moderate_severe_pvs <- 
  as.factor(df$T0_neurorad_moderate_severe_pvs)
df$T0_neurorad_lobar_microbleed_present <- 
  as.factor(df$T0_neurorad_lobar_microbleed_present)

df$T0_neurorad_moderate_severe_pvs <- 
  as.factor(df$T0_neurorad_moderate_severe_pvs)
df$T0_neurorad_lobar_microbleed_present <- 
  as.factor(df$T0_neurorad_lobar_microbleed_present)

df$T0_neurorad_number_of_lacunar_infarcts <- 
  as.factor(df$T0_neurorad_number_of_lacunar_infarcts)

df$T0_neurorad_non_lobar_microbleed_present <-
  as.factor(df$T0_neurorad_non_lobar_microbleed_present)

df$outcome_composite <- as.factor(df$outcome_composite)
df$Event_Stroke <- as.factor(df$Event_Stroke)
df$T0_CDR <- as.factor(df$T0_CDR)
df$Event_MACE <- as.factor(df$Event_MACE)
df$T0_neurorad_svd_score <- as.factor(df$T0_neurorad_svd_score)
df$CDR_INCR <- as.factor(df$CDR_INCR)

df <- df %>% 
  select(-patientID, -Time_Stroke, -Time_MACE)

df$T0_neurorad_number_of_lacunar_infarcts <- 
  as.numeric(as.character(df$T0_neurorad_number_of_lacunar_infarcts))

# Select only numeric columns
numeric_vars <- df %>% select(where(is.numeric))

saveRDS(df, "data/df.rds")
df <- readRDS("data/df.rds")

# ---------------------------------------------------------------------------- #

set.seed(1234)
df.impute <- mice(df, m=5, method="pmm") 

imp <- complete(df.impute, 1)

saveRDS(imp, "data/df_imp.rds")




# df <- df %>%
#   mutate(
#     across(contains("datum"), ~as.Date(., format = "%Y-%m-%d"))
#   ) %>%
#   mutate(
#     # Pre-process to replace conditionally and ensure date or NA of date type
#     T2_Stroke_datum_safe = ifelse(T2_CVA_type == 3, T2_CVA_datum, as.Date(NA)),
#     T2_1_datum_overlijden_E3_C11_safe = ifelse(
#       grepl("herseninfarct", T2_1_oorzaak_overlijden_E3_C11, ignore.case = TRUE) |
#         grepl("hersenbloeding", T2_1_oorzaak_overlijden_E3_C11, ignore.case = TRUE) |
#         grepl("CVA", T2_1_oorzaak_overlijden_E3_C11, ignore.case = TRUE),
#       T2_1_datum_overlijden_E3_C11, as.Date(NA)),
#
#     T4_Stroke_datum_E4_C12_safe = ifelse(T4_CVA_type_E4_C12 == 3,
#                                          T4_CVA_datum_E4_C12, as.Date(NA)),
#     T4_1_datum_overlijden_E4_C12_safe = ifelse(
#       grepl("herseninfarct", T4_1_oorzaak_overlijden_E4_C12, ignore.case=TRUE) |
#         grepl("hersenbloeding", T4_1_oorzaak_overlijden_E4_C12, ignore.case=TRUE) |
#         grepl("CVA", T4_1_oorzaak_overlijden_E4_C12, ignore.case=TRUE) |
#       T4_1_datum_overlijden_E4_C12, as.Date(NA))
#     ) %>%
#   mutate(
#     T2_Stroke_Date = ifelse(
#       T2_Event_Stroke == 1,
#       pmin(T2_Stroke_datum_safe, na.rm = TRUE), as.Date(NA)),
#     T5_Stroke_Date = ifelse(
#       T4_Event_Stroke == 1, pmin(T4_Stroke_datum_E4_C12_safe,
#                                  T4_1_datum_overlijden_E4_C12_safe, na.rm = TRUE),
#       as.Date(NA))
#   )
#
#
# df <- df %>%
#   mutate(
#     T2_Stroke_Date = as.Date(T2_Stroke_Date, origin = "1970-01-01"),
#     T5_Stroke_Date = as.Date(T5_Stroke_Date, origin = "1970-01-01")
#   )

# df <- df %>%
#   mutate(
#     T0_Time = 0,  # Baseline
#     T2_Stroke_Time = as.numeric(difftime(T2_Stroke_Date,
#                                          T0_datumbaselinebezoek_E1_C1,
#                                          units = "days")) / 365.25,
#     T4_Stroke_Time = as.numeric(difftime(T5_Stroke_Date,
#                                          T0_datumbaselinebezoek_E1_C1,
#                                          units = "days")) / 365.25
#  ) %>%
# dplyr::select(
#   -starts_with("T2_CVA"),
#   -starts_with("T2_cardio"),
#   -starts_with("T4_CVA"),
#   -starts_with("T4_cardio"),
#   -starts_with("T2_1_"),
#   -starts_with("T4_1_")
# ) %>%
#  mutate(T2_Stroke_Time = ifelse((T2_Stroke_Time<0), 0.005, T2_Stroke_Time)
#  ) %>%
#  mutate(Time_Stroke = pmin(T2_Stroke_Time, T4_Stroke_Time, na.rm=TRUE))

# ---------------------------------------------------------------------------- #

# df <- df %>%
#   mutate(
#     across(contains("datum"), ~as.Date(., format = "%Y-%m-%d"))
#   ) %>%
#   mutate(
#     T2_MACE_Date = ifelse(
#       T2_Event_MACE == 1,
#       pmin(T2_CVA_datum, T2_cardio_datum, T2_1_datum_overlijden_E3_C11, 
#             na.rm = TRUE),
#       as.Date(NA)),
#     T5_MACE_Date = ifelse(
#       T4_Event_MACE == 1,
#       pmin(T4_CVA_datum_E4_C12, T4_cardio_datum_E4_C12, 
#            T4_1_datum_overlijden_E4_C12, na.rm = TRUE),
#       as.Date(NA))
#   )
# 
# 
# df <- df %>%
#   mutate(
#     T2_MACE_Date = as.Date(T2_MACE_Date, origin = "1970-01-01"),
#     T5_MACE_Date = as.Date(T5_MACE_Date, origin = "1970-01-01")
#   )
# 
# df <- df %>%
#   mutate(
#     T0_Time = 0,  # Baseline
#     T2_MACE_Time = as.numeric(difftime(T2_MACE_Date, 
#                                        T0_datumbaselinebezoek_E1_C1, 
#                                        units = "days")) / 365.25,
#     T4_MACE_Time = as.numeric(difftime(T5_MACE_Date, 
#                                        T0_datumbaselinebezoek_E1_C1, 
#                                        units = "days")) / 365.25
#   ) %>% 
# dplyr::select(
#      -starts_with("T2_CVA"),
#      -starts_with("T2_cardio"),
#      -starts_with("T4_CVA"),
#      -starts_with("T4_cardio"),
#      -starts_with("T2_1_"),
#      -starts_with("T4_1_")
#    ) %>% 
#   mutate(T2_MACE_Time = ifelse((T2_MACE_Time<0), 0.005, T2_MACE_Time)
#   ) %>% 
#   mutate(Time_MACE=pmin(T2_MACE_Time, T4_MACE_Time, na.rm=TRUE))

# ---------------------------------------------------------------------------- #

# df <- df %>% 
#   mutate(Time_MACE = ifelse(is.na(Time_MACE), 5, Time_MACE)) %>% 
#   mutate(Time_Stroke = ifelse(is.na(Time_Stroke), 5, Time_Stroke))


