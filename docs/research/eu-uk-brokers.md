# EU/UK Brokers: a sourced starting list for the Unlist overlay

Research for issue #29. Checked on **2026-11-26**. Builds on [organization-lists.md](organization-lists.md).

## Answer

- **75 Brokers listed**: Germany 26, UK 15, Austria 8, France 6, Netherlands 6, Ireland 3, and 11 from other countries (Belgium 9, Italy 1, Sweden 1). Kinds across the table: about 25 credit agencies (Auskunfteien, credit reference agencies, a credit registry), about 24 address, list and lead brokers, about 10 B2B contact-data and business-information providers, about 8 marketing-data and audience-data firms, and 2 people-search or tracing services.
- **54 of 75 already exist in `datenanfragen/data`** (clone at commit `4f63855`). All 26 German and all 8 Austrian rows are there, because upstream curated Germany and Austria heavily (`address-brokers` and `credit-agencies` company packs). **21 are not**: 5 UK, 3 French, 4 Dutch, 1 Irish and 8 Belgian.
- **Confidence is uneven.** Only the UK rows are checked on a primary register (ICO register entries, read one name at a time). The regulator decisions (CNIL, EDPB study, ICO report) were read for 7 rows. For the rest, the Broker's own site could not be opened in this session (see "Could not verify"), so the contact comes from the `datenanfragen` record (CC0, status `verified` upstream) and the Broker's own privacy page URL that record cites. Each row says which.
- **Main gaps.** Ireland is nearly empty (no Irish Broker confirmed beyond the credit bureau and two foreign-group subsidiaries). The Netherlands, France and Belgium rest on enforcement news and one Belgian market study, so list brokers there are mostly unknown to us. No German or Austrian regulator document was reachable, so German and Austrian rows lean on upstream. Large audience-data and ad-tech firms (the TCF vendor list) were not researched at all.
- **Defunct or ceased operators** are marked `ceased` and should stay out of the default list unless Unlist wants them for historic requests: Caloga (FR, ceased 2024), Experian Nederland (NL, left the market in 2025).
- **Borderline kinds** are marked `borderline` so the Operator-facing list can decide: Cifas (fraud-prevention data sharing), GB Group (identity verification), BKR (statutory-style credit registry run by a foundation), Besurance HIS (insurance claims database), DEMDA (tenant database).

How to read the confidence tags:

| Tag | Meaning |
|---|---|
| `[reg]` | Entity, address and role mailbox read on the ICO register entry for that name (a one-name lookup, not a download). |
| `[reg+]` | Read in a regulator document or news page on a regulator's own site (CNIL, EDPB, ICO). |
| `[D]` | Record in `datenanfragen/data` read in the clone; contact is that record's `email` or `webform`. The record's own-site `sources` URL is given but was not opened by me. |
| `[S]` | Taken from a search-engine excerpt of a page that could not be opened. Treat as a lead to verify. |

Contact columns hold role addresses and official forms only. Where a source gave only a named person's mailbox, it is not recorded.

## Germany

Primary regulator sources were not reachable (see "Could not verify"). All rows are `[D]`: the `datenanfragen` record, status `verified` unless noted, and the Broker's own privacy page it cites. Classification of "credit agency" and "address broker" also matches upstream's own company packs (`credit-agencies`, `address-brokers`).

