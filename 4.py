import pandas as pd

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
import numpy as np

df = pd.read_excel("C:/Users/Mahmoud/Desktop/مراجعة_عملاء_ورشة.xlsx", header=1)

df = df.dropna(how="all")
print(df.head(1))
parts = df["الاسم||رقم الموبايل"].str.split(r"\|+", expand=True, regex=True)
parts[0] = parts[0].str.strip()
parts[1] = parts[1].str.strip()
df["الرقم"] = np.where(parts[0].str.isdigit(), parts[0], parts[1])
df["الاسم"] = np.where(parts[1].str.isdigit(), parts[0], parts[1])
clint = df._series["التاريخ"]
issue = df._series["نوع العطل"]
work = df.groupby(["التاريخ", "نوع العطل"]).size()
follow_up = df[(df["الرد"].isna()) | (df["call"].isna())]
print(clint.value_counts())
print("--------------------")
print(issue.value_counts())
print("--------------------")
print(work)
print("--------------------")
print(follow_up)
print("--------------------")
print(df["الاسم"], df["الرقم"])
print("--------------------")
