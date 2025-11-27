import pandas as pd
import sys

future_rows = 3000
black_rows = 3000

input_file = 'data/raw/posts.csv'
data_folder = 'data/split_data'

sys.stdout = open('data_splitting.log', 'w')

def check_data_quality(df):
    if df.isnull().values.any():
        raise ValueError("Data contains missing values.")
    if df.duplicated().any():
        raise ValueError("Data contains duplicate rows.")
    print("Data quality check passed: No missing values or duplicates.")

def split_data(input_file, data_folder):
    df = pd.read_csv(input_file)
    check_data_quality(df)
    print(f"Number of rows in the dataset: {len(df)}")
    print(df.columns)
    df['date'] = pd.to_datetime(df['date'])
    print(f"Date column converted to datetime. Data types:\n{df.dtypes}")

    df_sorted = df.sort_values(by='date', ascending=False).reset_index(drop=True)
    future_df = df_sorted.head(future_rows)    # 3K most recent rows
    print(f"Date range in future_df: \n  {future_df['date'].min()} to {future_df['date'].max()}")
    print(f"Number of rows in future_df: {len(future_df)}")
    future_df.to_csv(f'{data_folder}/future.csv', index=False)
    
    remaining_df = df_sorted.iloc[future_rows:]
    remaining_df = remaining_df.sample(frac=1, random_state=42).reset_index(drop=True)
    black_df = remaining_df.head(black_rows)      # 3K random rows
    present_df = remaining_df.iloc[black_rows:]
    
    print(f"Number of rows in black_df: {len(black_df)}")
    print(f"Number of rows in present_df: {len(present_df)}")
    
    black_df.to_csv(f'{data_folder}/black.csv', index=False)
    present_df.to_csv(f'{data_folder}/present.csv', index=False)

if __name__ == "__main__":
    split_data(input_file, data_folder)
    print("Data splitting completed successfully.")
    sys.stdout.close()