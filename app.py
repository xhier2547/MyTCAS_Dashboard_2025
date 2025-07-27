from flask import Flask, render_template, send_file
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import os
import re

app = Flask(__name__)

DATA_FILE = 'mytcas_tuition_data.json'

def load_and_process_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(), "Data file not found. Please run scrape_mytcas.py first."

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not data:
            return pd.DataFrame(), "No data found in the file."

        df = pd.DataFrame(data)
        
        # Clean tuition fee: Extract numerical value
        def extract_tuition(fee_str):
            if isinstance(fee_str, str):
                match = re.search(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', fee_str.replace(',', ''))
                if match:
                    return float(match.group(1))
            return None # Return None for non-numeric or missing fees

        df['tuition_numeric'] = df['tuition_fee'].apply(extract_tuition)
        df.dropna(subset=['tuition_numeric'], inplace=True) # Remove rows where tuition could not be extracted

        # Sort by tuition fee for easier viewing
        df = df.sort_values(by='tuition_numeric', ascending=True).reset_index(drop=True)
        
        return df, None

    except json.JSONDecodeError:
        return pd.DataFrame(), "Error decoding JSON from data file. File might be corrupted."
    except Exception as e:
        return pd.DataFrame(), f"An unexpected error occurred while loading data: {e}"

def generate_plot(df, plot_type='bar'):
    if df.empty:
        return None

    plt.figure(figsize=(12, 7))

    if plot_type == 'bar':
        # Group by university and course to show average tuition, or just show top N
        # For simplicity, let's show top/bottom universities by tuition for selected programs
        top_n = 15 # Display top N cheapest/most expensive
        
        # Ensure 'tuition_numeric' is not empty and has enough data
        if not df['tuition_numeric'].empty:
            df_plot = df.nlargest(top_n, 'tuition_numeric', keep='first').sort_values(by='tuition_numeric', ascending=False)
            
            # Combine university and course name for clearer labels
            df_plot['uni_course'] = df_plot['university_name'] + " - " + df_plot['course_name']

            sns.barplot(x='tuition_numeric', y='uni_course', data=df_plot, palette='viridis')
            plt.title(f'ค่าเทอมสูงสุด {top_n} หลักสูตรที่เกี่ยวข้อง (บาท/ภาคการศึกษา)', fontsize=16)
            plt.xlabel('ค่าเทอม (บาท/ภาคการศึกษา)', fontsize=12)
            plt.ylabel('มหาวิทยาลัย - หลักสูตร', fontsize=12)
            plt.tight_layout()
        else:
            plt.text(0.5, 0.5, 'ไม่พบข้อมูลค่าเทอมที่ถูกต้องสำหรับการสร้างกราฟ', horizontalalignment='center', verticalalignment='center', transform=plt.gca().transAxes)

    elif plot_type == 'average_by_program':
        # Average tuition fee per broad program type
        # For simplicity, let's categorize
        def categorize_program(name):
            if "ปัญญาประดิษฐ์" in name or "AI" in name:
                return "วิศวกรรมปัญญาประดิษฐ์/AI"
            elif "คอมพิวเตอร์" in name or "ซอฟต์แวร์" in name:
                return "วิศวกรรมคอมพิวเตอร์/ซอฟต์แวร์"
            elif "วิทยาการคอมพิวเตอร์" in name:
                return "วิทยาการคอมพิวเตอร์"
            return "อื่นๆ"

        df['program_category'] = df['course_name'].apply(categorize_program)
        avg_tuition_by_category = df.groupby('program_category')['tuition_numeric'].mean().sort_values(ascending=False)
        
        if not avg_tuition_by_category.empty:
            sns.barplot(x=avg_tuition_by_category.values, y=avg_tuition_by_category.index, palette='coolwarm')
            plt.title('ค่าเทอมเฉลี่ยตามประเภทหลักสูตร', fontsize=16)
            plt.xlabel('ค่าเทอมเฉลี่ย (บาท/ภาคการศึกษา)', fontsize=12)
            plt.ylabel('ประเภทหลักสูตร', fontsize=12)
            plt.tight_layout()
        else:
             plt.text(0.5, 0.5, 'ไม่พบข้อมูลค่าเทอมที่ถูกต้องสำหรับการสร้างกราฟ', horizontalalignment='center', verticalalignment='center', transform=plt.gca().transAxes)
    
    # Save plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode()

@app.route('/')
def dashboard():
    df, error_message = load_and_process_data()
    
    if error_message:
        return render_template('dashboard.html', error=error_message)

    if df.empty:
        return render_template('dashboard.html', error="No data available to display. Please run the scraper.")

    # Generate plots
    plot_tuition_bar = generate_plot(df, 'bar')
    plot_average_by_program = generate_plot(df, 'average_by_program')

    # Basic statistics
    summary_stats = {
        'total_programs': len(df),
        'min_tuition': df['tuition_numeric'].min(),
        'max_tuition': df['tuition_numeric'].max(),
        'avg_tuition': df['tuition_numeric'].mean()
    }

    # Data for table display (top 20 for brevity)
    table_data = df.head(20).to_dict(orient='records')

    # Insights for prospective students
    insights = [
        "เปรียบเทียบค่าเทอมของหลักสูตรที่สนใจ เพื่อวางแผนค่าใช้จ่ายได้ง่ายขึ้น",
        "ค้นหามหาวิทยาลัยที่เสนอค่าเทอมที่เข้าถึงได้สำหรับสาขาที่คุณต้องการ",
        "ดูแนวโน้มค่าเทอมเฉลี่ยของแต่ละสาขา เพื่อเป็นข้อมูลในการตัดสินใจ",
        "พิจารณาทั้งค่าเทอมและชื่อเสียงของมหาวิทยาลัยควบคู่กันไป"
    ]

    return render_template(
        'dashboard.html',
        summary=summary_stats,
        table_data=table_data,
        plot_tuition_bar=plot_tuition_bar,
        plot_average_by_program=plot_average_by_program,
        insights=insights
    )

if __name__ == '__main__':
    # Ensure matplotlib uses a non-interactive backend for web apps
    plt.switch_backend('Agg')
    
    # Run the Flask app
    app.run(debug=True, port=5000)