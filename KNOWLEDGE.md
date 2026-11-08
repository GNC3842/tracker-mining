## Basics

### Vocab

**URL** (Uniform Resource Locator): ```https://user:pw@stats.g.doubleclick.net:443/g/collect?uid=123#top```
- ```http(s)```: scheme
- ```user:pw```: credentials
- ``` stats.g.doubleclick.net```:host
- ```443```: port
- ```/g/collect```:path
- ```?uid=123```:query
- ```#top```: fragment

Some *URL* don't have a *host* and so no **//**, they are *non-hierarchical*: ```data:image/png```, or ```about:blank``` or ```javascript```

**HTTP**:the protocol of the web. The browser sends a request ("give me /g/collect"); the server returns a response with a status code: *200 (OK)*, 302 (redirection: "go to this address instead"), *404 (not found)*, *403 (forbidden)*, *500 (server error)*

**Domain**: the name of a server, read from right to left. In ```stats.g.doubleclick.net```: *net* is the extension, *doubleclick* is the chosen name, *stats.g* are the subdomains

**DNS** is the directory that translates a name into an IP address

**Public suffix**: an extension under which anyone can register a name: *com*, *vn*, but also *com.vn* or *co.uk*. The official list is called the **Public Suffix List (PSL)**

**Registrable domain (eTLD+1)** : the public suffix plus one label, meaning "what a company bought." ```stats.g.doubleclick.net``` $\rightarrow$ ```doubleclick.net```; ```a.b.example.co.uk``` $\rightarrow$ ```example.co.uk```

**First-party / third-party**: on ```vnexpress.net```, a request to ```vnexpress.net``` is first-party (**FP**); a request to ```google-analytics.com``` is third-party: an entity other than the site being visited

**Cookie**: a small piece of data that a server asks the browser to store and send back with every visit. It has a domain, a name, and an expiration date (otherwise it is a session cookie, deleted upon closure). A long-lived (1 to 2 years) third-party cookie containing an identifier is the classic tracking technique.

**Tracker**: a third party whose function is to identify or profile the visitor: audience measurement, targeted advertising, session recording. Examples: ```google-analytics.com```, ```doubleclick.net``` (Google's advertising network), ```facebook.net``` (Facebook pixel).

**Pixel**: a 1×1 pixel image, invisible, whose sole purpose is to make a request to a tracker (with parameters like ?uid=123).

**Tag manager**: a script that loads other scripts according to a configuration. Example: Google Tag Manager (```googletagmanager.com```). It is often the first link in tracker chains.

**CDN** (Content Delivery Network): a network of servers that distributes files quickly. Examples: ```cdnjs.cloudflare.com```, ```cdn.jsdelivr.net```. A CDN hosts code: it does not necessarily track.

**Iframe**: a page embedded within another page (a frame). Its own resources are loaded from within that frame.
Anti-bot / challenge: a verification page (Cloudflare "Just a moment…", captcha) served in place of the site when a visitor appears automated

**Consent banner / CMP (Consent Management Platform)**: the "Accept cookies" banner. Some sites only load their trackers after a click on "Accept."

**CrUX**: Chrome UX Report,statistics published by Google on sites actually visited by Chrome users who have enabled stats sharing, by country

**Tracker Radar**: DuckDuckGo's database describing third-party domains (categories, owner, prevalence), built by a crawl from 9 regions: AU, CA, CH, DE, FR, GB, NL, NO, US. None in Asia

**EasyPrivacy**: a list of tracker-blocking rules used by ad blockers

**Stratified sample**: the population is divided into groups (strata), and samples are drawn from each group in proportion to its size

### How trackers work
1. We open a website: ```tintuc.vn```, inside the *HTML* code there is a tag ```<script src="https://www.googletagmanager.com/gtm.js">```, so the website include *GTM*, depth 1

2. *GTM* also include for exemple: ```google-analytics.com/analytics.js```, but it's not show on ```tintuc.vn```, depth 2
3. The script of *google-analytics* send a *pixel* to ```stats.g.doubleclick.net``` with our id, depth 3
4. And then ```stats.g.doubleclick.net``` send id to a partnership that will give us its *cookie*, depth 4


## Data

1. List of website CrUX from ```https://github.com/zakird/crux-top-lists/tree/main/data/country/vn```, data from *September 2026* : list of *rank* and *origins*

2. We prepare the websites: in ```src/tm/crawl/prepare_sites.py```