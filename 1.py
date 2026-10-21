import pandas as pd
pd.set_option('display.max_columns', None)
import numpy as np

df = pd.read_excel("C:/Users/Mahmoud/Desktop/تقريرر_عملاء_اكسا.xlsx", header = 1)
df = df.dropna(how='all')
parts = df["الاسم||رقم الموبايل"].str.split(r"\|+", expand=True, regex=True)
parts[0] = parts[0].str.strip()
parts[1] = parts[1].str.strip()
df["الرقم"] = np.where(parts[0].str.isdigit(), parts[0], parts[1])
df["الاسم"] = np.where(parts[1].str.isdigit(), parts[0], parts[1])
date = df._series["التاريخ"]
req = df._series["sh"]
group = df.groupby(["sh", "التاريخ"]).size()
follow_up = df[(df["call"].isna()) | (df["الرد"].isna())]
print(follow_up)
print(group)
print(req.value_counts(dropna=False))
print(date.value_counts(dropna=False))
print(df[["الرقم", "الاسم"]])
