# Required Variables:

#Sex (1 = female, 0 = male)
#T0_diabetes_E1_C1
#T0_Age
#T0_roken_E1_C1
#T0_SYSBP
#T0_cholesterol_totaal_E1_C6
#T0_cholesterol_HDL_E1_C6

calculate_score2 <- function(df) {
  
  df <- df %>% 
    mutate(Gender_SCORE2 = ifelse(Sex == 1, "female", "male"),
           Diabetes_SCORE2 = ifelse(T0_diabetes_E1_C1 == 0, 0, 1),
           Currentsmoker = ifelse(T0_roken_E1_C1 == 1, 1, 0))
  
  df <- df %>% 
    rowwise() %>% 
    mutate(SCORE2_score = RiskScorescvd::SCORE2(
      Age = T0_Age,
      Gender = Gender_SCORE2,
      smoker = as.numeric(as.factor(Currentsmoker)),
      systolic.bp = as.numeric(T0_SYSBP),
      diabetes = Diabetes_SCORE2,
      total.chol = T0_cholesterol_totaal_E1_C6,
      total.hdl = T0_cholesterol_HDL_E1_C6,
      classify=FALSE))
  
  return(df)
}

# Usage
df <- calculate_score2(df)

