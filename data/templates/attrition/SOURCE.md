# Employee attrition template data source

Not bundled. The template uses IBM's "HR Analytics Employee Attrition & Performance" sample, a fictional data
set created by IBM data scientists: 1,470 employees, 35 columns, target `Attrition` (16.1% Yes).

Get it from https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset
(`WA_Fn-UseC_-HR-Employee-Attrition.csv`); the same file is in https://github.com/IBM/employee-attrition-aif360
as `data/emp_attrition.csv`. Then either upload it on the "Your data" screen, or set
`CONCOURS_ATTRITION_CSV=/path/to/file.csv` so new attrition projects load it automatically.

What Protect does with it: `EmployeeNumber` is dropped as an identifier, `EmployeeCount`, `Over18` and
`StandardHours` as constants. `Age`, `Gender` and `MaritalStatus` are set aside for the fairness report.

Framing: the list is for retention conversations (a manager checks in), never for performance or termination
decisions.
