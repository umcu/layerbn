# Required Variables:
  
#T2_CVA
#T2_CVA_datum
#T2_cardio
#T2_cardio_datum
#T2_1_oorzaak_overlijden_E3_C11
#T2_cardio_type
#T2_1_datum_overlijden_E3_C11
#T4_CVA_E4_C12
#T4_CVA_datum_E4_C12
#T4_cardio_E4_C12
#T4_cardio_datum_E4_C12
#T4_1_oorzaak_overlijden_E4_C12
#T4_cardio_type_E4_C12
#T4_1_datum_overlijden_E4_C12
#T0_datumbaselinebezoek_E1_C1


define_mace <- function(df) {
  
  df <- df %>%
    mutate(T0_Event = 0,
           
           # Follow-up 1
           T2_Event = ifelse(T2_CVA == 1 | 
                               T2_CVA == 2 | 
                               T2_cardio == 1 |
                               T2_cardio == 2 | 
                               grepl("myocardinfarct", 
                                     T2_1_oorzaak_overlijden_E3_C11)|
                               grepl("aneurysma", 
                                     T2_1_oorzaak_overlijden_E3_C11) |
                               grepl("Myocardinfarct", 
                                     T2_cardio_type) |
                               grepl("Dotter/stent hart",
                                     T2_cardio_type) |
                               grepl("Coronaire bypass operatie", 
                                     T2_cardio_type), 1, 0),
           
           # Follow-up 2
           T4_Event = ifelse(T4_CVA_E4_C12 == 1 | 
                               T4_CVA_E4_C12 == 2 | 
                               T4_cardio_E4_C12 == 1 |
                               T4_cardio_E4_C12 == 2 | 
                               grepl("myocardinfarct", 
                                     T4_1_oorzaak_overlijden_E4_C12)|
                               grepl("aneurysma", 
                                     T4_1_oorzaak_overlijden_E4_C12) |
                               grepl("Myocardinfarct", 
                                     T4_cardio_type_E4_C12) |
                               grepl("Dotter/stent hart",
                                     T4_cardio_type_E4_C12) |
                               grepl("Coronaire bypass operatie", 
                                     T4_cardio_type_E4_C12), 1, 0)
    ) %>% 
    mutate(Event = 
             ifelse(T2_Event==1 | T4_Event==1, 1, 0)
    )
  
  df <- df %>% 
    mutate(
      across(contains("datum"), ~as.Date(., format = "%Y-%m-%d"))) %>% 
    mutate(
      T2_Event_Date = case_when(
        T2_Event == 1 ~ pmin(
          ifelse(T2_CVA == 1 | T2_CVA == 2, 
                 T2_CVA_datum, NA),
          ifelse(T2_cardio == 1 | T2_cardio== 2, 
                 T2_cardio_datum, NA),
          ifelse(grepl("myocardinfarct", T2_1_oorzaak_overlijden_E3_C11) |
                   grepl("aneurysma", T2_1_oorzaak_overlijden_E3_C11) |
                   grepl("Myocardinfarct", T2_cardio_type) |
                   grepl("Dotter/stent hart", T2_cardio_type) |
                   grepl("Coronaire bypass operatie", T2_cardio_type),
                 T2_1_datum_overlijden_E3_C11, as.Date(NA)),
          na.rm = TRUE
        ),
        TRUE ~ NA_real_  # Assign NA if no event
      ),
      T5_Event_Date = case_when(
        T4_Event == 1 ~ pmin(
          ifelse(T4_CVA_E4_C12 == 1 | T4_CVA_E4_C12 == 2, 
                 T4_CVA_datum_E4_C12, NA),
          ifelse(T4_cardio_E4_C12 == 1 | T4_cardio_E4_C12 == 2, 
                 T4_cardio_datum_E4_C12, NA),
          ifelse(grepl("myocardinfarct", T4_1_oorzaak_overlijden_E4_C12) |
                   grepl("aneurysma", T4_1_oorzaak_overlijden_E4_C12) |
                   grepl("Myocardinfarct", T4_cardio_type_E4_C12) |
                   grepl("Dotter/stent hart", T4_cardio_type_E4_C12) |
                   grepl("Coronaire bypass operatie", T4_cardio_type_E4_C12),
                 T4_1_datum_overlijden_E4_C12, as.Date(NA)),
          na.rm = TRUE
        ),
        TRUE ~ NA_real_
      )
    )
  
  df <- df %>%
    mutate(
      T2_Event_Date = as.Date(T2_Event_Date, origin = "1970-01-01"),
      T5_Event_Date = as.Date(T5_Event_Date, origin = "1970-01-01")
    )
  
  df <- df %>%
    mutate(
      T0_Time = 0,
      T2_Time = as.numeric(difftime(T2_Event_Date, 
                                    T0_datumbaselinebezoek_E1_C1, 
                                    units = "days")) / 365.25,
      T4_Time = as.numeric(difftime(T5_Event_Date, 
                                    T0_datumbaselinebezoek_E1_C1, 
                                    units = "days")) / 365.25
    ) %>% 
    dplyr::select(
      -starts_with("T2_CVA"),
      -starts_with("T2_cardio"),
      -starts_with("T4_CVA"),
      -starts_with("T4_cardio"),
      -starts_with("T2_1_"),
      -starts_with("T4_1_")
    ) %>% 
    mutate(T2_Time = ifelse((T2_Time<0), 0.005, T2_Time)
    )
  
  df <- df %>%
    mutate(
      T2_Event_Date = as.Date(T2_Event_Date, origin = "1970-01-01"),
      T5_Event_Date = as.Date(T5_Event_Date, origin = "1970-01-01")
    )
  
  df <- df %>% 
    mutate(Time = ifelse(!is.na(T2_Time) & is.na(T4_Time), 
                         T2_Time,
                         ifelse(is.na(T2_Time) & !is.na(T4_Time), 
                                T4_Time,
                                ifelse(!is.na(T2_Time) & !is.na(T4_Time),
                                       T2_Time, NA))))
  
  df <- df %>%
    dplyr::select(
      -starts_with("T2_CVA"),
      -starts_with("T2_cardio"),
      -starts_with("T4_CVA"),
      -starts_with("T4_cardio"),
      -starts_with("T2_1_"),
      -starts_with("T4_1_")
    ) %>% 
    mutate(
      Time = ifelse(is.na(Time), 5, Time)
    ) %>% 
    mutate(
      Event = ifelse(is.na(Event), 0, Event))
  
  return(df)
}

# Usage
df <- define_mace(df)

