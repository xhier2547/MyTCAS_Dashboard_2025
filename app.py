import os
import glob
import pandas as pd
import re
import json
from flask import Flask, render_template

# Initialize the Flask application
app = Flask(__name__)

def clean_fee_data(fee_str):
    """
    Extracts numerical values from a string containing fee information.
    Handles various formats like 'ประมาณ 25,000 บาท' or '15000'.
    """
    if not isinstance(fee_str, str):
        return 0
    
    # Remove commas and find all numbers in the string
    fee_str = fee_str.replace(',', '')
    numbers = re.findall(r'\d+\.?\d*', fee_str)
    
    if numbers:
        # Return the first number found as a float
        return float(numbers[0])
    return 0

@app.route('/')
def dashboard():
    """
    Main route for the dashboard. Finds the latest CSV, processes data,
    and renders the dashboard page.
    """
    try:
        # Find the most recent tcas_data CSV file
        list_of_files = glob.glob('tcas_data.csv')
        if not list_of_files:
            return render_template('error.html', message="ไม่พบไฟล์ข้อมูล CSV (tcas_data.csv)")
            
        latest_file = max(list_of_files, key=os.path.getctime)
        print(f"กำลังใช้ไฟล์ข้อมูล: {latest_file}")

        df = pd.read_csv(latest_file)

        # --- Data Processing ---
        df['fee_numeric'] = df['ค่าใช้จ่าย'].apply(clean_fee_data)
        df_with_fee = df[df['fee_numeric'] > 0].copy()

        # 1. Overall Statistics
        stats = {}
        if not df_with_fee.empty:
            stats = {
                'average_fee': df_with_fee['fee_numeric'].mean(),
                'max_fee': df_with_fee['fee_numeric'].max(),
                'min_fee': df_with_fee['fee_numeric'].min(),
            }

        # 2. Top Programs Chart (Highest Cost)
        df_sorted_programs = df_with_fee.sort_values('fee_numeric', ascending=False)
        top_programs_chart_data = df_sorted_programs.head(20).iloc[::-1]
        top_programs_labels = (top_programs_chart_data['ชื่อหลักสูตร'] + " (" + top_programs_chart_data['มหาวิทยาลัย'] + ")").tolist()
        top_programs_values = top_programs_chart_data['fee_numeric'].tolist()

        # 3. University/Campus Statistics
        university_stats = pd.DataFrame()
        if not df_with_fee.empty:
            university_stats = df_with_fee.groupby('มหาวิทยาลัย').agg(
                program_count=('fee_numeric', 'size'),
                average_fee=('fee_numeric', 'mean')
            ).reset_index().sort_values('average_fee', ascending=False)

        # 4. University Average Cost Chart
        top_uni_chart_data = university_stats.head(15).iloc[::-1]
        uni_chart_labels = top_uni_chart_data['มหาวิทยาลัย'].tolist()
        uni_chart_values = top_uni_chart_data['average_fee'].tolist()

        return render_template(
            'index.html',
            # Overall Info
            file_name=os.path.basename(latest_file),
            total_programs=len(df),
            programs_with_fee=len(df_with_fee),
            stats=stats,
            # Top Programs Chart
            top_programs_labels=json.dumps(top_programs_labels),
            top_programs_values=json.dumps(top_programs_values),
            # University Stats Table
            university_stats=university_stats.to_dict(orient='records'),
            # University Average Cost Chart
            uni_chart_labels=json.dumps(uni_chart_labels),
            uni_chart_values=json.dumps(uni_chart_values),
            # Full Data Table
            table_data=df_sorted_programs.to_dict(orient='records')
        )

    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', message=f"เกิดข้อผิดพลาดในการประมวลผล: {e}")

if __name__ == '__main__':
    app.run(debug=True)