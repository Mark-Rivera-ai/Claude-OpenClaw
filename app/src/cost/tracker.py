"""
OpenClaw Cost Tracker

Token counting, cost calculation, and CloudWatch metrics for API usage.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# Claude Sonnet 4 pricing (USD per million tokens)
CLAUDE_SONNET_4_INPUT_PRICE = 3.0  # $3 per 1M input tokens
CLAUDE_SONNET_4_OUTPUT_PRICE = 15.0  # $15 per 1M output tokens


class CostTracker:
    """
    Tracks API usage costs and publishes metrics to CloudWatch.

    Features:
    - Token counting and USD calculation
    - Monthly budget tracking with $50 default
    - CloudWatch metric publishing
    """

    def __init__(
        self,
        monthly_budget_usd: float = 50.0,
        cloudwatch_namespace: str = "OpenClaw/Costs",
        aws_region: str = "us-east-1",
        enabled: bool = True,
    ):
        """
        Initialize the cost tracker.

        Args:
            monthly_budget_usd: Monthly budget limit in USD
            cloudwatch_namespace: CloudWatch metrics namespace
            aws_region: AWS region for CloudWatch
            enabled: Whether cost tracking is enabled
        """
        self._enabled = enabled
        self._monthly_budget = monthly_budget_usd
        self._namespace = cloudwatch_namespace
        self._aws_region = aws_region

        # Current month tracking
        self._current_month = self._get_current_month()
        self._monthly_input_tokens = 0
        self._monthly_output_tokens = 0
        self._monthly_cost_usd = 0.0

        # Total tracking
        self._total_requests = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0

        # CloudWatch client
        self._cloudwatch = None
        if enabled:
            try:
                self._cloudwatch = boto3.client("cloudwatch", region_name=aws_region)
            except Exception as e:
                logger.warning(f"Failed to initialize CloudWatch client: {e}")

    @staticmethod
    def _get_current_month() -> str:
        """Get current month as YYYY-MM string."""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _check_month_rollover(self) -> None:
        """Reset monthly counters if month has changed."""
        current = self._get_current_month()
        if current != self._current_month:
            logger.info(f"Month rollover: {self._current_month} -> {current}")
            self._current_month = current
            self._monthly_input_tokens = 0
            self._monthly_output_tokens = 0
            self._monthly_cost_usd = 0.0

    @staticmethod
    def calculate_cost(
        input_tokens: int,
        output_tokens: int,
        input_price_per_million: float = CLAUDE_SONNET_4_INPUT_PRICE,
        output_price_per_million: float = CLAUDE_SONNET_4_OUTPUT_PRICE,
    ) -> float:
        """
        Calculate cost in USD for given token counts.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            input_price_per_million: Price per million input tokens
            output_price_per_million: Price per million output tokens

        Returns:
            Cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * input_price_per_million
        output_cost = (output_tokens / 1_000_000) * output_price_per_million
        return input_cost + output_cost

    def track_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        provider: str = "claude",
    ) -> dict[str, Any]:
        """
        Track token usage and calculate costs.

        Args:
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            provider: Provider name (only "claude" incurs cost)

        Returns:
            Dictionary with tracking results
        """
        if not self._enabled:
            return {"tracked": False, "reason": "cost_tracking_disabled"}

        # Only track costs for Claude (Llama is free/self-hosted)
        if provider != "claude":
            return {
                "tracked": True,
                "provider": provider,
                "cost_usd": 0.0,
                "reason": "no_cost_provider",
            }

        self._check_month_rollover()

        # Calculate cost
        cost = self.calculate_cost(input_tokens, output_tokens)

        # Update counters
        self._monthly_input_tokens += input_tokens
        self._monthly_output_tokens += output_tokens
        self._monthly_cost_usd += cost

        self._total_requests += 1
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cost_usd += cost

        # Publish metrics to CloudWatch
        self._publish_metrics(input_tokens, output_tokens, cost)

        return {
            "tracked": True,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "monthly_cost_usd": round(self._monthly_cost_usd, 4),
            "budget_remaining_usd": round(self._monthly_budget - self._monthly_cost_usd, 4),
            "budget_utilization_pct": round(
                (self._monthly_cost_usd / self._monthly_budget) * 100, 2
            ),
        }

    def _publish_metrics(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """Publish metrics to CloudWatch."""
        if not self._cloudwatch:
            return

        try:
            metrics = [
                {
                    "MetricName": "InputTokens",
                    "Value": input_tokens,
                    "Unit": "Count",
                },
                {
                    "MetricName": "OutputTokens",
                    "Value": output_tokens,
                    "Unit": "Count",
                },
                {
                    "MetricName": "TotalTokens",
                    "Value": input_tokens + output_tokens,
                    "Unit": "Count",
                },
                {
                    "MetricName": "CostUSD",
                    "Value": cost_usd,
                    "Unit": "None",
                },
                {
                    "MetricName": "MonthlyCostUSD",
                    "Value": self._monthly_cost_usd,
                    "Unit": "None",
                },
                {
                    "MetricName": "MonthlyBudgetUtilization",
                    "Value": (self._monthly_cost_usd / self._monthly_budget) * 100,
                    "Unit": "Percent",
                },
            ]

            self._cloudwatch.put_metric_data(
                Namespace=self._namespace,
                MetricData=metrics,
            )
        except ClientError as e:
            logger.warning(f"Failed to publish CloudWatch metrics: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error publishing metrics: {e}")

    def is_budget_exceeded(self) -> bool:
        """Check if monthly budget has been exceeded."""
        self._check_month_rollover()
        return self._monthly_cost_usd >= self._monthly_budget

    def get_budget_remaining(self) -> float:
        """Get remaining budget for the current month in USD."""
        self._check_month_rollover()
        return max(0.0, self._monthly_budget - self._monthly_cost_usd)

    def get_budget_utilization(self) -> float:
        """Get budget utilization as a percentage (0-100+)."""
        self._check_month_rollover()
        return (self._monthly_cost_usd / self._monthly_budget) * 100

    def get_stats(self) -> dict[str, Any]:
        """
        Get comprehensive cost statistics.

        Returns:
            Dictionary with all cost tracking stats
        """
        self._check_month_rollover()

        return {
            "enabled": self._enabled,
            "monthly_budget_usd": self._monthly_budget,
            "current_month": self._current_month,
            "monthly": {
                "input_tokens": self._monthly_input_tokens,
                "output_tokens": self._monthly_output_tokens,
                "total_tokens": self._monthly_input_tokens + self._monthly_output_tokens,
                "cost_usd": round(self._monthly_cost_usd, 4),
                "budget_remaining_usd": round(
                    max(0.0, self._monthly_budget - self._monthly_cost_usd), 4
                ),
                "budget_utilization_pct": round(
                    (self._monthly_cost_usd / self._monthly_budget) * 100, 2
                ),
                "budget_exceeded": self._monthly_cost_usd >= self._monthly_budget,
            },
            "total": {
                "requests": self._total_requests,
                "input_tokens": self._total_input_tokens,
                "output_tokens": self._total_output_tokens,
                "total_tokens": self._total_input_tokens + self._total_output_tokens,
                "cost_usd": round(self._total_cost_usd, 4),
            },
            "pricing": {
                "model": "claude-sonnet-4",
                "input_per_million_usd": CLAUDE_SONNET_4_INPUT_PRICE,
                "output_per_million_usd": CLAUDE_SONNET_4_OUTPUT_PRICE,
            },
        }
