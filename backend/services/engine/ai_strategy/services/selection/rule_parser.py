import json
import logging
import os
from typing import Any, Dict, List

from openai import AsyncOpenAI

from .prompts import TRADE_RULE_PARSER_PROMPT

logger = logging.getLogger(__name__)


class TradeRuleParser:
    def __init__(self):
        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = os.getenv("DASHSCOPE_MODEL", "qwen-max")

        if not api_key:
            logger.warning("DASHSCOPE_API_KEY not found, TradeRuleParser may not work properly.")

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def parse_rules(self, text: str, rule_type: str) -> list[dict[str, Any]]:
        """
        Parse natural language trade rules into structured JSON.

        Args:
            text: User input string (e.g. "当日涨幅超过3%")
            rule_type: 'buy' or 'sell'

        Returns:
            List of rule dictionaries.
        """
        try:
            prompt = f"Rule Type: {rule_type}\nUser Input: {text}"

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": TRADE_RULE_PARSER_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )

            content = response.choices[0].message.content.strip()

            # Basic cleanup if model outputs markdown blocks
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()

            rules = json.loads(content)
            return rules if isinstance(rules, list) else []

        except Exception as e:
            logger.error(f"TradeRuleParser failed: {e}")
            return []


# Singleton pattern
_rule_parser = None


def get_trade_rule_parser() -> TradeRuleParser:
    global _rule_parser
    if _rule_parser is None:
        _rule_parser = TradeRuleParser()
    return _rule_parser