| Legal entity | Kind | Contact (role address or form) | datenanfragen slug | Source (own site, via record) |
|---|---|---|---|---|
| SCHUFA Holding AG, Wiesbaden | credit agency | datenschutz@schufa.de | `schufa` | https://www.schufa.de/de/datenschutz/ |
| CRIF GmbH, München (formerly CRIF Bürgel) | credit agency, address broker | datenschutz.de@crif.com; self-disclosure form https://selbstauskunft.crif.de/onlineForm | `crifbuergel` | https://www.crif.de/datenschutz |
| infoscore Consumer Data GmbH, Baden-Baden (Experian group; absorbed Creditreform Boniversum GmbH) | credit agency | ICD-Datenschutz@experian.com | `infoscore`; `creditreform-boniversum` is obsolete, redirects here | https://www.experian.de/selbstauskunft ; merger: https://www.lto.de/recht/kanzleien-unternehmen/k/experian-creditreform-strategische-partnerschaft-uebernahme-boniversum |
| Verband der Vereine Creditreform e.V., Neuss | credit agency | datenschutz@verband.creditreform.de | `creditreform-verband` | https://www.creditreform.de/datenschutz |
| Bisnode Deutschland GmbH, Darmstadt | credit agency | datenschutz.de@bisnode.com | `bisnode-de` | https://www.bisnode.de/globalassets/germany/pdf-dokumente/datenschutzhinweise/datenschutzhinweise_fur_personen-im-auskunftsdatenbestand_final.pdf |
| Dun & Bradstreet Deutschland GmbH, Frankfurt | credit agency, address broker | datenschutz.de@dnb.com; form https://www-prod.dnb.com/de-de/datenschutz/ihre-rechte-als-betroffener/selbstauskunft-widerspruch/ | `dud-de` | https://www.dnb.com/de-de/impressum.html (likely same group as Bisnode; unverified, see below) |
| Intrum Information Services Deutschland GmbH, Heppenheim | credit agency | datenschutz.de@intrum.com; form https://www.intrum.de/zahlungserinnerung-erhalten/uber-intrum/datenschutz/rechte-der-betroffenen-person/ | `intrum-information-services-deutschland-gmbh` | https://www.intrum.de/zahlungserinnerung-erhalten/uber-intrum/datenschutz/datenschutzerklarung/ |
| IHD Gesellschaft für Kredit- und Forderungsmanagement mbH, Frechen | credit agency, collection | datenschutz@ihd.de | `ihd-kredit` (quality `tested`) | https://www.ihd.de/datenschutz/ |
| Besurance HIS GmbH, Wiesbaden (formerly informa HIS) | insurance claims database, `borderline` | datenschutz@besurance-his.de; form https://besurance-his.de/selbstauskunft | `informa-his` | https://besurance-his.de/datenschutz |
| Regis24 GmbH, Berlin | credit agency, address broker | datenschutz@regis24.de; form https://selbstauskunft.regis24.com/ | `regis24` (`tested`) | https://www.regis24.de/datenschutz/ |
| EURO-PRO Gesellschaft für Data Processing mbH, Grävenwiesbach | credit agency, address broker | datenschutz@europro.de | `europro` (`tested`) | https://www.europro.de/datenschutz/ |
| CS Connect GmbH & Co. KG, Wiesbaden | credit agency | datenschutz@cs-connect.de; form https://www.cs-connect.de/kontakt/ | `cs-connect` (`tested`) | https://www.cs-connect.de/datenschutz.jsp |
| DEMDA Deutsche Mieter Datenbank GmbH & Co. KG, Bremen | tenant database, `borderline` | info@demda.de; form https://www.demda.de/eigenauskunft.php | `demda` | https://www.demda.de/datenschutzerklaerung.php |
| Deutsche Post Direkt GmbH, Troisdorf | address broker | datenschutz@postdirekt.de; form via https://www.deutschepost.de/de/d/deutsche-post-direkt/kontakt.html?thema=Datenschutz%20%28z.B.%20Widerspruch%20zur%20Datenverwendung%29 | `deutsche-post-direkt` | https://service.postdirekt.de/portal/datenschutz |
| Deutsche Post Adress GmbH & Co. KG, Gütersloh | address broker | datenschutz@postadress.de | `deutsche-post-adress` (`tested`) | https://www.deutschepost.de/de/p/postadress/datenschutz.html |
| Acxiom Deutschland GmbH, Frankfurt | address broker, marketing data | datenschutz@acxiom.com; form https://www.acxiom.de/datenschutzanfragen/ | `acxiom` | https://www.acxiom.de/datenschutz/datenschutzinformationen-fuer-verbraucher-und-firmendatenbank/ |
| AZ Direct GmbH, Gütersloh (Bertelsmann) | address and list broker | datenschutz@az-direct.com | `az-direct` (`tested`) | https://www.az-direct.com/site/dm |
| ABIS GmbH, Frankfurt | address broker | datenschutz@abis-online.de | `abis` (`tested`) | https://www.abis-online.de/betroffenenanfrage/ |
| eGENTIC GmbH, Sulzbach (Taunus) | address broker | info@egentic.com (general mailbox; no role address found) | `egentic` | https://www.egentic.com/datenschutz/ |
| QUADRESS GmbH, Bochum | address broker | dsb.quadress@zb-datenschutz.de (external DPO service) | `quadress` | http://www.quadress.de/datenschutz |
| Capaneo GmbH, Leinfelden-Echterdingen (formerly Schober) | address broker | datenschutz@capaneo.de | `schober` | https://capaneo.de/datenschutz/ |
| adpublisher AG | marketing and audience data | datenschutz@adpublisher.com | `adpublisher` | https://www.adpublisher.com/de/datenschutz.html |
| panadress marketing intelligence GmbH, München | address broker | datenschutz@panadress.de | `panadress` | http://www.panadress.de/data-und-services/adressen#btocadressen |
| Nexiga GmbH, Bonn | geomarketing, address data | datenschutzbeauftragter@nexiga.com | `nexiga` | https://www.nexiga.com/datenschutzerklaerung/ |
| Media Information Systems Deutschland GmbH, Grünwald | address and list broker | datenschutz@mismail.de | `mediainformationsystems` | https://mediainformationsystems.de/datenschutz.html |
| DTM Deutsche Tele Medien GmbH, Frankfurt (Das Telefonbuch) | directory publisher, people search | datenschutz@dtme.de | `dastelefonbuch` | https://www.dastelefonbuch.de/Datenschutz |

