import logging
import extruct
import html2text
import json
import os
from openai import OpenAI
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import w3lib.html
from urllib.parse import urlparse, urljoin


class EventScraper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.llm_config = self._load_llm_config()
        self.client = None
        if self.llm_config.get("enabled"):
            self.client = OpenAI(
                base_url=self.llm_config.get("api_base"),
                api_key=self.llm_config.get("api_key", "ollama")
            )

    def _load_llm_config(self):
         # Helper to load config again or pass it in. For simplicity, reading file.
         # In a real app, pass config to __init__
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
            with open(config_path, 'r') as f:
                return json.load(f).get("llm_config", {})
        except:
            return {}

    async def scrape_sites(self, sites):
        """
        Scrapes a list of sites using Playwright and extracts event data.
        Returns:
            list: A list of all extracted event dictionaries.
        """
        config = self._load_llm_config() # Reusing this method to load full config if possible, or just modify _load_llm_config to load full config.
        # Actually _load_llm_config only returns the llm block. Let's load the full config properly or assume defaults.
        # For robustness, let's load it here again or trust defaults.
        crawling_config = self._load_full_config().get('crawling_config', {})
        max_depth = crawling_config.get('max_depth', 2)
        max_pages = crawling_config.get('max_pages_per_site', 10)

        all_events = []
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page()
                
                for start_url in sites:
                    # BFS Initialization
                    queue = [(start_url, 0)] # (url, depth)
                    visited = {start_url}
                    pages_scraped_count = 0
                    
                    domain = urlparse(start_url).netloc
                    self.logger.info(f"Starting crawl for {start_url} (Max Depth: {max_depth}, Max Pages: {max_pages})")

                    while queue and pages_scraped_count < max_pages:
                        current_url, current_depth = queue.pop(0)
                        
                        try:
                            self.logger.info(f"Crawling {current_url} (Depth: {current_depth})...")
                            
                            # Navigate
                            try:
                                response = await page.goto(current_url, wait_until="domcontentloaded", timeout=45000)
                            except Exception as e:
                                self.logger.warning(f"Failed to load {current_url}: {e}")
                                continue

                            if not response or not response.ok:
                                self.logger.warning(f"Skipping {current_url}: HTTP {response.status if response else 'Unknown'}")
                                continue

                            # Optional wait for content
                            try:
                                await page.wait_for_load_state("networkidle", timeout=3000)
                            except:
                                pass

                            # Extract Events from Main Page and ALL Frames (Iframes)
                            frames = page.frames
                            self.logger.info(f"Scanning {len(frames)} frames on {current_url}...")
                            
                            for i, frame in enumerate(frames):
                                try:
                                    # Wait for frame to have some content if possible, or just grab it
                                    frame_url = frame.url
                                    frame_desc = "Main Frame" if frame == page.main_frame else f"Frame {i} ({frame_url[:50]}...)"
                                    
                                    # Simple Frame Analysis (Static HTML)
                                    # Just get the content and analyze it. No navigation.
                                    try:
                                        # Wait for content to stabilize
                                        await frame.wait_for_load_state("domcontentloaded", timeout=5000)
                                    except:
                                        pass
                                    
                                    frame_content = await frame.content()
                                    events = self.extract_events(frame_content, current_url) 
                                    
                                    if events:
                                        self.logger.info(f"  -> Found {len(events)} events in {frame_desc}.")
                                        all_events.extend(events)
                                            
                                except Exception as e:
                                    self.logger.debug(f"Error reading frame {i}: {e}")
                            
                            pages_scraped_count += 1

                            # Find Links if we haven't reached max depth
                            if current_depth < max_depth:
                                links = await self._extract_links(page, domain)
                                for link in links:
                                    if link not in visited:
                                        visited.add(link)
                                        queue.append((link, current_depth + 1))
                        
                        except Exception as e:
                            self.logger.error(f"Error processing {current_url}: {e}")
            
            finally:
                await browser.close()
        
        return all_events
    
    def _load_full_config(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            return {}

    async def _extract_links(self, page, allowed_domain):
        """
        Extracts internal links from the current page.
        """
        links = []
        try:
            # Evaluate JavaScript to get all hrefs
            hrefs = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a[href]')).map(a => a.href);
            }''')
            
            for href in hrefs:
                # Basic cleaning
                href = href.split('#')[0].rstrip('/')
                
                # Check domain
                parsed = urlparse(href)
                if parsed.netloc == allowed_domain:
                    # Filter out non-html extensions roughly
                    if not any(href.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.zip', '.css', '.js']):
                        links.append(href)
        except Exception as e:
            self.logger.warning(f"Error extracting links: {e}")
            
        return list(set(links)) # Unique links

    def extract_events(self, html_content, url):
        """
        Extracts event data using extruct (standards) -> LLM (fallback).
        """
        # Strategy 1 & 2: Standards (JSON-LD, Microdata)
        data = extruct.extract(html_content, base_url=url, uniform=True)
        events = []
        if 'json-ld' in data:
            for item in data['json-ld']:
                if self._is_event(item):
                    events.append(item)
        if 'microdata' in data:
             for item in data['microdata']:
                if self._is_event(item):
                    events.append(item)

        # Strategy 3: LLM Extraction (Fallback)
        if not events and self.client:
            self.logger.info("No structured data found. Attempting LLM extraction...")
            llm_events = self.llm_extraction(html_content)
            events.extend(llm_events)

        # Post-processing: Add source URL to all events
        for event in events:
            event['source_url'] = url

        return events

    def llm_extraction(self, html_content):
        """
        Uses a local LLM to parse events from HTML text.
        """
        # 1. Convert HTML to Markdown to save tokens and reduce noise
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        markdown_text = h.handle(html_content)

        # Truncate if too long (simple safety, can be improved)
        if len(markdown_text) > 10000:
            markdown_text = markdown_text[:10000] + "\n...(truncated)"

        prompt = f"""
        You are an event extraction assistant.
        Extract detailed martial arts event information from the following text.
        Return ONLY a raw JSON array of objects. Do not use markdown formatting.
        Each object should have:
        - name: string
        - startDate: string (ISO format if possible)
        - location: string
        - description: string
        
        If no events are found, return an empty array [].

        Text:
        {markdown_text}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.llm_config.get("model", "llama3"),
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts data as JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean up potential markdown code blocks
            if content.startswith("```"):
                content = content.strip("`")
                if content.startswith("json"):
                    content = content[4:]
            
            extracted = json.loads(content)
            if isinstance(extracted, list):
                for e in extracted:
                    e['@type'] = 'Event' # Standardize
                    e['extraction_method'] = 'llm'
                return extracted
            else:
                self.logger.warning("LLM did not return a list.")
                return []

        except Exception as e:
            self.logger.error(f"LLM extraction failed: {e}")
            return []

    def _is_event(self, item):
        item_type = item.get('@type')
        if isinstance(item_type, str):
            return 'Event' in item_type
        elif isinstance(item_type, list):
             return any('Event' in t for t in item_type)
        return False
