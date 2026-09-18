"""
HTML sanitization utilities for preventing XSS vulnerabilities.
"""

import bleach


def sanitize_documentation_content(content: str, allow_markdown: bool = True) -> str:
    """
    Sanitize documentation content to prevent XSS vulnerabilities.

    Args:
        content: Raw documentation content
        allow_markdown: Whether to allow markdown formatting tags

    Returns:
        Sanitized content safe for storage and rendering

    Raises:
        ValueError: If content contains dangerous HTML that cannot be sanitized
    """
    if not content:
        return content

    # Define allowed tags for markdown content
    if allow_markdown:
        allowed_tags = [
            # Basic text formatting
            "p",
            "br",
            "hr",
            # Headers
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            # Text styling
            "strong",
            "b",
            "em",
            "i",
            "u",
            "strike",
            "del",
            # Lists
            "ul",
            "ol",
            "li",
            # Links and images
            "a",
            "img",
            # Code blocks
            "pre",
            "code",
            # Blockquotes
            "blockquote",
            # Tables
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
            # Definition lists
            "dl",
            "dt",
            "dd",
        ]

        allowed_attributes = {
            "a": ["href", "title", "target"],
            "img": ["src", "alt", "title", "width", "height"],
            "code": ["class"],
            "pre": ["class"],
            "*": ["class", "id"],  # Allow class and id on any element
        }
    else:
        # For non-markdown content, only allow basic text formatting
        allowed_tags = ["p", "br", "strong", "b", "em", "i"]
        allowed_attributes = {}

    # Define allowed protocols for links and images
    allowed_protocols = ["http", "https", "mailto"]

    try:
        # Sanitize the content
        sanitized = bleach.clean(
            content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True,  # Remove disallowed tags completely
        )

        # Additional security check: reject if content contains script tags
        # (bleach should remove them, but this is a double-check)
        if "<script" in sanitized.lower():
            raise ValueError("Content contains dangerous HTML that cannot be sanitized")

        return sanitized

    except Exception as e:
        # If bleach fails for any reason, reject the content
        raise ValueError(f"Content could not be sanitized: {str(e)}")


def validate_documentation_content(content: str) -> None:
    """
    Validate documentation content for security issues.

    Args:
        content: Documentation content to validate

    Raises:
        ValueError: If content contains dangerous patterns
    """
    if not content:
        return

    # Check for obvious XSS patterns
    dangerous_patterns = {
        "<script",
        "javascript:",
        "onabort=",
        "onafterprint=",
        "onbeforecopy=",
        "onbeforecut=",
        "onbeforepaste=",
        "onbeforeprint=",
        "onbeforeunload=",
        "onblur=",
        "onbounce=",
        "onchange=",
        "oncontextmenu=",
        "oncopy=",
        "oncut=",
        "onerror=",
        "onfinish=",
        "onfocus=",
        "onhashchange=",
        "oninput=",
        "oninvalid=",
        "onkeydown=",
        "onkeypress=",
        "onkeyup=",
        "onload=",
        "onmessage=",
        "onmousedown=",
        "onmousemove=",
        "onmouseout=",
        "onmouseover=",
        "onmouseup=",
        "onclick=",
        "onoffline=",
        "ononline=",
        "onpagehide=",
        "onpageshow=",
        "onpaste=",
        "onpopstate=",
        "onreset=",
        "onresize=",
        "onsearch=",
        "onselect=",
        "onselectionchange=",
        "onselectstart=",
        "onstart=",
        "onstorage=",
        "onsubmit=",
        "onunload=",
        "onwheel=",
    }

    content_lower = content.lower()
    for pattern in dangerous_patterns:
        if pattern in content_lower:
            raise ValueError(f"Content contains dangerous pattern: {pattern}")

    # Check for data URLs in links or images
    if "data:" in content_lower:
        raise ValueError("Content contains data URLs which are not allowed")

    # Check for overly long content (prevent DoS)
    if len(content) > 50000:  # 50KB limit
        raise ValueError("Content is too long (maximum 50KB allowed)")
