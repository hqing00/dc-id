import streamlit as st
import pandas as pd

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        pwd = st.text_input("Enter password", type="password")
        if st.button("Login"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
            else:
                st.error("Incorrect password")
        return False
    return True

if not check_password():
    st.stop()

st.set_page_config(page_title="ID CSV Cleaner", layout="wide")
st.title("📄CSV Cleaning Tool")
st.write("Upload **1 or 2 CSV files**. If 2 are uploaded, they will be combined automatically.")

# --- File uploader ---
uploaded_files = st.file_uploader(
    "Upload CSV file(s)",
    type=["csv"],
    accept_multiple_files=True
)

def load_and_combine(files):
    dfs = []
    for f in files:
        df = pd.read_csv(f, header=None, dtype=str, keep_default_na=False)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

if uploaded_files:
    if len(uploaded_files) > 2:
        st.error("Please upload **maximum 2 files**.")
        st.stop()

    # --- Load & combine ---
    df = load_and_combine(uploaded_files)
    st.success(f"{len(uploaded_files)} file(s) loaded successfully")

    # =======================
    # Cleaning logic starts
    # =======================

    required_cols = [
        'Posting Date', 'Effective Date', 'Branch', 'Journal',
        'Transaction Description', 'Amount', 'DB/CR', 'Balance'
    ]

    header_row_idx = None
    for i, row in df.iterrows():
        row_stripped = row.astype(str).str.strip()
        matches = [
            any(col.lower() in str(cell).lower() for cell in row_stripped)
            for col in required_cols
        ]
        if all(matches):
            header_row_idx = i
            break

    if header_row_idx is None:
        st.error("Header row not found. Cleaning cannot proceed.")
        st.stop()

    header = df.iloc[header_row_idx].astype(str).str.strip()
    col_indices = {}
    for col in required_cols:
        for idx, cell in enumerate(header):
            if col.lower() in cell.lower():
                col_indices[col] = idx
                break

    POSTING_DATE_COL = 1
    EFFECTIVE_DATE_COL = 5
    BRANCH_COL = 9

    data_rows = df.iloc[header_row_idx + 1:]
    extracted_data = []

    for _, row in data_rows.iterrows():
        dbcr = row[col_indices['DB/CR']]
        is_ledger = False
        try:
            float(str(dbcr).replace(",", ""))
            is_ledger = True
        except:
            pass

        if is_ledger:
            extracted_row = {
                'Posting Date': '',
                'Effective Date': '',
                'Branch': '',
                'Journal': '',
                'Transaction Description': '',
                'Amount': '',
                'DB/CR': dbcr,
                'Balance': ''
            }
        else:
            extracted_row = {
                'Posting Date': row[POSTING_DATE_COL],
                'Effective Date': row[EFFECTIVE_DATE_COL],
                'Branch': row[BRANCH_COL],
                'Journal': row[col_indices['Journal']],
                'Transaction Description': row[col_indices['Transaction Description']],
                'Amount': row[col_indices['Amount']],
                'DB/CR': dbcr,
                'Balance': row[col_indices['Balance']]
            }
        extracted_data.append(extracted_row)

    clean_df = pd.DataFrame(extracted_data)

    cols_to_check = [
        'Posting Date', 'Effective Date', 'Branch',
        'Journal', 'Transaction Description', 'Amount', 'Balance'
    ]

    clean_df = clean_df[
        ~clean_df[cols_to_check]
        .apply(lambda x: x.astype(str).str.strip().eq('').all(), axis=1)
    ]

    clean_df = clean_df[
        ~clean_df.apply(
            lambda row: row.astype(str).str.contains("Account Statement", case=False).any(),
            axis=1
        )
    ]

    header_keywords = [
        'posting date', 'effective date', 'branch',
        'journal', 'transaction description', 'amount', 'db/cr', 'balance'
    ]

    clean_df = clean_df[
        ~clean_df.apply(
            lambda row: any(
                k in str(cell).lower()
                for k in header_keywords
                for cell in row.astype(str)
            ),
            axis=1
        )
    ]

    merged_rows = []
    prev = None

    for _, row in clean_df.iterrows():
        is_spill = (
            str(row['Posting Date']).strip() == '' and
            str(row['Effective Date']).strip() == '' and
            str(row['DB/CR']).strip() == '' and
            (
                str(row['Branch']).strip() != '' or
                str(row['Transaction Description']).strip() != '' or
                str(row['Balance']).strip() != ''
            )
        )

        if is_spill and prev is not None:
            if str(row['Branch']).strip():
                prev['Branch'] += " " + str(row['Branch'])
            if str(row['Transaction Description']).strip():
                prev['Transaction Description'] += " " + str(row['Transaction Description'])
            if str(row['Balance']).strip():
                prev['Balance'] += str(row['Balance'])
        else:
            merged_rows.append(row.copy())
            prev = merged_rows[-1]

    clean_df = pd.DataFrame(merged_rows)

    # --- Cleaned preview only ---
    st.subheader("✅ Cleaned Data Preview (first 100 rows)")
    st.dataframe(clean_df.head(100), use_container_width=True)
    st.caption(f"Total rows after cleaning: {len(clean_df)}")

    # --- Download button ---
    csv = clean_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Cleaned CSV",
        csv,
        "Cleaned_Data.csv",
        "text/csv"
    )

else:
    st.info("Please upload at least 1 CSV file.")
