import pytest

from tm.domains import host_of, is_http, lookup_suffix, reg


@pytest.mark.parametrize("url, expected", [
    ("https://a.b.example.co.uk/x?y=1", "example.co.uk"),
    ("http://news-bench.vn:8765/", "news-bench.vn"),
    ("https://stats.g.doubleclick.net/g/collect", "doubleclick.net"),
    ("https://user:pw@www.Example.COM/", "example.com"),
    ("http://127.0.0.1:8080/x", "127.0.0.1"),
    ("https://shop.com.vn/", "shop.com.vn"),
    # section privée de la PSL : chaque client CloudFront / GitHub Pages est un site distinct
    ("https://d1rao4145q4o1h.cloudfront.net/t.js", "d1rao4145q4o1h.cloudfront.net"),
    ("https://user.github.io/p", "user.github.io"),
    ("data:image/png;base64,AAAA", ""),
])
def test_reg(url, expected):
    assert reg(url) == expected


def test_reg_bare_host():
    assert reg(".doubleclick.net") == "doubleclick.net"
    assert reg("www.example.com:8080") == "example.com"
    assert reg("") == ""


@pytest.mark.parametrize("url", ["about:blank", "javascript:void(0)", "data:text/html,x"])
def test_reg_non_hierarchical_urls(url):
    assert reg(url) == ""


def test_host_of_edge_cases():
    assert host_of("https://[::1]:8080/x") == "::1"              # IPv6 sans crochets (urllib)
    assert host_of("https://[::1/x") == ""                       # malformée : pas d'exception
    assert host_of("https://a.com\t/x") == "a.com"               # tabulation retirée (WHATWG)
    assert host_of("blob:https://a.com/uuid") == "a.com"         # blob : origine créatrice
    assert host_of("https://EXAMPLE.com./") == "example.com"
    assert host_of("no-scheme.com/x") == ""


def test_is_http():
    assert is_http("https://a.com") and is_http("http://a.com")
    assert not is_http("blob:https://a.com/x") and not is_http("chrome-extension://abc/x")


def test_lookup_suffix_longest_first_and_never_tld():
    table = {"example.com", "b.example.com", "com"}
    assert lookup_suffix("a.b.example.com", table) == "b.example.com"
    assert lookup_suffix("x.example.com", table) == "example.com"
    assert lookup_suffix("other.com", table) is None      # ne descend pas jusqu'à "com"
