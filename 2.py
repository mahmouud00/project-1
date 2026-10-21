
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
import numpy as np

df =pd.read_excel("C:/Users/Mahmoud/Desktop/مراجعة_عملاء_ستائر.xlsx", header = 1)

df = df.dropna(how='all')
parts = df["الاسم||رقم الموبايل"].str.split(r"\|+", expand=True, regex=True)
parts[0] = parts[0].str.strip()
parts[1] = parts[1].str.strip()
df["الاسم"] = np.where(parts[1].str.isdigit(), parts[0], parts[1])
df["الرقم"] = np.where(parts[0].str.isdigit(), parts[0], parts[1])
date = df._series["التاريخ"]
type = df._series["النوع"]
group = df.groupby(["التاريخ", "النوع"]).size()
follow_up =df[(df["الرد"].isna()) | (df["call"].isna())]
print(df.head(1))
print(df["الاسم"], df["الرقم"])
print(date.value_counts(dropna=False))
print(type.value_counts(dropna=False))
print(group)
print(follow_up)
