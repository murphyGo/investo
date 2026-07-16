"""Media RSS image-reference extraction shared by RSS source adapters.

Implements u136 Fixed Contract #2
(``aidlc-docs/construction/plans/u136-feed-image-metadata-harvest-code-generation-plan.md``):
pure functions that pull the FIRST usable image reference out of an
already-parsed feed ``<item>`` element (:func:`extract_feed_image`) and
map it to the Contract #3 ``raw_metadata`` keys (:func:`image_metadata`),
so adapters can surface image candidates without any new HTTP request
or binary download (those are u137 scope).

Design choices (2026-07-17 live-probe facts in the u136 plan):

* **``<media:content>`` preferred over ``<media:thumbnail>``** — the
  full-size wire photo (Yonhap) / CDN image (Yahoo) beats the reduced
  thumbnail when both exist. Within each element kind, document order
  wins and only the first accepted candidate is returned.
* **``<media:content>`` must be image-shaped** — accepted when its
  ``type`` attribute is an ``image/*`` mime, OR the ``type`` attribute
  is absent and the URL path carries a known image file extension, OR
  the ``type`` attribute is absent and the element carries positive
  integer ``width`` + ``height`` attributes (Yahoo Finance's zenfs CDN
  URLs are extension-less content hashes with no ``type`` — verified
  against the 2026-07-16 live recording; the dimension pair is the
  image evidence there. Divergence from the u136 plan's
  mime-or-extension wording ratified at Step 3 implementation time,
  same precedent as the L6.5 pubDate-format divergence). Non-image
  mimes (``video/mp4`` etc.) are skipped so the fallback can still
  find a thumbnail. ``<media:thumbnail>`` is an image by Media RSS
  definition and needs no mime gate.
* **Safe degrade, never raise** — malformed candidates (missing/empty
  ``url``, non-http(s) scheme, URL longer than the 1000-char cap) are
  skipped; non-integer ``width``/``height`` degrade to ``None`` without
  rejecting the URL itself.
* **``<media:credit>``** is read from the accepted media element's
  children first, then item-level siblings (Yahoo places it under
  ``<item>`` directly); trimmed and capped at 240 chars.
* **Element parameter typed ``Any``** — the input is an
  :class:`xml.etree.ElementTree.Element` produced by the safe
  ``defusedxml`` parser, but importing the stdlib XML module under
  ``src/investo/sources`` would trip the NFR-007 AC-7.6 grep guard.

This module is internal to the sources package — not part of the public
re-export surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from investo.sources._xml_namespaces import MEDIA_CONTENT, MEDIA_CREDIT, MEDIA_THUMBNAIL

_ALLOWED_SCHEMES = ("http", "https")

# u136 Fixed Contract #2 caps: URL 1000 chars, credit 240 chars.
_URL_MAX_LEN = 1000
_CREDIT_MAX_LEN = 240

_IMAGE_MIME_PREFIX = "image/"

# Fallback image test when <media:content> omits the `type` attribute:
# the URL path must end in a well-known raster/vector image extension.
_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".svg"})


@dataclass(frozen=True, slots=True)
class FeedImageRef:
    """Image reference harvested from one feed ``<item>`` (metadata only)."""

    url: str
    width: int | None
    height: int | None
    mime: str | None
    credit: str | None


def extract_feed_image(item: Any) -> FeedImageRef | None:
    """Return the first usable image reference under ``item``, or ``None``.

    ``item`` is a parsed feed ``<item>``/``<entry>`` element from the
    safe ``defusedxml`` parser. Preference order: image-shaped
    ``<media:content>`` first, ``<media:thumbnail>`` fallback; within
    each kind the first candidate that passes URL validation wins.
    Pure function — no I/O, no mutation of ``item``.
    """

    for content in item.findall(MEDIA_CONTENT):
        if not _is_image_content(content):
            continue
        ref = _ref_from_element(content, item)
        if ref is not None:
            return ref
    for thumbnail in item.findall(MEDIA_THUMBNAIL):
        ref = _ref_from_element(thumbnail, item)
        if ref is not None:
            return ref
    return None


def _is_image_content(content: Any) -> bool:
    """True when a ``<media:content>`` element is image-shaped.

    Image mime in ``type`` → yes. Non-image mime → no (video/audio
    enclosures must not shadow a usable thumbnail). Absent/empty
    ``type`` → fall back to the URL file-extension test, then to the
    positive-``width``+``height`` dimension pair (extension-less
    zenfs-style CDN URLs — see module docstring).
    """

    mime = (content.get("type") or "").strip()
    if mime:
        return mime.lower().startswith(_IMAGE_MIME_PREFIX)
    url = (content.get("url") or "").strip()
    if not url:
        return False
    suffix = PurePosixPath(urlparse(url).path).suffix.lower()
    if suffix in _IMAGE_EXTENSIONS:
        return True
    return (
        _parse_dimension(content.get("width")) is not None
        and _parse_dimension(content.get("height")) is not None
    )


def _ref_from_element(elem: Any, item: Any) -> FeedImageRef | None:
    """Build a :class:`FeedImageRef` from one media element, or ``None``.

    ``None`` means the element's URL is unusable (missing, non-http(s),
    or over the length cap); the caller moves on to the next candidate.
    """

    url = (elem.get("url") or "").strip()
    if not url or len(url) > _URL_MAX_LEN:
        return None
    if urlparse(url).scheme not in _ALLOWED_SCHEMES:
        return None

    mime = (elem.get("type") or "").strip() or None
    return FeedImageRef(
        url=url,
        width=_parse_dimension(elem.get("width")),
        height=_parse_dimension(elem.get("height")),
        mime=mime,
        credit=_extract_credit(elem, item),
    )


def _parse_dimension(raw: str | None) -> int | None:
    """Parse a width/height attribute; any failure degrades to ``None``."""

    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        return None
    # A zero/negative dimension is feed noise, not usable metadata.
    return value if value > 0 else None


def image_metadata(ref: FeedImageRef) -> dict[str, str | int]:
    """Map a :class:`FeedImageRef` to the u136 Contract #3 keys.

    ``image_url`` is always present; ``image_width`` / ``image_height``
    / ``image_mime`` / ``image_credit`` appear only when the field is
    set — absent field = absent key, never ``None`` / empty (R8:
    flat strings/ints only). Adapters merge the result into their
    ``raw_metadata`` bag via ``dict.update``.

    Contract #4 (safety invariant): this is the ONLY place adapters
    derive image keys from, and it never emits license-family keys
    (``image_license`` / ``image_attribution`` / ``image_author`` /
    ``image_allowed_use`` or ``visual_image_*`` synonyms) — so the
    dormant ``visuals/external_image`` fetch path can never trigger
    off harvested feed metadata.
    """

    metadata: dict[str, str | int] = {"image_url": ref.url}
    if ref.width is not None:
        metadata["image_width"] = ref.width
    if ref.height is not None:
        metadata["image_height"] = ref.height
    if ref.mime is not None:
        metadata["image_mime"] = ref.mime
    if ref.credit is not None:
        metadata["image_credit"] = ref.credit
    return metadata


def _extract_credit(elem: Any, item: Any) -> str | None:
    """Trimmed ``<media:credit>`` text (240-char cap), or ``None``.

    Media RSS allows the credit either nested under the media element
    (canonical) or as an item-level sibling (Yahoo Finance's shape);
    the nested form wins when both exist.
    """

    for scope in (elem, item):
        credit_elem = scope.find(MEDIA_CREDIT)
        if credit_elem is None or credit_elem.text is None:
            continue
        # ``credit_elem`` is ``Any`` (Element typing note above), so the
        # explicit ``str`` annotation restores mypy-strict coverage.
        credit: str = credit_elem.text.strip()
        if credit:
            return credit[:_CREDIT_MAX_LEN]
    return None
