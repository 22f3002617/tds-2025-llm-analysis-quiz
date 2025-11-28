import abc
import asyncio
import base64
import dataclasses
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import override, TypedDict

from openai.types.responses import ResponseCustomToolCallOutputParam, ResponseInputImageParam, ResponseInputTextParam, \
    ResponseInputFileParam
from openai.types.responses.response_custom_tool_call_output_param import OutputOutputContentList
from playwright.async_api import async_playwright

from setup_logger import setup as logger_setup
import config

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class ScrapedDetails:
    url: str
    html_content: str
    script_result: str | None
    screenshot: bytes | None

    def as_openai_response_api_input(self) -> list[OutputOutputContentList]:
        result: list[OutputOutputContentList] = [ResponseInputFileParam(
            type="input_file",
            file_data=self.html_content,
            filename="scraped_content.html",
        )]
        if self.script_result is not None:
            result.append(
                ResponseInputTextParam(
                    type="input_text",
                    text=self.script_result,
                )
            )
        if self.screenshot is not None:
            result.append(
                ResponseInputImageParam(
                    type="input_image",
                    detail="high",
                    image_url="data:image/png;base64," + base64.b64encode(self.screenshot).decode('utf-8'),
                )
            )

        return result

    def save(self, agent_log_dir):
        timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        content_path = Path(agent_log_dir) / f"scraped_content_{timestamp}.html"
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(self.html_content)
        if self.script_result is not None:
            script_path = Path(agent_log_dir) / f"script_result_{timestamp}.txt"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(self.script_result)
        if self.screenshot is not None:
            screenshot_path = Path(agent_log_dir) / f"screenshot_{timestamp}.png"
            with open(screenshot_path, "wb") as f:
                f.write(self.screenshot)


class Scraper(abc.ABC):
    def __init__(self, agent_path: Path,
                 headless: bool):
        logger.info(f"Initializing Scraper with headless={headless}, agent_path={agent_path}")
        self.agent_path = agent_path
        os.makedirs(self.agent_path, exist_ok=True)
        self.headless = headless

    @abc.abstractmethod
    async def scrape(self, url: str,
                     script: str | None = None,
                     screenshot_required: bool = False,
                     request_id: str | None = None) -> ScrapedDetails:
        pass

    async def save_script(self, url: str, script: str, request_id: str | None = None) -> Path:
        """
        Save script to a file. name the file based on the url and current timestamp.
            >>> url = "https://example.com/page"
            >>> # expected will be like "example_com_page_2024-06-01T12:00:00.js"
        :param request_id:
        :param url:
        :param script:
        :return:
        """
        sanitized_url = url.replace("https://", "").replace("/", "_")
        timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        if request_id:
            file_path = self.agent_path / request_id / f"{sanitized_url}_{timestamp}.js"
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            file_path = self.agent_path / f"{sanitized_url}_{timestamp}.js"
        self.agent_path.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(script)
        return file_path

    async def save_screenshot(self, url: str, screenshot_bytes: bytes, request_id: str | None = None) -> Path:
        """
        Save screenshot bytes to a file. name the file based on the url and current timestamp.
            >>> url = "https://example.com/page"
            >>> # expected will be like "example_com_page_2024-06-01T12:00:00.png"
        :param request_id:
        :param url:
        :param screenshot_bytes:
        :return:
        """
        sanitized_url = url.replace("https://", "").replace("/", "_")
        timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        if request_id:
            file_path = self.agent_path / request_id / f"{sanitized_url}_{timestamp}.png"
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            file_path = self.agent_path / f"{sanitized_url}_{timestamp}.png"
        self.agent_path.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(screenshot_bytes)
        return file_path

    async def save_content(self, url: str, content: str, request_id: str | None = None) -> Path:
        """
        Save scraped content to a file. name the file based on the url and current timestamp.
            >>> url = "https://example.com/page"
            >>> # expected will be like "example_com_page_2024-06-01T12:00:00.html"
        :param request_id:
        :param url:
        :param content:
        :return:
        """
        sanitized_url = url.replace("https://", "").replace("/", "_")
        timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        if request_id:
            file_path = self.agent_path / request_id / f"{sanitized_url}_{timestamp}.html"
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            file_path = self.agent_path / f"{sanitized_url}_{timestamp}.html"
        self.agent_path.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path


class PlaywrightScraper(Scraper):
    @override
    async def scrape(self, url: str,
                     script: str | None = None,
                     screenshot_required: bool = False,
                     request_id: str | None = None) -> ScrapedDetails:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            await page.goto(url)
            if script:
                # await self.save_script(url, script, request_id)
                script_result = await page.evaluate(script)
                logger.info(f"Script executed with result: {script_result}")
            if screenshot_required:
                screenshot_bytes = await page.screenshot()
                # await self.save_screenshot(url, screenshot_bytes, request_id)

            content = await page.content()
            # await self.save_content(url, content, request_id)
        return ScrapedDetails(url=url, html_content=content, script_result=script_result if script else None,
                              screenshot=screenshot_bytes if screenshot_required else None)
        # return content, script_result if script else None, screenshot_bytes if screenshot_required else None


class ScraperFactory:
    _instances: dict[str, Scraper] = {}
    _registry: dict[str, type[Scraper]] = {
        "playwright": PlaywrightScraper,
    }

    @classmethod
    def get(cls, scraper_type: str) -> Scraper:
        if scraper_type not in cls._instances:
            if scraper_type not in cls._registry:
                raise ValueError(f"Unknown scraper type: {scraper_type}")
            scraper_class = cls._registry[scraper_type]
            cls._instances[scraper_type] = scraper_class(
                agent_path=config.AGENT_LOG_BASE_PATH,
                headless=config.HEADLESS_SCRAPER
            )
        return cls._instances[scraper_type]


async def main() -> int:
    logger_setup()
    scraper = ScraperFactory.get("playwright")

    url = "https://example.com"
    content = await scraper.scrape(url, screenshot_required=True)
    print(content)
    return 0


if __name__ == '__main__':
    exit(asyncio.run(main()))
