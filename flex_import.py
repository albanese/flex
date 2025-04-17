import json
import hashlib
import pandas as pd


raw_json = '''{"assets":{"name":"ASSETS","value":"13318970.87","items":[{"account_id":null,"name":"Current Assets","value":"13300233.24","items":[{"account_id":null,"name":"Bank Accounts","value":"-513160.89","items":[{"account_id":"6c9790a2-0800-46cc-8c50-e29e69d8015c","name":"Flex Cash","value":"806291.61"},{"account_id":"b58e60f6-fe20-451e-9fc2-87eb58bcb297","name":"Flex Checking","value":"-1272375.00"},{"account_id":"c7a7a89e-cc40-40b0-90dd-60f0dadedc41","name":"Flex 2761","value":"-47077.50"}]},{"account_id":null,"name":"Accounts Receivable","value":"13788410.16","items":[{"account_id":"bdd4df93-54ac-420c-8a9b-897a24f79c9c","name":"Accounts Receivable","value":"13788410.16"}]},{"account_id":null,"name":"Other Current Assets","value":"24983.97","items":[{"account_id":"15560eaa-78c3-4ef6-bcc2-4697c9f509ef","name":"Payments to Deposit","value":"10000.00"},{"account_id":"1d09f6de-b8e5-4865-94e4-5a1f15e0ce04","name":"Prepaid Expenses","value":"14983.97"}]}]},{"account_id":null,"name":"Fixed Assets","value":"18737.63","items":[{"account_id":null,"name":"Property, Plant, and Equipment","value":"18737.63","items":[{"account_id":"47c124b7-efcb-4225-95b8-7b85e2dcb977","name":"Office Equipment","value":"14855.91"},{"account_id":"3073b7ee-8d38-48e8-b2cc-a422ffb2d20f","name":"Furniture","value":"1017.08"},{"account_id":"6450bea2-bafc-40a5-9faa-0a069669f758","name":"Computers and Accessories","value":"2864.64"}]}]}]},"liabilities":{"name":"Liabilities","value":"1025016.99","items":[{"account_id":null,"name":"Current Liabilities","value":"1014525.75","items":[{"account_id":null,"name":"Accounts Payable","value":"83086.72","items":[{"account_id":null,"name":"Accounts Payable","value":"83086.72","items":[{"account_id":"09342b42-bfa9-459c-997b-f7dac52d32a6","name":"Accrued Rent","value":"69723.08"},{"account_id":"1cf73166-6064-4e55-875a-ede915e5f0cb","name":"Payable to Character","value":"9313.64"},{"account_id":"51818eb7-9561-4f26-8285-b391b90b3c21","name":"Accounts Payable","value":"4050.00"}]}]},{"account_id":null,"name":"Credit Cards","value":"854440.93","items":[{"account_id":null,"name":"2004 Credit Card","value":"854440.93","items":[{"account_id":"420851e1-e6f4-4f2f-9a15-3634fa24bce0","name":"Flex Bronze Card","value":"5817.50"},{"account_id":"1a6c59d8-ae89-4704-b6ec-721da2e6b7c0","name":"Flex Silver Card","value":"797087.28"},{"account_id":"6112362b-0dac-4172-a3da-5c89e4487768","name":"Flex Gold Card","value":"76536.15"},{"account_id":"fc38e9a5-f2f5-45b0-8466-ecfc36d28561","name":"Flex Platinum Card","value":"-25000.00"}]}]}]},{"account_id":null,"name":"Long-Term Liabilities","value":"10491.24","items":[{"account_id":"220","name":"Settle Loans Payable","value":"10491.24"}]}]},"equity":{"name":"Equity","value":"12399101.55","items":[{"account_id":null,"name":"Owners Equity","value":"-95000.00","items":[{"account_id":"831b6852-6f82-4ce1-b07b-88601d16457d","name":"Owner's Equity","value":"-95000.00"}]},{"account_id":"b1ba5fb3-5d54-4806-ad8d-e78bd2187e13","name":"Retained Earnings","value":"11881707.50"},{"account_id":"49862dbf-e470-479e-98ae-c1e172bd86a3","name":"Balance Adjustments","value":"122453.09"},{"account_id":null,"name":"Net Income","value":"489940.96"}]}}'''
data = json.loads(raw_json)


def generate_account_id(path_name: str) -> str:
  '''
  Generate a unique ID for a given path.
  Input: path_name (ex. "Assets>Current Assets>Bank Accounts")
  Output: MD5 hash ID (ex. "6c9790a2-0800-46cc-8c50-e29e69d8015c")
  '''
  return hashlib.md5(path_name.encode('utf-8')).hexdigest()

