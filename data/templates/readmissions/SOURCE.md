# Hospital readmissions template data source

`dataset.csv` is built by `scripts/fetch_data.py` from `diabetic_data.csv` in UCI Machine Learning Repository
dataset 296, "Diabetes 130-US Hospitals for Years 1999-2008",
https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008 (Strack et al., 2014).
101,766 hospital encounters of 71,518 diabetic patients in 130 US hospitals.

License: CC BY 4.0. Credit: UCI Machine Learning Repository; B. Strack, J. DeShazo, C. Gennings, J. Olmo,
S. Ventura, K. Cios and J. Clore, "Impact of HbA1c Measurement on Hospital Readmission Rates: Analysis of
70,000 Clinical Database Patient Records", BioMed Research International, 2014.

Changes from the source file: `readmitted` ("<30", ">30", "NO") is replaced by `readmitted_30d`, "yes" for
"<30" and "no" otherwise (11.2% yes). "?" (the file's missing-value marker) is read as empty.

What Protect must catch: `patient_nbr` repeats (16,773 patients have more than one encounter, 46% of rows), so a random
split would test the model on patients it trained on. Protect drops it as a feature and splits by patient.
`encounter_id` is unique per row and dropped as an identifier. `race`, `gender` and `age` are set aside for the
fairness report. No time column: the file has no admission dates.
