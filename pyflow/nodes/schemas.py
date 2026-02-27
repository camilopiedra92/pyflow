from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HttpConfig(BaseModel):
    url: str = Field(description="Target URL for the HTTP request")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(
        default="GET", description="HTTP method"
    )
    headers: dict[str, str] = Field(
        default_factory=dict, description="HTTP headers to include"
    )
    body: Any = Field(default=None, description="Request body (sent as JSON)")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    raise_for_status: bool = Field(
        default=True, description="Raise an exception on HTTP error status codes"
    )
    allow_private_networks: bool = Field(
        default=False, description="Allow requests to private/internal network addresses"
    )
    max_response_size: int = Field(
        default=10_485_760, description="Max response size in bytes"
    )


class HttpResponse(BaseModel):
    status: int = Field(description="HTTP response status code")
    headers: dict[str, str] = Field(description="HTTP response headers")
    body: Any = Field(description="Response body (parsed JSON or raw text)")


class TransformConfig(BaseModel):
    input: Any = Field(description="Input data or template reference to transform")
    expression: str = Field(description="JSONPath expression to apply")


class ConditionConfig(BaseModel):
    if_: str = Field(alias="if", description="Python expression to evaluate as boolean")

    model_config = ConfigDict(populate_by_name=True)


class AlertConfig(BaseModel):
    webhook_url: str = Field(description="Webhook URL to send alert to")
    message: str = Field(description="Alert message text")


class AlertResponse(BaseModel):
    status: int = Field(description="HTTP response status code from webhook")
    sent: bool = Field(description="Whether the alert was successfully sent")
    error: str | None = Field(default=None, description="Error message if sending failed")


class StorageConfig(BaseModel):
    path: str = Field(description="File path for storage operations")
    action: Literal["read", "write", "append"] = Field(
        default="read", description="Storage action to perform"
    )
    data: Any = Field(default=None, description="Data to write or append")
