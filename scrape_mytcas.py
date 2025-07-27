import asyncio
import pandas as pd
from playwright.async_api import async_playwright, Page, Browser
from datetime import datetime
import traceback

# --- Constants and Configuration ---

BASE_URL = "https://course.mytcas.com"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
HEADLESS_MODE = False  # Set to True to run without a visible browser window

# Selectors are grouped for easier management
SEARCH_SELECTORS = [
    "input[placeholder='พิมพ์ชื่อมหาวิทยาลัย คณะ หรือหลักสูตร']",
    "input[placeholder*='ค้นหา']",
]
RESULTS_LIST_SELECTOR = ".t-programs > li"
PROGRAM_LINK_SELECTOR = "a"
PROGRAM_TYPE_SELECTORS = [
    "dt:has-text('ประเภทหลักสูตร') + dd",
    ".program-type"
]
FEE_SELECTORS = [
    "dt:has-text('ค่าใช้จ่าย') + dd",
    "dt:has-text('ค่าธรรมเนียม') + dd",
    ".fee-info",
    ".tuition-fee"
]


class TCASScraper:
    """
    A class to scrape program information from the myTCAS website.
    """
    def __init__(self, keywords: list[str]):
        self.keywords = keywords
        self.results_df = pd.DataFrame()

    async def run(self):
        """
        Initializes the scraper, runs the scraping process, and saves the results.
        """
        print("🚀 Starting TCAS Scraper...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS_MODE)
            context = await browser.new_context(
                locale='th-TH',
                user_agent=USER_AGENT
            )
            page = await context.new_page()

            try:
                all_program_links = await self._collect_all_program_links(page)
                if not all_program_links:
                    print("❌ No programs found matching the keywords.")
                    return

                scraped_data = await self._scrape_program_details(page, all_program_links)
                if scraped_data:
                    self.results_df = pd.DataFrame(scraped_data)
                    self._save_to_csv()

            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                print(traceback.format_exc())
            finally:
                await browser.close()
                print("✅ Scraper has finished its job.")

    async def _collect_all_program_links(self, page: Page) -> list[dict]:
        """
        Searches for keywords and collects links to program detail pages.
        """
        program_links = []
        unique_urls = set()

        for keyword in self.keywords:
            print(f"\n🔎 Searching for keyword: '{keyword}'")
            try:
                await page.goto(BASE_URL, wait_until='domcontentloaded')

                # Find and fill the search box
                search_input = None
                for selector in SEARCH_SELECTORS:
                    search_input = page.locator(selector).first
                    if await search_input.is_visible(timeout=5000):
                        break
                
                if not search_input:
                    print("  - Could not find the search input box.")
                    continue

                await search_input.fill(keyword)
                await search_input.press("Enter")
                await page.wait_for_timeout(2000) # Wait for results to load

                # Collect results
                results = await page.query_selector_all(RESULTS_LIST_SELECTOR)
                print(f"  - Found {len(results)} results.")

                for item in results:
                    link_element = await item.query_selector(PROGRAM_LINK_SELECTOR)
                    if not link_element:
                        continue

                    relative_url = await link_element.get_attribute("href")
                    full_url = f"{BASE_URL}{relative_url}"

                    if full_url not in unique_urls:
                        unique_urls.add(full_url)
                        text_content = (await item.inner_text()).split('\n')
                        program_links.append({
                            'keyword': keyword,
                            'program_name': text_content[0].strip() if len(text_content) > 0 else "N/A",
                            'faculty': text_content[1].strip() if len(text_content) > 1 else "N/A",
                            'university': text_content[2].strip() if len(text_content) > 2 else "N/A",
                            'url': full_url
                        })

            except Exception as e:
                print(f"  - Error while searching for '{keyword}': {e}")
        
        print(f"\nCollected {len(program_links)} unique program links.")
        return program_links

    async def _scrape_program_details(self, page: Page, program_links: list[dict]) -> list[dict]:
        """
        Navigates to each program URL and extracts detailed information.
        """
        all_details = []
        total = len(program_links)

        for i, program in enumerate(program_links, 1):
            print(f"\n[{i}/{total}] Scraping: {program['program_name']}")
            print(f"  - University: {program['university']}")

            try:
                await page.goto(program['url'], wait_until='domcontentloaded')

                program_type = await self._get_text_from_selectors(page, PROGRAM_TYPE_SELECTORS)
                fee = await self._get_text_from_selectors(page, FEE_SELECTORS)

                all_details.append({
                    'คำค้น': program['keyword'],
                    'ชื่อหลักสูตร': program['program_name'],
                    'มหาวิทยาลัย': program['university'],
                    'คณะ': program['faculty'],
                    'ประเภทหลักสูตร': program_type,
                    'ค่าใช้จ่าย': fee,
                    'ลิงก์': program['url'],
                    'วันที่เก็บข้อมูล': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                print(f"  - Fee: {fee}")
                await asyncio.sleep(1) # Be respectful to the server

            except Exception as e:
                print(f"  - Failed to scrape {program['url']}: {e}")

        return all_details
    
    async def _get_text_from_selectors(self, page: Page, selectors: list[str]) -> str:
        """
        Tries a list of selectors and returns the inner text of the first one found.
        """
        for selector in selectors:
            element = page.locator(selector).first
            if await element.is_visible(timeout=1000):
                return (await element.inner_text()).strip()
        return "ไม่พบข้อมูล"

    def _save_to_csv(self):
        """
        Saves the scraped data to a CSV file.
        """
        if self.results_df.empty:
            print("No data to save.")
            return

        filename = f"tcas_data.csv"
        
        self.results_df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print("\n" + "="*50)
        print(f"Data saved successfully to {filename}")
        print(f"Total records: {len(self.results_df)}")
        
        # Display summary
        print("\nSummary:")
        print(self.results_df['คำค้น'].value_counts())
        
        with_fee_count = len(self.results_df[self.results_df['ค่าใช้จ่าย'] != 'ไม่พบข้อมูล'])
        print(f"\nPrograms with fee information: {with_fee_count}/{len(self.results_df)}")
        print("="*50)


def get_user_keywords() -> list[str]:
    """
    Prompts the user to select or enter keywords.
    """
    print("\nSelect search keywords:")
    print("1. วิศวกรรมปัญญาประดิษฐ์ (Artificial Intelligence Engineering)")
    print("2. วิศวกรรมคอมพิวเตอร์ (Computer Engineering)")
    print("3. Both of the above")
    print("4. Enter custom keywords")

    choice = input("Enter your choice (1-4): ").strip()
    
    if choice == "1":
        return ["วิศวกรรมปัญญาประดิษฐ์"]
    if choice == "2":
        return ["วิศวกรรมคอมพิวเตอร์"]
    if choice == "3":
        return ["วิศวกรรม ปัญญาประดิษฐ์", "วิศวกรรม คอมพิวเตอร์"]
    if choice == "4":
        custom = input("Enter keywords, separated by commas: ")
        return [k.strip() for k in custom.split(',') if k.strip()]
        
    print("Invalid choice. Defaulting to Computer Engineering.")
    return ["วิศวกรรมคอมพิวเตอร์"]


async def main():
    """
    Main function to run the scraper.
    """
    try:
        keywords = get_user_keywords()
        scraper = TCASScraper(keywords=keywords)
        await scraper.run()
    except KeyboardInterrupt:
        print("\n⏹️ User stopped the program.")
    except Exception as e:
        print(f"\nA critical error occurred in main: {e}")
        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())