## United Kingdom

Entity, address and the role mailbox on the ICO register are `[reg]`: the ICO register entry page for each name was read (lookup of one name at a time). The ICO's own investigation report (<https://ico.org.uk/media2/migrated/2618470/investigation-into-data-protection-compliance-in-the-direct-marketing-data-broking-sector.pdf>, `[reg+]`) names Experian, Equifax and TransUnion as the three big credit reference agencies that also did direct-marketing data broking, and lists four earlier fines against data brokers.

| Legal entity | Kind | Contact (role address or form) | datenanfragen slug | Source |
|---|---|---|---|---|
| Experian Limited, Nottingham | credit agency, marketing data | uk.dpobusinessenquiries@experian.com `[reg]`. Consumer notices also cite uk.dpo@experian.com `[S]` | `experian-gb` | https://ico.org.uk/ESDWebPages/Entry/Z6424480 ; ICO report above (enforcement notice, Oct 2020); https://www.experian.co.uk/crain/index.html |
| Equifax Limited, London | credit agency | ukdpo@equifax.com `[reg]` | `equifax-gb` | https://ico.org.uk/ESDWebPages/Entry/Z6564696 ; ICO report above |
| TransUnion International UK Limited, Leeds (formerly Callcredit; DPO role held by TransUnion Information Group Limited) | credit agency | DPO@transunion.co.uk `[reg]` | `callcredit-gb` (record still named "Callcredit Information Group", `dpo@callcreditgroup.com`; stale) | https://ico.org.uk/ESDWebPages/Entry/Z5169270 ; https://ico.org.uk/ESDWebPages/Entry/Z2222218 ; ICO report above (also names Callcredit Marketing Limited, not found on the register under that name) |
| Cifas, London | fraud-prevention data sharing, `borderline` | none on the ICO register or in the record; its notice is at https://www.cifas.org.uk/privacy-notice | `cifas` | https://ico.org.uk/ESDWebPages/Entry/Z5080002 |
| Acxiom Limited, London | marketing data, address broker | dataprotection@acxiom.com `[reg]` | `acxiom-gb` | https://ico.org.uk/ESDWebPages/Entry/Z5459609 ; own site https://www.acxiom.co.uk/about-acxiom/privacy/uk-privacy-policy/ (not opened) |
| 192.Com Ltd, Lewes (company no. 13207491 per its policy) | people search | no role mailbox on the register. Policy gives postal "192.com Customer Services, 36 Southwark Bridge Rd, London SE1 9EU" and an email redacted in the excerpt `[S]` | not in | https://ico.org.uk/ESDWebPages/Entry/ZB013711 ; https://www.192.com/info/privacy-policy/ `[S]` |
| Tracesmart Limited, Cardiff (LexisNexis Risk Solutions) | people tracing, identity data | dpo@lexisnexisrisk.com `[reg]` | not in | https://ico.org.uk/ESDWebPages/Entry/Z708281X ; TraceIQ uses electoral roll data `[S]`: https://risk.lexisnexis.co.uk/about-us/press-room/press-release/uk-2014-07-04-traceiq-incorporates-electoral-roll |
| Cognism Limited, London | B2B contact data | privacy@cognism.com `[S]` (register lists no DPO) | not in | https://ico.org.uk/ESDWebPages/Entry/ZA217416 ; https://www.cognism.com/en/privacy-policy `[S]` |
| Creditsafe Business Solutions Limited, Cardiff | business credit data (includes sole traders), B2B data | dpocsgroup@creditsafeuk.com `[reg]` | not in | https://ico.org.uk/ESDWebPages/Entry/Z8580278 |
| GB Group plc, Chester | identity-verification data, address data, `borderline` | DPO@gbgplc.com; form https://www.gbgplc.com/en/contact/general-enquiry/individual-data-enquiry/ `[D]` | `gb-group` | https://www.gbgplc.com/privacy-policy/ (register name lookup was ambiguous; entry not read) |
| LiveRamp UK Limited, London | audience data, identity graph | ukprivacy@liveramp.com `[reg]`; form https://liveramp.uk/privacy/your-rights/ `[D]` | `liveramp-gb` | https://ico.org.uk/ESDWebPages/Entry/ZA446812 |
| Databroker Ltd, Altrincham | list broker | info@data-broker.co.uk `[D]` (general mailbox) | `data-broker-gb` | https://ico.org.uk/ESDWebPages/Entry/ZA095934 ; DMA member profile: https://dma.org.uk/company/databroker-ltd `[S]` |
| Marketscan Ltd, Chichester (ICO now shows "Marketscan Data Solutions Ltd", registered June 2025, Terminus Road) | list broker | info@marketscan.co.uk `[D]` (general mailbox) | `marketscan-gb` | https://ico.org.uk/ESDWebPages/Entry/ZB916560 (entity change; record's address "8 Duke's Court" may be stale) |
| ChooseLeads Ltd, London | lead and list broker | hello@chooseleads.co.uk `[D]` | `chooseleads` | https://www.chooseleads.co.uk/contact-us/ (not opened; not found on the ICO register under that name) |
| Lifecycle Marketing (Mother & Baby) Limited, London (trades as Emma's Diary) | consumer-data list seller | the register shows only a named person's mailbox, so none recorded | not in | https://ico.org.uk/ESDWebPages/Entry/ZA478466 ; fined 2018 per ICO report above `[reg+]` |

Historic ICO fines against data brokers (same report): The Data Supply Company (2017), Verso Group (UK) Limited (2017), Lifecycle Marketing (2018), Bounty (UK) Ltd (2019). The register lookup found none of Bounty, Verso or The Data Supply Company under those names, so treat them as gone. Not rows.

## France

CNIL decisions are `[reg+]` (read on cnil.fr). The CNIL's 2022 priority control topic was commercial prospecting by data resellers.

| Legal entity | Kind | Contact (role address or form) | datenanfragen slug | Source |
|---|---|---|---|---|
| SOLOCAL MARKETING SERVICES | lead and data broker (SMS and email prospecting, data resale) | not found (CNIL page does not give one) | not in | CNIL fined it EUR 900,000 on 15 May 2025: https://www.cnil.fr/fr/sanction-de-900-000-euros-societe-solocal-marketing-services |
| TAGADAMEDIA | lead broker (competition and product-test sites collecting prospects) | not found | not in | CNIL fine EUR 75,000 (29 Dec 2023), cut to EUR 50,000 by the Conseil d'Etat on 20 May 2026: https://www.cnil.fr/fr/courtiers-en-donnees-sanction-de-75-000-euros-lencontre-de-la-societe-tagadamedia |
| KASPR SAS, Paris | B2B contact data (browser extension, about 160 million contacts) | privacy@kaspr.io `[D]` | `kaspr` (`tested`) | CNIL fine EUR 240,000 (5 Dec 2024): https://www.cnil.fr/fr/aspiration-de-donnees-sanction-de-240-000-euros-lencontre-de-la-societe-kaspr . CNIL page on the order closure says the database was deleted and LinkedIn collection stopped (closure dated 4 Mar 2026) `[S]`: https://www.cnil.fr/fr/cloture-de-linjonction-prononcee-lencontre-de-la-societe-kaspr |
| CALOGA | lead and data broker, `ceased` | none | not in | CNIL fine EUR 80,000 (15 May 2025); the company ended all activity in 2024: https://www.cnil.fr/fr/sanction-de-80-000-euros-societe-caloga |
| LiveRamp France SAS, Levallois-Perret | audience data, identity graph | cil@liveramp.com `[D]` | `liveramp-fr` | https://liveramp.fr/politique-de-confidentialite-de-nos-produits-et-services-2/ |
| Weborama, Paris | audience and marketing data | privacy@weborama.com `[D]` | `weborama` | https://weborama.com/respect-de-la-vie-privee-2-2/ |

## Netherlands

| Legal entity | Kind | Contact (role address or form) | datenanfragen slug | Source |
|---|---|---|---|---|
| Stichting BKR, Tiel | credit registry, `borderline` | fg@bkr.nl (data protection officer role); post: Functionaris Gegevensbescherming, Postbus 6080, 4000 HB Tiel `[S]` | not in | BKR privacy statement March 2026 `[S]`: https://communicatie.bkr.nl/media/4y3pm2dh/privacyverklaring-stichting-bkr-maart-2026.pdf ; Dutch DPA fined it EUR 830,000 in 2020 over access limits `[S]`: https://nos.nl/l/2339737 |
| Creditsafe Nederland B.V., Amsterdam (trades as GraydonCreditsafe after the Graydon merger) | business credit data and company information | avg@graydoncreditsafe.nl `[S]` | not in | https://www.creditsafe.com/content/dam/nl/legal/creditsafe-notificatiebrief-nl.pdf `[S]` ; privacy page https://www.creditsafe.com/be/nl/legal/uw-onderneming-uw-privacy.html |
| Experian Nederland B.V. | credit agency, `ceased` | none | not in | Dutch DPA fine EUR 2.7 million, decision 16 Oct 2025; Experian no longer active in the Netherlands since early 2025 and was deleting its database `[S]`: https://dutchnews.nl/2025/10/privacy-watchdog-hands-e2-7-m-fine-to-credit-score-firm-experian ; https://privacymatters.dlapiper.com/2025/11/dutch-dpa-fines-experian-e2-7m-for-breaches-of-the-gdpr/ |
| Locatefamily.com (Canadian operator, no EU establishment) | people search (addresses, phone numbers) | none found | not in | Dutch DPA fine EUR 525,000 in 2021 for no EU representative; most data since deleted: https://www.edpb.europa.eu/node/2676_en `[S]`. Operator and legal entity not confirmed; may be inactive. |
| Sales.Rocks BV, Rotterdam | B2B contact data | datasubjectrequest@sales.rocks `[D]` | `sales-rocks-bv` | https://sales.rocks/privacy-terms-conditions/ |
| LiveRamp Netherlands B.V., Amsterdam | audience data, identity graph | privacy.nl@liveramp.com `[D]` | `liveramp-nl` | https://liveramp.uk/privacy-policy-netherlands/ |

## Austria

All rows `[D]` except the Post row, whose enforcement history is `[S]`.

| Legal entity | Kind | Contact (role address or form) | datenanfragen slug | Source (own site, via record) |
|---|---|---|---|---|
| KSV1870 Holding AG, Wien | credit agency, collection | ksv1870.datenschutzbeauftragter@ksv.at | `ksv1870` | https://www.ksv.at/datenschutzerklaerung ; notices by company: https://www.ksv.at/en/datenschutzerklarung `[S]` |
| CRIF GmbH, Wien | credit agency, address publisher | auskunft@crif.com | `crif-at` | https://www.crif.at/datenschutzerklaerung-auskunftei-und-adressverlag/ |
| Dun & Bradstreet Austria GmbH, Wien | credit agency | eigenauskunft.at@dnb.com; form https://www.dnb.com/de-at/datenschutz-eigenauskunft/beantragung-eigenauskunft-privatpersonen/ | `dnb-at` | https://www.dnb.com/de-at/impressum/ |
| AKV EUROPA, Alpenländischer Kreditorenverband, Wien | credit agency | datenschutz@akveuropa.at | `akv-at` | https://www.akv.at/datenschutz |
| HEROLD Business Data GmbH, Mödling | business directory, address and marketing data | office@herold.at (general mailbox) | `herold` | https://www.ichbinderherold.at/impressum |
| Österreichische Post AG, Wien | address and marketing-data seller (also postal operator) | team-datenschutz@post.at; form https://www.post.at/k/f/kontaktformular?problem=DatenschutzAuskunft | `post-at` | https://www.post.at/co/c/datenschutz . Austrian DPA found its party-affinity profiling unlawful (Oct 2019, fine later set aside on a formal point; final amount reports disagree) `[S]`: https://edpb.europa.eu/news/national-news/2019/austrian-data-protection-authority-finalises-investigation-oesterreichische_el |
| DPIT GmbH, Wien (ProfileAddress) | address broker | auskunft@dp-it.at; form https://dp-it.at/auskunft/ | `profileaddress` | https://dp-it.at/datenschutz/ |
| AZ Direct Österreich GmbH, Wien | address and list broker | office@bertelsmann.at (general mailbox) | `az-direct-at` | https://www.az-direct.com/site/unternehmen/standorte/ |

## Ireland

Thin. No Irish list broker or people-search service was confirmed.

| Legal entity | Kind | Contact (role address or form) | datenanfragen slug | Source |
|---|---|---|---|---|
| Irish Credit Bureau DAC | credit reference agency | not found | not in | Data Protection Commission decision of 23 Mar 2021 (inquiry IN-19-7-2, breach of Arts 5(2), 24(1), 25(1) GDPR; no corrective order) `[S]`: https://www.dataprotection.ie/sites/default/files/uploads/2021-05/Summary%20of%20Decision%20Irish%20Credit%20Bureau.pdf |
| Trulioo (Ireland) Limited, Dublin | identity-verification data (EU arm of a Canadian firm), `borderline` | privacy@trulioo.com `[D]` | `trulioo-information-services-inc` | https://www.trulioo.com/services-privacy-policy |
| NextRoll Limited, Dublin | ad-tech audience data | dpo@nextroll.com `[D]` | `nextroll` | https://www.nextroll.com/privacy |

## Other countries

Belgium comes from the EDPB-published Support Pool of Experts study "Data brokers market study" (04 March 2026, written by an external expert at the Belgian DPA's request, not an EDPB position). It classifies these firms on public website evidence and says it did not independently verify them. It gives no privacy contacts, only policy URLs. `[reg+]` for kind and entity name: <https://www.edpb.europa.eu/system/files/2026-04/spe_databorkersmarketstudy_en.pdf> (page summary: <https://www.edpb.europa.eu/our-work-tools/our-documents/support-pool-experts-projects/data-brokers-market-study_en>).

| Country | Legal entity | Kind (as the study classes it) | Contact | datenanfragen slug | Source |
|---|---|---|---|---|---|
| BE | Infobel SA, Brussels (InfobelPro) | personal data broker (B2B and B2C lists, 11 countries) | none given; policy https://www.infobelpro.com/en/privacy-policy | not in | EDPB study, section 3.2.1 |
| BE | GeoPostcodes, Brussels | personal data broker (address data; the study is unsure whether it links to individuals), `borderline` | none given; policy https://www.geopostcodes.com/privacy-policy/ | not in | EDPB study, section 3.2.1 |
| BE | Sirius Insight, Louvain-la-Neuve | data broker and aggregated-data provider (geomarketing) | none given; policy https://siriusinsight.be/privacy-policy/?lang=en | not in | EDPB study, section 3.2.1 |
| BE | Target Search BV, Sint-Martens-Latem | personal data broker (ethnomarketing, names and addresses) | none given; policy https://www.targetsearch.be/nl/privacybeleid/ | not in | EDPB study, section 3.2.1 |
| BE | Altares, part of Dun & Bradstreet, Groot-Bijgaarden | business data broker with personal data | none given; policy https://www.altares.be/en/legal/privacy-policy/ | not in | EDPB study, business data brokers section |
| BE | Companyweb, Vilvoorde | business data broker with personal data | none given; policy https://www.companyweb.be/en/privacy-policy | not in | EDPB study, business data brokers section |
| BE | Trends Business Information (Roularta Media Group) | business data broker with personal data | none given; policy https://www.roularta.be/nl/privacy-policy | not in | EDPB study, business data brokers section |
| BE | PH Com, Brussels | business data broker (telemarketing database) | none given; policy https://www.phcom.be/privacy/en/ | not in | EDPB study, business data brokers section |
| BE | Black Tiger Belgium SA/NV, Anderlecht (former Bisnode Belgium) | address and business data broker | dpo@blacktigerbelgium.tech `[D]` | `bisnode-be` | https://www.blacktigerbelgium.tech/privacy-policy/ |
| IT | CRIF SpA, Bologna | credit agency | dirprivacy@crif.com `[D]` | `crif-it` | https://www.crif.it/privacy-policy/ |
| SE | Active Leads AB, Stockholm | lead and address broker | privacy@activeleads.se `[D]` | `activeleads-se` | https://www.activeleads.se/copy-of-om-oss?lang=en |

## Sources

Read in this session:

- `datenanfragen/data` clone, commit `4f6385518492d0c15dddf0ac3e487098ccdc922a` (CC0): `companies/`, `obsolete-records/`, `company-packs/`. <https://github.com/datenanfragen/data>
- ICO register of fee payers, entry pages for single names (lookup through the register's own search form; the dataset download was not used): <https://ico.org.uk/about-the-ico/what-we-do/register-of-fee-payers/>
- ICO, "Investigation into data protection compliance in the direct marketing data broking sector": <https://ico.org.uk/media2/migrated/2618470/investigation-into-data-protection-compliance-in-the-direct-marketing-data-broking-sector.pdf>
- CNIL decisions on Caloga, Solocal Marketing Services, Tagadamedia, Kaspr (URLs in the France table), read on cnil.fr.
- EDPB, Data brokers market study (SPE project, 04 March 2026), PDF and summary page (URLs above).

Search-engine excerpts only (pages not opened, `[S]`): the broker pages and news items named in the rows, plus <https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/organisations-using-marketing-services-of-data-brokers/> for ICO guidance on brokers.

Used only to pick names to check, never copied: none. No CC BY-NC-SA list (Big Ass Data Broker Opt-Out List, Optery, Privacy Rights Clearinghouse) and no commercial removal-service list was consulted for this file.

## Could not verify

- **Broker websites and most regulator sites are blocked** from this session (DNS or proxy refusal): schufa.de, crif.de, ksv.at, experian.co.uk, equifax.co.uk, transunion.co.uk, creditsafe.com, 192.com, liveramp.com, dsb.gv.at, autoriteitpersoonsgegevens.nl, dataprotection.ie, bfdi.bund.de, data.gouv.fr, gov.uk, Companies House and the Wikipedia sites. Only github.com, ico.org.uk, cnil.fr and edpb.europa.eu answered. This is why contacts for 54 rows rest on the `datenanfragen` record plus the Broker's own page URL that record cites, which I did not open. They need a check before shipping.
- **No German or Austrian regulator document** was read. German Auskunftei and Adresshändler rows have no enforcement or registry source of their own, only upstream. A search suggested the Berlin DPA's 2024 annual report has a section "Adresshandel vor Gericht"; not read.
- **Contacts found only through search excerpts** (`[S]`): Experian consumer DPO mailbox, 192.com postal and email, Cognism, BKR, Creditsafe Nederland. Excerpts can be stale.
- **192.com**: the register entry shows a Lewes address, the policy excerpt a London customer-services address. Which receives requests is unconfirmed, and the email was redacted.
- **Bisnode Deutschland and Dun & Bradstreet Deutschland** are both in upstream and are probably one group after a takeover. I did not confirm the relationship or that both entities still hold separate databases.
- **Callcredit Marketing Limited** (named by the ICO) was not found on the register, and the `callcredit-gb` record is stale (TransUnion rebrand).
- **GB Group plc**: the register search returned a list, not an exact entry; entry not read.
- **ChooseLeads, Databroker, Marketscan, eGENTIC, AZ Direct Österreich, HEROLD, KASPR (post-order business)**: contacts are general mailboxes or unconfirmed whether the entity still sells data.
- **Locatefamily.com**: the legal entity, whether it still operates, and any privacy contact were not established.
- **Ireland**: no Irish Broker other than the Credit Bureau (and the two foreign-group arms) was found. The Irish Credit Bureau's contact, and any Experian or Equifax presence in Ireland, are unknown.
- **Not researched**: ad-tech and audience-data vendors from the IAB TCF vendor list, other countries' brokers (Spain, Italy, Nordics beyond one record, Poland), French credit-like services (Banque de France registers are public, not Brokers), French people-search and company-data sites, Cegedim (CNIL health-data case), and CACI (register lookup returned nine near-matches; no entry chosen).
- **Bulk download of the ICO register**: a fetch of the full dataset zip was refused by this session's permission layer and was not retried, in line with "lookup only". Only the single-name lookups above were made.
- **Whether each firm meets "Broker"** is my classification from the source's wording, not a legal finding. The `borderline` rows are the ones most likely to be removed.