def parse_partner_json(json_node: dict, parent_path: str = "", parent_id: str = None, parent_name: str = None, origin_name: str = None, statement_type: str = None, level: int = 0) -> list:
    '''
    Parse a JSON node and return a list of rows.  Recursively parses values within items[]
    '''
    rows = []
    current_name = json_node["name"]
    current_value = float(json_node["value"])
    current_path = f"{parent_path}>{current_name}" if parent_path else current_name

    if level == 0 and current_name.lower() in ["assets", "liabilities", "equity"]:
        statement_type = current_name.lower()

    if level == 1:
        origin_name = current_name.lower()

    account_id = json_node.get("account_id")
    id = account_id if account_id else generate_account_id(current_path)

    items = json_node.get("items", [])
    if items:
        value_item_total = round(sum(float(item["value"]) for item in items), 2)
    else:
        value_item_total = None

    terminated_node = not bool(items)

    rows.append({
        "id": id,
        "account_id": account_id,
        "name": current_name,
        "value": current_value,
        "value_item_total": value_item_total,
        "parent_id": parent_id,
        "parent_name": parent_name,
        "origin_parent_name": origin_name,
        "statement_type": statement_type,
        "level": level,
        "terminated_node": terminated_node
    })

    for child in items:
        rows.extend(parse_partner_json(child, current_path, id, current_name, origin_name, statement_type, level + 1))

    return rows

def run_validations(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Run quality validations on the dataframe.

    Rules List:
    1. Roll-up values match sum of children
    2. Unique IDs for Accounts
    3. Accounts have Names
    4. All ($) values are numeric
    5. Valid statement types (Assets, Liabilities, Equity)
    6. Equity equals Assets minus Liabilities
    '''
    results = []

    mismatched_rollups = df[(df["value_item_total"].notnull()) & (df["value"].round(2) != df["value_item_total"].round(2))]
    results.append({
        "check": "Roll-up values match sum of children", 
        "status": "PASS" if mismatched_rollups.empty else "FAIL", 
        "fail_count": len(mismatched_rollups),
        "failed_ids": mismatched_rollups["id"].tolist() if not mismatched_rollups.empty else []
    })

    duplicate_ids = df[df["id"].duplicated(keep=False)]
    results.append({
        "check": "Unique IDs", 
        "status": "PASS" if duplicate_ids.empty else "FAIL", 
        "fail_count": len(duplicate_ids),
        "failed_ids": duplicate_ids["id"].tolist() if not duplicate_ids.empty else []
    })

    named_accounts = df[df["name"].isnull()]
    results.append({
        "check": "Accounts have Names",
        "status": "PASS" if named_accounts.empty else "FAIL",
        "fail_count": len(named_accounts),
        "failed_ids": named_accounts["id"].tolist() if not named_accounts.empty else []
    })

    non_numeric_values = df[~df["value"].apply(lambda x: isinstance(x, (int, float)))]
    results.append({
        "check": "All values are numeric", 
        "status": "PASS" if non_numeric_values.empty else "FAIL", 
        "fail_count": len(non_numeric_values),
        "failed_ids": non_numeric_values["id"].tolist() if not non_numeric_values.empty else []
    })

    unexpected_statements = df[~df["statement_type"].isin(["assets", "liabilities", "equity"])]
    results.append({
        "check": "Valid statement types", 
        "status": "PASS" if unexpected_statements.empty else "FAIL", 
        "fail_count": len(unexpected_statements),
        "failed_ids": unexpected_statements["id"].tolist() if not unexpected_statements.empty else []
    })

    top_level_values = df[df["level"] == 0]
    assets_value = top_level_values[top_level_values["statement_type"] == "assets"]["value"].iloc[0]
    liabilities_value = top_level_values[top_level_values["statement_type"] == "liabilities"]["value"].iloc[0]
    equity_value = top_level_values[top_level_values["statement_type"] == "equity"]["value"].iloc[0]
    
    equity_calc_diff = abs(equity_value - (assets_value - liabilities_value))
    equity_calc_check = equity_calc_diff != 0
    
    results.append({
        "check": "Equity equals Assets minus Liabilities",
        "status": "PASS" if equity_calc_check else "FAIL",
        "fail_count": 0 if equity_calc_check else 1,
        "failed_ids": [] if equity_calc_check else [top_level_values[top_level_values["statement_type"] == "equity"]["id"].iloc[0]]
    })

    print("\nValidation Results:")
    result_df = pd.DataFrame(results)
    print(result_df)
    return result_df
    
def process_json_to_df(json_data):
    all_rows = []
    for top_key in ["assets", "liabilities", "equity"]:
        all_rows.extend(parse_partner_json(json_data[top_key]))

    df = pd.DataFrame(all_rows)
    validations = run_validations(df)
    return df, validations

def write_df_to_db(df: pd.DataFrame, destination_table: str):
    '''
    PLACEHOLDER: Write the resulting dataframe to a database table.
    '''
    print(f"Writing dataframe to {destination_table} table.")
    pass


df, validations = process_json_to_df(data)
# print(df.head())
# print(df.iloc[0])
# print(df[df["id"] == "f23574628cb724a4c1fe74b25006b228"])

write_df_to_db(df, "flex_import")
write_df_to_db(validations, "flex_import_validations")