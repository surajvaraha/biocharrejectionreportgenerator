import pandas as pd
from automation import process_data_and_generate_reports
import os
import shutil

# Create dummy data with messy columns and missing images
data = {
    'Partner Name': ['Partner A', 'Partner A', 'Partner B'],
    'Inventory ID': ['1', '2', '3'],
    'Start Date': ['2025-01-01', '2025-01-01', '2025-01-01'],
    'Start Time': ['10:00', '11:00', '12:00'],
    'Kiln ID': ['K1', 'K2', 'K3'],
    'Artisan Pro': ['Art1', 'Art2', 'Art3'],
    'Slot': ['S1', 'S2', 'S3'],
    # Messy columns
    '1.Process Start (Image)_Status ': ['Rejected', 'Accepted', 'rejected'], # trailing space, lowercase
    'Process Start (Image)': ['http://example.com/img1.jpg', '', 'http://example.com/img3.jpg'], # missing image 2
    '3.90%  (Image)_Status': ['Accepted', 'Rejected', 'Accepted'], # Double space (already in config)
    ' 90%End(Image)': ['', 'http://example.com/img2.jpg', ''] # leading space (already in config)
}

df = pd.DataFrame(data)
df.to_excel("test_messy.xlsx", index=False)

if os.path.exists("generated_reports"):
    shutil.rmtree("generated_reports")
os.makedirs("generated_reports")

print("--- Running Robust Test ---")
process_data_and_generate_reports("test_messy.xlsx", sheet_type='shambav')

print("\n--- Results ---")
files = os.listdir("generated_reports")
print(f"Generated {len(files)} files:")
for f in files:
    print(f" - {f}")

# Cleanup
os.remove("test_messy.xlsx")
