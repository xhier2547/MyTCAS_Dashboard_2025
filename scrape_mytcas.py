import asyncio
from playwright.async_api import async_playwright
import json
import re
import os

async def scrape_mytcas_detailed_data():
    search_terms = [
        "วิศวกรรมปัญญาประดิษฐ์"
    ]
    
    all_scraped_data = [] # เก็บข้อมูลทั้งหมด
    
    async with async_playwright() as p:
        # เปิดเบราว์เซอร์ Microsoft Edge โดยใช้ channel 'msedge' ผ่าน p.chromium.launch()
        # ต้องแน่ใจว่าได้ติดตั้ง Playwright Edge drivers ด้วยคำสั่ง 'playwright install msedge' แล้ว
        browser = await p.chromium.launch(channel='msedge', headless=False) 
        page = await browser.new_page()

        print("กำลังไปยัง https://course.mytcas.com/ ...")
        await page.goto("https://course.mytcas.com/", wait_until="domcontentloaded")
        
        # --- Selector ที่อิงจากรูปภาพทั้งหมดที่ให้มา ---
        
        # Selector สำหรับช่องค้นหาบนหน้าแรก: ใช้ id="input-search" ตามที่เห็นในรูปภาพ
        SEARCH_INPUT_SELECTOR = '#search'
        
        # Selector สำหรับแต่ละรายการผลลัพธ์การค้นหาบนหน้าแรก:
        # ul.t-programs > li > a[href*="/program/"] ตามที่เห็นใน image_cfdbbd.png และ image_d04fff.png
        COURSE_RESULT_LINK_SELECTOR = 'ul.t-programs > li > a[href*="/programs/"]'
        
        # Selector ภายในหน้าแต่ละหลักสูตร (อิงจาก image_cee6cc.png และ image_cfcc64.jpg)
        # ชื่อมหาวิทยาลัย: h2 ภายใน div.container.py-3
        UNI_NAME_SELECTOR = 'div.container.py-3 h2'
        # ชื่อหลักสูตรเต็ม: h3 ภายใน div.container.py-3
        COURSE_FULL_NAME_SELECTOR = 'div.container.py-3 h3'
        
        # Selector สำหรับ "ค่าใช้จ่าย" (label) และ Element ที่มีค่าของมัน
        # จาก image_cfcc64.jpg: <div class="col-6 col-md-6">ค่าใช้จ่าย</div>
        # และ <div class="col-6 col-md-6">อัตราค่าเล่าเรียน 28,000.-/ภาคการศึกษา</div>
        TUITION_VALUE_SELECTOR = 'div.col-6.col-md-6:has-text("ค่าใช้จ่าย") + div.col-6.col-md-6'
        
        for term in search_terms:
            print(f"\n===== กำลังประมวลผลคำค้นหา: '{term}' =====")
            
            # 1. ค้นหา
            try:
                # รอให้ช่องค้นหาปรากฏก่อน
                await page.wait_for_selector(SEARCH_INPUT_SELECTOR, timeout=15000)
                
                # คลิกที่ช่องค้นหาเพื่อให้โฟกัส
                await page.click(SEARCH_INPUT_SELECTOR)
                print("คลิกที่ช่องค้นหาแล้ว")
                
                # ล้างช่องค้นหา (สำคัญมากก่อนจะกรอกใหม่สำหรับคำค้นถัดไป)
                await page.fill(SEARCH_INPUT_SELECTOR, '') #
                
                # ใช้ page.type() เพื่อจำลองการพิมพ์ทีละตัวอักษร พร้อม delay
                await page.type(SEARCH_INPUT_SELECTOR, term, delay=100) #
                print(f"กรอกคำค้นหา '{term}' แล้ว")
                
                # กด Enter เพื่อให้ผลลัพธ์ขึ้นตามรูป
                await page.keyboard.press('Enter') #
                
                # รอให้ network สงบหลังค้นหา และรอให้ผลลัพธ์ปรากฏ
                await page.wait_for_load_state('networkidle', timeout=15000) #
                # อาจต้องเพิ่ม delay เล็กน้อยหลังกด Enter ถ้าผลลัพธ์ไม่ขึ้นทันที
                await page.wait_for_timeout(1000) # รอ 1 วินาที (ปรับค่าได้ตามความเหมาะสม)

            except Exception as e:
                print(f"  - เกิดข้อผิดพลาดในการค้นหาสำหรับ '{term}': {e}")
                continue # ข้ามไปยังคำค้นหาถัดไป
            
            # ดึงลิงก์ของแต่ละหลักสูตรจากผลการค้นหา
            current_term_links = set() # ใช้ set เพื่อป้องกันลิงก์ซ้ำ
            try:
                # รอให้ผลลัพธ์การค้นหา (รายการ ul.t-programs > li) ปรากฏ
                # เพิ่ม timeout สำหรับการรอ selector ผลลัพธ์ อาจจะใช้เวลาโหลดนาน
                await page.wait_for_selector(COURSE_RESULT_LINK_SELECTOR, state='visible', timeout=20000)
                
                # ดึง href ของลิงก์ทั้งหมด
                link_locators = await page.locator(COURSE_RESULT_LINK_SELECTOR).all()
                if not link_locators:
                    print(f"  - ไม่พบลิงก์ผลลัพธ์สำหรับ '{term}'")
                    continue

                for locator in link_locators:
                    href = await locator.get_attribute('href')
                    if href and "/programs/" in href: # ตรวจสอบให้แน่ใจว่าเป็นลิงก์หลักสูตร
                        full_url = f"https://course.mytcas.com{href}" # สร้าง URL เต็ม
                        current_term_links.add(full_url)
                
                print(f"  - พบ {len(current_term_links)} ลิงก์หลักสูตรที่เกี่ยวข้องสำหรับ '{term}'")

            except Exception as e:
                print(f"  - เกิดข้อผิดพลาดในการดึงลิงก์จากผลลัพธ์สำหรับ '{term}': {e}")
                continue

            # 3. วนลูปเข้าแต่ละลิงก์และดึงข้อมูลรายละเอียด
            for i, course_url in enumerate(list(current_term_links)): # แปลงเป็น list เพื่อวนลูป
                print(f"  กำลังดึงข้อมูลจากลิงก์ที่ {i+1}/{len(current_term_links)}: {course_url}")
                course_page = await browser.new_page() # เปิดแท็บใหม่สำหรับแต่ละหลักสูตร
                try:
                    await course_page.goto(course_url, wait_until="domcontentloaded", timeout=30000)
                    
                    # เพิ่มการรอ 2 วินาทีหลังจากเปิดลิงก์ใหม่ตามคำขอ
                    await course_page.wait_for_timeout(2000) 

                    # 4. ดึงข้อมูลจากหน้าหลักสูตร
                    uni_name = "N/A"
                    course_full_name = "N/A"
                    tuition_fee = "N/A"

                    try:
                        # ชื่อมหาวิทยาลัย
                        uni_name_element = course_page.locator(UNI_NAME_SELECTOR).first
                        if await uni_name_element.is_visible(): 
                            uni_name = (await uni_name_element.text_content()).strip()

                        # ชื่อหลักสูตรเต็ม
                        course_full_name_element = course_page.locator(COURSE_FULL_NAME_SELECTOR).first
                        if await course_full_name_element.is_visible(): 
                            course_full_name = (await course_full_name_element.text_content()).strip()

                        # ค่าใช้จ่าย (ค่าเทอม)
                        tuition_value_element = course_page.locator(TUITION_VALUE_SELECTOR).first
                        if await tuition_value_element.count() > 0 and await tuition_value_element.is_visible(): 
                            tuition_fee = await tuition_value_element.text_content()
                            tuition_fee = tuition_fee.strip() #
                                
                    except Exception as e_detail:
                        print(f"    - เกิดข้อผิดพลาดในการดึงรายละเอียดหลักจากหน้า {course_url}: {e_detail}")

                    # กรองเฉพาะหลักสูตรที่เกี่ยวข้องกับคำค้นหา
                    # ตรวจสอบว่า ชื่อหลักสูตร หรือชื่อมหาวิทยาลัย มีคำที่เกี่ยวข้องอยู่ในกลุ่มเป้าหมาย
                    if any(k_word in course_full_name or k_word in uni_name for k_word in ["ปัญญาประดิษฐ์", "คอมพิวเตอร์", "AI", "Software", "วิทยาการ", "วิศวกรรม", "เทคโนโลยีสารสนเทศ"]):
                         # ตรวจสอบว่าได้ข้อมูลหลักครบถ้วนก่อนเพิ่ม
                        if "N/A" not in uni_name and "N/A" not in course_full_name: 
                            all_scraped_data.append({
                                "university_name": uni_name,
                                "course_name": course_full_name,
                                "tuition_fee": tuition_fee,
                                "source_url": course_url,
                                "search_term_used": term 
                            })
                            print(f"    - ดึงข้อมูลได้: มหาวิทยาลัย: {uni_name} | หลักสูตร: {course_full_name} | ค่าเทอม: {tuition_fee}")
                        else:
                            print(f"    - ดึงข้อมูลหลัก (ชื่อมหาลัย/หลักสูตร) ไม่ครบถ้วนจาก {course_url}")

                except Exception as e_page:
                    print(f"  - เกิดข้อผิดพลาดในการเข้าถึงหน้า {course_url}: {e_page}")
                finally:
                    await course_page.close() # ปิดแท็บหลังจากดึงข้อมูลเสร็จ

        await browser.close() 
        print("\nปิดเบราว์เซอร์เรียบร้อยแล้ว")
        
        # บันทึกข้อมูลที่ได้ลงในไฟล์ JSON
        with open('mytcas_tuition_data.json', 'w', encoding='utf-8') as f:
            json.dump(all_scraped_data, f, ensure_ascii=False, indent=4)
        print(f"บันทึกข้อมูลทั้งหมด {len(all_scraped_data)} รายการลงใน mytcas_tuition_data.json แล้ว")
        
        return all_scraped_data

if __name__ == "__main__":
    asyncio.run(scrape_mytcas_detailed_data())