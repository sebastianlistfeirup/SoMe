# Mål og KPI'er

Målet er en kanal, der bliver målbart bedre over tid uden at gå på kompromis med fakta, rettigheder eller ejerens tid. Der gives ingen garanti for vækst.

## Hovedmål (north star)

**Netto-subscribers pr. 1.000 views** (gained − lost), målt omkring dag 7 pr. opslag. Hovedmålet vises som median pr. uge i scorecardet (`python -m app.cli scorecard`).

Hvorfor dette mål: Det belønner opslag, der får nye seere til at blive. Det er mindre følsomt for kanalvækst end rå views. Og det passer til en kanal, der lever af tilbagevendende formater.

## Sikkerhedsgrænser (guardrails)

En ny læringsmodel aktiveres ikke, hvis en guardrail i den seneste uge ligger under 85 % af medianen for de fire uger før.

| Guardrail | Måling |
|---|---|
| Gennemsnitlig retention | `averageViewPercentage` (YouTube) |
| Hook-retention | Andel seere tilbage 3 s efter intro-slut (`hookRetention3s`) |
| Første-gangs-godkendelse | Andel videoer, hvis første ejerbeslutning er godkendelse |

Falder hovedmålet to uger i træk efter en aktivering, rulles læringsmodellen tilbage automatisk.

## Drifts-KPI'er

| KPI | Mål for piloten | Kilde |
|---|---|---|
| Ejerens minutter pr. opslag | Måles først; derefter −25 % på det dyreste trin | `timelog report` |
| API-pris pr. produktion | ≤ 2 DKK (1–2 min. video) | `cost-report` / Drift-siden |
| Samlet månedlig drift | ≤ ca. 230 DKK (server + API) | `cost-report` |
| Første-gangs-godkendelse | ≥ 70 % | scorecard |
| Tid fra idé til publicering | Måles i piloten | idé-ID → publiceringsdato |
| Fejlede jobs uden opfølgning | 0 | Drift-siden / alarmer |
| Verificeret backup | Dagligt + månedlig gendannelsestest | alarmer / restore-drill |

## Sådan læses tallene

- Små samples giver brede intervaller. Rapporten viser 90 %-intervaller, og når de overlapper, er der ingen påvist forskel.
- Sammenligninger sker kun inden for samme platform, format og længde og korrigeres for kanalvækst.
- Eksterne kanalers tal er inspiration, ikke målestok.
