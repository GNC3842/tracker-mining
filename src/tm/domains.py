"""Domains normalization and registrable domain extraction.
  https://a.b.example.co.uk/x  ->  example.co.uk
"""
from __future__ import annotations

from functools import lru_cache
from typing import Container
from urllib.parse import urlsplit

import tldextract

_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)


def host_of(url):
  if url.startswith("blob:"):
    url = url[5:]
  if "://" not in url:
    return ""
  try:
    h = urlsplit(url).hostname
  except ValueError:
    return ""
  return h.rstrip(".") if h else ""


@lru_cache(maxsize=1_000_000)
def _reg_host(host):
  if not host:
    return ""
  e = _EXTRACT(host)
  return e.top_domain_under_public_suffix or host


def reg(url_or_host):
  if not url_or_host:
    return ""
  if "://" not in url_or_host:
    scheme = url_or_host.split(":", 1)[0]
    if ":" in url_or_host and "." not in scheme:
      return ""
  h = host_of(url_or_host) if "://" in url_or_host else url_or_host.lower().lstrip(".")
  return _reg_host(h)


def is_http(url):
  return url.startswith(("http://", "https://"))


def lookup_suffix(host_or_dom, table):
  parts = host_or_dom.split(".")
  for i in range(len(parts) - 1):
    key = ".".join(parts[i:])
    if key in table:
      return key
  return None