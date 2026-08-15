Abi dürüst cevap vereyim: Archiverr plugin sistemi “internette eşi yok” seviyesinde değil, ama kendi problem alanına göre — medya metadata pipeline’ı, pluggable provider’lar, parse/data/output ayrımı, dry-run/no-delete güvenliği — ortalama self-host projelerin %90’ından daha bilinçli tasarlanmış.

Ama aynı zamanda şunu da söylemem lazım: senin sistemin büyük workflow/plugin engine’lerle kıyaslandığında hâlâ “lokal, in-process, trusted plugin pipeline” seviyesinde. Yani Arcaflow, Kestra, Temporal, Conductor, HashiCorp go-plugin gibi sistemlerin sahip olduğu isolation/durability/versioning/marketplace/SDK sertliği sende yok. Bu kötü mü? Hayır. Çünkü Archiverr’ın ihtiyacı o değil. Ama “dünyadaki en kapsamlı plugin runtime” değil.

Net skor:

Problem-fit architecture:     8.5/10
Plugin authoring simplicity:  7.5/10
Runtime orchestration:        7/10
Safety model:                 7/10
SDK/public contract quality:  5.5/10
Isolation/security:           2/10
Durability/resume/retry:      3/10
Marketplace/versioning:       1/10

Yani: çekirdek fikir iyi, execution modeli akıllı, ama SDK/contract/productization tarafı ham.

---
Archiverr’da iyi olan şey ne?

1. Manifest-driven core ciddi iyi karar

Şu yapı doğru:

name: tmdb
run_mode: per_job
stage: data
class_name: TMDbPlugin
entry_point: client.py

requires:
  - plugin.renamer.parsed:success

provides:
  - http.request
  - state.update

trigger_rule: all_success

Bu bence Archiverr’ın en iyi tarafı. Plugin core’a “ben kimim, ne zaman çalışırım, neye ihtiyacım var, ne sağlarım” diyor.

Bu, çoğu hobi self-host projesinde yok. Çoğu projede hâlâ şöyle şeyler görüyorsun:

if plugin_name == "tmdb":
    run_tmdb()
elif plugin_name == "tvdb":
    run_tvdb()

Archiverr’da bu yok. Üstelik proje kuralı olarak core içinde plugin adı yasak. Bu çok iyi.

Keep — Bu mimari korunmalı.

---
2. 3-stage pipeline doğru sınır çizmiş

Archiverr şunu yapıyor:

per_run input plugins
  ↓
PARSE
  ↓
DATA
  ↓
OUTPUT

Bu medya metadata domain’i için temiz. Kestra/Temporal gibi sonsuz DAG sistemi yapmamışsın. Bu iyi, çünkü senin domain’in sınırsız workflow değil; medya dosyasını metadata ile zenginleştirme.

Bu YAGNI açısından doğru:

- parse stage: filename/path/video info çıkar
- data stage: TMDB/TVDB/OMDB gibi external metadata çek
- output stage: rename/task/file/write/render

Keep — Daha fazla stage ekleme. İhtiyaç çıkana kadar bu 3 stage iyi.

---
3. Dependency grouping + parallel execution mantıklı

DependencyResolver requires alanından plugin dependency çıkarıyor:

plugin.renamer.parsed:success -> renamer
job.plugins.renamer.parsed   -> renamer
provides.http.request        -> plugin dependency değil
events.job.created           -> plugin dependency değil

Sonra topological groups üretiyor:

group 1: renamer, ffprobe
group 2: tmdb, tvdb, omdb
group 3: tasker

StageExecutor da grup içini paralel, grupları sıralı çalıştırıyor.

Bu gerçekten güzel fikir. Özellikle şu ayrım iyi:

decide -> invoke -> commit

Parallel path’te worker thread sadece plugin’i invoke ediyor; state mutation main thread’de commit ediliyor. Bu önceki race-condition risklerini azaltır.

Keep — Bu sistem Archiverr’ın en zeki parçalarından biri.

---
4. Trigger rule sistemi domain için iyi

Airflow benzeri:

all_success
one_success
all_done
all_fail
none_fail

ve requires matcher:

plugin.renamer.parsed:success
provides.http.request
events.x:fired

Bu medya metadata için çok yeterli. Örneğin:

requires:
  - plugin.renamer.parsed:success
trigger_rule: all_success

veya ileride:

requires:
  - plugin.tmdb.movie:success
  - plugin.tvdb.show:success
trigger_rule: one_success

Bu gayet güçlü.

Keep — Ama trigger semantics biraz daha dokümante edilmeli.

---
5. Provides registry fikri iyi ama yarım

ProvidesRegistry şunu yapıyor:

http.request
state.update
fs.write:/srv/media
fs.delete

ve status tutuyor:

pending / completed / failed

Ayrıca lockable provides tanımı var:

fs.write
fs.delete
fs.move
fs.hardlink
fs.symlink

Bu konsept güzel. “Plugin ne capability sağlıyor / hangi side effect’i yapacak” sorusunu manifest’e taşıyor.

Ama burada sert eleştiri:

Şu an provides daha çok observability/requirement matcher gibi duruyor; gerçek capability enforcement değil.

Yani plugin manifest’te fs.write demese bile Python kodu dosya yazabilir. Çünkü plugin aynı process içinde trusted code olarak çalışıyor.

Büyük sistemlerde capability demek genelde:

- sandbox
- permission enforcement
- filesystem scope
- network scope
- subprocess isolation
- timeout
- resource limit

Archiverr’da bu yok.

Simplify/Improve — Provides iyi metadata, ama bunu “security boundary” gibi pazarlama. Şimdilik “declared side effects / orchestration capabilities” de.

---
Dış dünyadaki ciddi sistemlerle kıyas

1. HashiCorp go-plugin

Kullananlar:

- Terraform
- Vault
- Packer
- Nomad
- Boundary

Model:

Host process
  ↔ gRPC/RPC
Plugin subprocess

Artıları:

- plugin ayrı process
- crash isolation
- language boundary mümkün
- gRPC contract
- bidirectional communication
- complex argument support
- plugin ölürse host ölmez

Archiverr’a göre üstün:

Isolation: çok daha iyi
Security: daha iyi
Plugin lifecycle: daha olgun
Binary distribution: daha gerçekçi

Archiverr’ın üstün olduğu yer:

Domain-specific orchestration daha basit
Manifest/stage/requires/provides medya pipeline için daha anlaşılır
Python plugin yazmak daha kolay

Sert eleştiri:

▎ Archiverr plugin’i bug atarsa veya process’i kilitlerse tüm run etkilenir. HashiCorp modelinde plugin dış process olduğu için bu çok daha kontrollü.

Ama Archiverr için go-plugin modeli şu an fazla ağır olabilir.

Verdict: Archiverr daha basit ve domain-fit; HashiCorp daha production-grade plugin runtime.

---
2. Arcaflow

Model:

YAML workflow
  ↓
containerized plugins
  ↓
schema-validated inputs/outputs
  ↓
Podman/Docker/Kubernetes execution

Öne çıkanlar:

- container plugin
- Python/Go SDK
- schema validation
- workflow expression language
- input/output data validation
- portable execution

Archiverr’a göre üstün:

Plugin isolation
Typed IO schemas
Container runtime
Portable workflow definitions
SDK maturity

Archiverr’ın üstün olduğu yer:

Medya metadata domain’ine çok daha yakın
3-stage pipeline daha basit
Core plugin-agnostic guard çok iyi

Sert eleştiri:

▎ Archiverr’da plugin result data shape yeterince formal değil. PluginResult.data: dict[str, Any] pratik ama SDK kalitesi açısından zayıf. Arcaflow’da schema mismatch erken yakalanıyor.

Verdict: Arcaflow daha gerçek workflow/plugin platformu. Archiverr daha iyi domain engine.

---
3. Kestra

Model:

YAML declarative workflows
900+ plugins
UI + API
scheduling
event triggers
logs
retries
workers

Archiverr’a göre üstün:

- plugin ecosystem
- retries
- scheduling
- UI
- versioned task/plugin ecosystem
- worker/distributed execution
- large catalog
- typed task definitions

Archiverr’ın üstün olduğu yer:

- çok daha küçük
- medya işine özel
- over-engineered değil
- local homelab için daha anlaşılır

Sert eleştiri:

▎ Archiverr plugin sistemi “plugin ekosistemi” değil, “project-internal extension system”. Kestra gibi dış geliştirici dostu plugin marketplace/SDK/semver/documentation seviyesi yok.

Verdict: Kestra platform; Archiverr focused engine.

---
4. Temporal / Conductor

Bunlar plugin sisteminden çok durable workflow engine.

Sunduğu şeyler:

- durable execution
- retries
- pause/resume
- crash recovery
- long-running workflow
- task queues
- distributed workers
- UI observability
- replayability

Archiverr’da eksik:

retry policy
durable resume
idempotency model
per-step retry
timeout/cancel
worker queue
distributed execution
workflow history replay

Archiverr’da güzel olan:

plugin_execution state kaydı başlamış
save_plugin_execution var
stage executor state transition tutuyor

Ama bu henüz Temporal/Conductor seviyesinde değil.

Sert eleştiri:

▎ Archiverr’da “execution state” recovery bookkeeping gibi duruyor, durable workflow garantisi değil. Run yarıda kalırsa hangi plugin tekrar koşacak, hangisi idempotent, hangisi side-effect yaptı, bunlar contract olarak yeterince sert değil.

Verdict: Durable orchestration yok. Ama şu an gerekmez; rename/write aşaması büyürse gerekecek.

---
5. PF4J / DotNetCorePlugins

Bunlar classic plugin frameworks.

PF4J:

- Java plugin JAR
- plugin descriptor
- lifecycle: load/start/stop
- extension points
- classloader isolation
- plugin dependencies

DotNetCorePlugins:

- assembly loading
- dependency isolation
- shared type boundary

Archiverr’a göre üstün:

plugin packaging
versioning
extension point semantics
load/unload lifecycle
dependency isolation

Archiverr’ın üstün olduğu yer:

workflow ordering
requires/provides
stage execution
domain pipeline

Sert eleştiri:

▎ Archiverr’da plugin lifecycle çok basit: discover/load/execute. Start/stop/unload, compatibility boundaries, plugin API version, migration/deprecation sistemi yok.

Verdict: Archiverr orchestration’da daha domain-akıllı; plugin lifecycle’da daha zayıf.

---
6. Claude Code plugin sistemi / Open Plugin Spec tarzı sistemler

Bunlarda manifest, marketplace, dependency resolution, MCP servers, commands, hooks, agents, schemas, install/update/blocklist gibi devasa yüzeyler var.

Archiverr’a göre üstün:

- marketplace
- install/update
- dependency graph
- manifest schema çok geniş
- plugin component discovery
- blocklist/trust
- multiple component types

Archiverr’ın üstün olduğu yer:

- çok daha sade
- tek domain
- runtime daha anlaşılır
- “plugin ne zaman çalışır?” sorusu daha net

Sert eleştiri:

▎ Archiverr plugin sistemi dış dünyaya açılacaksa manifest validation çok küçük kalır. extra = ignore şu an plugin author hatalarını saklayabilir. Public SDK için unknown fields warning/error daha iyi olur.

Verdict: Archiverr internal plugin sistemi olarak iyi; public plugin ecosystem olarak erken.

---
Archiverr’ın en iyi tasarım kararları

Keep — Core plugin-agnostic guard

Core içinde plugin adı yasak kuralı çok iyi. Bu mimariyi koruyan test var:

test_plugin_agnostic.py

Bu seni birçok self-host projenin düştüğü bataktan korur.

Bence bu proje için “architectural gold” bu.

---
Keep — Manifest required stage/run_mode

PluginManifest artık stage ve run_mode zorunlu tutuyor:

if self.stage is None:
    raise ValueError(...)
if self.run_mode is None:
    raise ValueError(...)

Bu çok iyi. Default fallback’ler silinmiş. Sessiz sihir azalmış.

---
Keep — Modern plugin contract

Per-job plugin:

execute(job, services) -> PluginResult

Per-run plugin:

execute_run(services) -> dict

Eski adapter/dict fallback/signature introspection silinmiş. Bu çok iyi. Çünkü “esneklik” adı altında runtime çöpü biriktirmiyor.

---
Keep — Decide/invoke/commit separation

Parallel execution için en önemli şey bu:

workers: plugin code
main thread: state mutation

Bu bilinçli tasarım.

---
Sert eleştiriler

1. SDK hâlâ zayıf

BasePlugin, InputPlugin, OutputPlugin var ama plugin author deneyimi hâlâ “koddan anla” seviyesinde.

Eksikler:

Plugin API version yok
Manifest schema version yok
Typed config object yok
Typed result schema yok
Plugin template/generator yok
Official examples zayıfsa public adoption zor

Şu an plugin yazan kişi şunları bilmek zorunda:

- manifest formatı
- run_mode/stage ilişkisi
- requires syntax
- PluginResult formatı
- services API
- state model
- dry_run/no_delete beklentisi
- provides semantics

Bunlar çok güçlü ama “SDK” gibi paketlenmemiş.

Simplify/Improve:

archiverr plugin init tmdb-provider
archiverr plugin validate path/to/plugin
archiverr plugin inspect plugin-name

ve tek sayfalık plugin author contract lazım.

---
2. Plugin isolation yok

Plugin’ler in-process Python import ediliyor:

module = importlib.import_module(...)
instance = plugin_class(plugin_config)

Bu basit ve doğru, ama güvenlik/isolation yok.

Riskler:

- plugin process’i kilitler
- memory leak
- global state mutation
- monkey patch
- file write bypass
- network access bypass
- dependency conflict
- Python import side effects

Archiverr trusted local plugins için bu kabul edilebilir. Ama “plugin marketplace” hayali varsa yetersiz.

Keep for now — Çünkü sandbox eklemek şu an overkill.
Question for future — Third-party plugin dağıtımı olacak mı?

Eğer cevap evetse, minimal çözüm:

subprocess plugin runner
JSON-RPC/stdin-stdout
timeout
env isolation
working dir isolation
capability declaration

Container’a hemen atlama; önce subprocess yeter.

---
3. Requires/provides syntax güçlü ama fazla stringly-typed

Şu çok esnek:

requires:
  - plugin.renamer.parsed:success
  - provides.http.request

Ama string bazlı olduğu için hata riski var:

plugin.renmaer.parsed:success

Bunu runtime’da geç fark edebilirsin.

Büyük sistemler burada schema/typed contracts kullanıyor.

Simplify/Improve:

Manifest validator şunları yakalamalı:

- requires içindeki plugin adı mevcut mu?
- required plugin aynı stage’de mi, önceki stage’de mi?
- impossible dependency var mı?
- provides unknown capability mi?
- plugin.x.y:success syntax geçerli mi?

Bunun bir kısmı var, ama daha sert olabilir.

---
4. DependencyResolver fazla basit

Şu an dependency sadece requires path’ten plugin adı extract ederek graph kuruyor.

Bu iyi ama sınırlı.

Problem örnekleri:

requires:
  - provides.http.request

Bu plugin dependency olarak graph’a girmiyor. Eğer aynı stage’de bir plugin http.request provide ediyorsa ve diğeri ona requires diyorsa execution order garanti değil. Çünkü resolver provides.* için None dönüyor.

Bu doğru olabilir — çünkü provides.http.request global capability gibi düşünülmüş. Ama eğer provides gerçekten dependency olarak kullanılacaksa, graph bunu çözmeli.

Question:

▎ provides.* sadece “capability completed mi?” check’i mi, yoksa ordering dependency mi?

Eğer ordering dependency ise resolver eksik. Eğer sadece runtime condition ise dokümante edilmeli.

---
5. Error semantics biraz yumuşak

_invoke_safely bütün exception’ları PluginExecutionResult(success=False) yapıyor. Stage devam ediyor.

Bu “best-effort” için iyi. Ama bazı plugin failure’ları fatal olmalı.

Örneğin:

- scanner fail -> run devam edemez
- renamer parse fail -> o job için data stage skip
- tasker write fail -> output stage critical olabilir
- config validation fail -> startup fail mi, plugin skip mi?

Şu an bazı yerlerde plugin skip ediliyor, bazı yerlerde stage error oluyor. Bu policy daha net olmalı.

Simplify/Improve:

Manifest’e hemen karmaşık policy koyma. Önce basit:

failure_policy: optional | required

Default:

input/per_run: required
parse: required for downstream if required
data providers: optional olabilir
output writers: required olabilir

Ama bunu sadece gerçek ihtiyaç çıktığında ekle.

---
6. Per-run executor per-run dependency/parallelism açısından zayıf

PerRunPluginExecutor per_run plugin’leri sırayla çalıştırıyor. Şu an scanner gibi tek plugin varsa sorun yok.

Ama ileride:

scanner
rss-input
manual-list-input
torrent-watch-input

gibi birden fazla per_run plugin gelirse, per_run side effects ve dependency semantics yok.

Şimdilik Keep — çünkü tek/az input plugin var.
Üçüncü per_run plugin gelince resolver aynı mantıkla per_run’a da uygulanabilir.

---
7. Registry/loader hâlâ legacy baggage taşıyor

load_by_category('input'), load_by_category('output'), legacy config formats, FlexGet format gibi izler var.

Bu geçiş döneminde normal. Ama uzun vadede plugin sistemi temiz görünmesini engeller.

Örnek:

input_plugins = self._loader.load_by_category('input')
output_plugins = self._loader.load_by_category('output')

Yeni sistem stage/run_mode ise category abstraction artık tarih olmalı.

Simplify later — Şu an silme, çünkü migration bitmemiş olabilir. Ama hedef:

load_enabled_plugins()
group by run_mode/stage from manifest

olmalı.

---
8. Public docs/authoring story yoksa sistem “zeki ama kapalı” kalır

Sen sistemi seviyorsun çünkü içini biliyorsun. Dışarıdan biri için şu sorular net değilse plugin sistemi değerini gösteremez:

- Plugin nasıl yazılır?
- Minimal manifest nedir?
- requires syntax nedir?
- provides ne işe yarar?
- PluginResult nasıl döner?
- State’e nasıl veri yazılır?
- Dry-run/no-delete nasıl respect edilir?
- Config schema nasıl yazılır?
- Hangi plugin hangi stage’de olmalı?
- Test nasıl yazılır?

Bu sistemin kalitesini yükseltecek en ucuz iş dokümantasyon + plugin template.

Kod yazmaktan daha değerli olabilir.

---
Archiverr vs büyük sistemler: net tablo

┌────────────────────────┬────────────────────────────────────────────┬────────────────────────────────────────┐
│         Sistem         │           Archiverr’a göre üstün           │     Archiverr’ın üstün olduğu yer      │
├────────────────────────┼────────────────────────────────────────────┼────────────────────────────────────────┤
│ HashiCorp go-plugin    │ process isolation, RPC, crash safety       │ domain-specific pipeline, simplicity   │
├────────────────────────┼────────────────────────────────────────────┼────────────────────────────────────────┤
│ Arcaflow               │ container plugins, typed schema IO         │ medya metadata’ya özel orchestration   │
├────────────────────────┼────────────────────────────────────────────┼────────────────────────────────────────┤
│ Kestra                 │ huge plugin ecosystem, UI, scheduling,     │ küçük, anlaşılır, homelab-friendly     │
│                        │ retries                                    │                                        │
├────────────────────────┼────────────────────────────────────────────┼────────────────────────────────────────┤
│ Temporal               │ durable workflow, retries, resume          │ çok daha az operational yük            │
├────────────────────────┼────────────────────────────────────────────┼────────────────────────────────────────┤
│ Conductor              │ internet-scale orchestration               │ local metadata pipeline için overkill  │
│                        │                                            │ değil                                  │
├────────────────────────┼────────────────────────────────────────────┼────────────────────────────────────────┤
│ PF4J                   │ lifecycle, packaging, classloader          │ requires/provides stage execution      │
│                        │ isolation                                  │                                        │
├────────────────────────┼────────────────────────────────────────────┼────────────────────────────────────────┤
│ Claude plugin system   │ marketplace, install/update, component     │ runtime çok daha sade                  │
│                        │ ecosystem                                  │                                        │
├────────────────────────┼────────────────────────────────────────────┼────────────────────────────────────────┤
│ OpenShift dynamic      │ remote web plugin loading                  │ backend metadata pipeline için daha    │
│ plugins                │                                            │ uygun                                  │
└────────────────────────┴────────────────────────────────────────────┴────────────────────────────────────────┘

---
Benim dürüst hükmüm

Senin plugin sistemin zekice, ama “kompleks olduğu için iyi” değil. İyi olduğu yerler şunlar:

1. Domain’i iyi sınırlamışsın — sonsuz workflow engine değil.
2. Manifest-driven yapmışsın — core plugin bilmez.
3. Requires/provides ile ordering/condition ayrımı kurmuşsun.
4. Stage modeli medya metadata pipeline’ına cuk oturuyor.
5. Parallel execution’da state mutation’ı main thread’e toplamışsın.
6. Legacy fallback’leri silmeye başlamışsın — bu kalite göstergesi.

Ama sistemin zayıf olduğu yerler de net:

1. SDK public ürün kalitesinde değil.
2. Plugin isolation yok.
3. Typed IO/result schema yok.
4. Durable retry/resume yok.
5. Plugin version/API compatibility yok.
6. Provides capability enforcement değil, declaration.
7. Docs/template yoksa dış geliştirici için zor.

---
Ne yapmanı öneririm?

Hemen yapılacak en değerli 5 şey

1. Plugin author guide

Tek dosya:

docs/plugins/authoring.md

İçerik:

- minimal plugin
- manifest.yml
- run_mode/stage
- requires/provides
- config_schema
- PluginResult
- services API
- dry_run/no_delete
- test örneği

Bu sistemin algılanan kalitesini 2 kat artırır.

---
2. Plugin template

examples/plugins/example-provider/
  manifest.yml
  client.py
  test_example_provider.py

Plugin sistemi ancak “kopyala değiştir” örneğiyle yaşar.

---
3. archiverr plugin validate

Manifest + config + import + contract check:

archiverr plugin validate src/archiverr/plugins/tmdb

Kontrol:

- manifest parse
- required fields
- stage/run_mode
- class exists
- execute signature
- config_schema valid
- requires references possible
- provides known format

---
4. Manifest schema version

Basit:

api_version: archiverr.plugin/v1

Şimdi eklemek ucuz, sonra çok değerli olur.

---
5. Requires/provides static validation

Startup’ta şunları yakala:

plugin.renmaer.parsed:success -> unknown plugin renmaer
provides.fs.wirte -> unknown provide
same-stage dependency impossible/cyclic

Bu kod kalitesini ciddi artırır.

---
Ne yapmamalısın?

Şu an sandbox/container plugin yazma

Çok cazip ama overkill. Önce SDK/docs/validation.

Şu an marketplace yazma

Daha plugin author story hazır değil.

Şu an generic workflow engine’e dönüşme

Kestra/Temporal olma. Archiverr’ın gücü generic olmaması.

Şu an 10 tane trigger rule ekleme

Mevcut 5 rule yeterli.

---
Son söz

Abi senin plugin sistemine “boş hype” demem. Gerçekten iyi fikirler var. Özellikle manifest-driven stage orchestration + requires/provides + plugin-agnostic core guard kombinasyonu self-host medya projelerinde sık görülen bir kalite değil.

Ama sert gerçek şu:

▎ Archiverr şu an “çok iyi düşünülmüş internal plugin runtime”.
▎ Henüz “olgun public plugin platform / SDK ecosystem” değil.

Bence doğru hedef de şu olmalı:

Archiverr = medya metadata domain’inin Kestra’sı değil,
Archiverr = Jellyfin/Radarr/Sonarr dünyasındaki metadata plugin runtime’ı.

Bu hedef için mevcut temel sağlam. En büyük kalite artışı yeni runtime complexity değil; SDK contract, docs, validation, examples tarafında.
Interrupted · What should Claude do instead?

❯  sana varya normalde az once "Şimdi senden istediğim şey şu internetteki plugin orkestrationları araştır, plugin workflowları araştır, diğer açık hayal projelerdeki en kompleks ve en kapsamlılarını getir ve bizimkiyle karşılaştır. Şunu planlıyorum, acaba bu projedeki, bu archiver projesindeki plugin sistemi, plugin altyapısı ayrı bir middleware olarak ayarlamaya değer bir altyapı mı? Yani yoksa değil mi? olay şu arkayı projesindeki bu plug-in mantığını abi ben çok fazla projede kullanasım geliyor Çünkü gerçekten bir proje can katan özelliklerden bir tanesi ya her projenin bu tarz bir şeye gerek olması gerekiyor ama gerçekten de sıkıntı şu her projenin böyle bir şey farklı bir açıdan ihtiyacı oluyor bu projenin mesela bu olay abi bir metadata Playground olmak yani bir plugin Playground alıp plugin Playground sistem düzeyinde arşiv düzenleme amaçlı çalışıyor mesela başka bir projede ben mesela yapay zeka Agent orkestrasyon üzerine çalıştıracağım mesela bu plugin Playground ba bir projede ba bir ama her projede farkl ama i hani her projeye entegre etmek biraz zor plug sistemi bunun entegre edilebilirli d istiyorum internetteki karma plug altyap ve ayn zamanda internetteki direkt projene takabilecek plug-in middleware'larını araştırmanı istiyorum ve direkt hani sistemlere plug-in entegrasyonu sağlamak için güzel plug-in altyapıları var mı de bunları araştırmak istiyorum bizim plugin sisteminde eleştirebilirsin komplekslikten ziyade stabilite ve kalite kod kalitesi açısından eleştirebilirsin sdk ve kullanım açısından vesaire yani ne kadar iyi diğer plugin sistemlerine göre şöyle net sert eleştiriler ve gerçekten de kafamdaki o farklı projeler takılabilir bir net plugin middleware yapmak konusunda neden yapılamayacağını veya neden yapılabilir olacağına alakalı sorular cevaplar Bir yandan da Yani ben bayılıyorum bu plugin Sistemine bu projedeki Çünkü internette olmayan Gerçekten de güzel Architecture inşa edilmiş Sağlam inşa edilmiş bir sistem var yani bence Buradaki Çünkü sadece bir requires Provides'da ibaret değil aslında bu sistem Buradaki plugin altıymış Hani Pluginlerin sırası çalışma prensibi o kadar iyi ki. "  bu promptu yazacaktım ama dedimki olm bizim sistemdekii Yani bizim sistemdeki yapı birazcık bu projeye domayın özel dedim. Yani eğer ki yaparsam bu tarz bir orkestrasyon, plugin orkestrasyon altyapısı, bizim projedeki bazı future'ları yok etmek zorunda kalırım diye bir anda bana aydınlanma geldi. Ne gibi future'lar mesela? yani bu kastım Aslında şu bu Pronto oku anlarsın başka projelerde devletmek istiyordu mesela tane orkestrasyon projesine devletmek istiyordum tamam mı o orkestrasyon projesinde ekle ettiğimde mesela bizim arkaya projesindeki plugin yapısını değiştirmem gerekiyordu. Çünkü bu projedeki plugin yapısı tamamen plugin orkestrasyonundan ibaret değil. Birazdan stage ve workflow yapısı bu projede elzem. Neden? Şimdi konuya geleyim. Hani bu prompta sana araştırma istediğim şeyi var ya. tam olarak galiba Kestra şu an sen cevap yazarken gördüm Kestra bildiğin bizim yaptığımız her şeyi çok daha kapsamlı bir şekilde yapan bir proje yani yanlış anlamadıysam Kestra'dan farkımız aslında gerçekten de senin dediğin gibi doğru bir şekilde daha küçük olmamız çünkü daha ölçeklendirilebilir olmak ile sürekli savaş halindeyim  /home/samet/Workspace/bedrock/bedrock/Tasarilar/avarager/user-prompts/18.md  Yani şu 18. Promptum Oku Averager projesini birazcık anla aslında neden bahsettiğimi anlayacaksın. Benim aslında bu hani orada da söylediğim gibi. Modülerlik ve stabilitenin savaşını sonlandır. Yani bu savaş içerisinde sağ çıkan bulgular Archiver projesinin kendisi. Bu ne demek oluyor? Yani bu Kestra projesinin bizim projemizin Kestra projesinden farkını aslında ortaya çıkartıyor. Çünkü Kestra projesi potansiyeli abanmış ama bizim aynı zamanda hem stabiliteye hem potansiyeli abanmamız gerekiyor. Average Projesi'ne bak ve Archiver Projesi'ne bak. İkisinde de aslında yakalamaya çalıştığım hedef şu. Mümkün olduğunca stabiliteyi ve potansiyeli bir arada harmanlamak. Ben potansiyeli odakland s Chester gibi bir plugin orchestrasyon altyap d Ama stabiliteyi odakland s de hardcoded ve s kod i zorlama i yapt Yani Kestra projesi gerçekten de benden çok çok önce bu plugin orkestrasyon yapısını oluşturmuş şirketlere satmaya başlamış bile. Ama bu projeye ne kadar entegre edilebilir? Önemli hususlardan bir tanesi. Mesela biz Arkiber projesinde bile kestrayı takabilir miyiz? Böyle bir şey mümkün kestrada. Yoksa kestr tam olarak ne işe yarıyor? Gerçekten de çok dikkatimi çeken bir proje oldu şu anda. Çünkü tam olarak bizim yaptığımız şeyi aslında promosyonel ve ölçekli düzeyde yapıyor. Çok ilginç. Ama dediğim gibi biz burada sadece potansiyeli değil stabiliteye davarlık verdiğimiz için bizim projemiz küçük falan diye açıklamışan bu durum ama küçüklükten ziyade aslında stabilite yani olay burada. Biz burada gidip de inanılmaz bir potansiyel ve orkestrasyon ve imkan potansiyeli için çıkıp da Stability'den ödün vermiyoruz. Yani benim en azından görüşüm bu şekilde. Şimdi bu görüşümün ne kadar doğru olduğunu eleştir. Cestra projesinde neler örnek alabiliriz bu projeye? Bu projemizde neler çok ham kalmış, neler çok mantıklı? Çok dürüst bir şekilde analizleri istiyorum senden.Tam olarak Cloud Code Plugin sistemini de çok fena anlamadım açıkçası. Yani Archiver'daki orkestrasyon ve run tasarım kararları mesela. yani arkay buradaki bu requires provides sistemleri yani o bu Runtime sırasındaki mantık hani bu acaba Cloud Coden plug-in sistemler üstün mü? Yoksa Cloud Coden plug-in sistemi bizim projeden daha üstün. Daha detaylı analizler yapmanı istiyorum. Ve tüm bu analizlerin ve araştırmaların sonucunda gerçekten net karar getirmemiz lazım. Arkyver projesine neler katmalıyız. Gördüğüm kadarıyla tüm bu yazılımlar gerçekten de her biri farklı alanla ilgilenen sistemler. En şu anda soru işareti bıraktıran Cloud Code'un sistemi diğerleri mesela örneğin Conductor, Temporal bunlar mesela bizim açıkçası Archiver'a eklemek istediğim özelliklerden bir tanesi. .net core plugin deki olaylar da mantıklı. Özellikle manifest konusunda bizden çok daha üstünler gibi gözüküyor. Bunlarda mesela eklenebilir. Caster'a çok ayrı bir konu. Onu sen çok daha iyi inceleyeceksin. zaten bana getireceksin Onunla alakal neler eklenebilir neler eklenemez Ondan sonra arka Flow ve ha go plugin abi yani konusunda ayr CSS işte Kıraş izolayışın o alıdır Sen bak olayları vesaire dedi ki fslokun bizdeki fslokların veya provat değerlerini yalnızca deklaert olması gerçekten de bir şeyleri kapatmamaları bunlar çok ham şeyler açıkçası provides şu an işimi gördüğü için kullanıyorum yani ne yapayım abi sıfırdan yazamazdım yani sıfırdan plug-inlere öyle bir sistem yapsam sıkıntı olurdu dediğim gibi progresinin değişmesi gerekiyor bu vaysın kaldırılması gerekiyor hatta probat yerine tek bir requires bile yeter biliyor musun Aslında şöyle söyleyeyim requires içerisinde sayıl sistem izni require ettiğinde ya da yok ya şimdi düşündüm ne mantıksız yine provasını şart probat kanmalı Çünkü şöyle bir şey bizim problemizde file erişimi dosya yazma erişimine sahip olması kesinlikle belli dosyaları değiştireceği anlamına geliyor mu? bu önemli bir kriter çünkü sırayı değiştirecek bir olay o yüzden provides'in aslında declared olması daha çok işimize geliyor diyebilirim yani olabilirim yani hani bence bu bilgis ile probas ayr olaylar ya evet neyi de Dependency olarak da hani sistemin workflow bir de ama neyi değiştirebileceğinin kararını plugin'in vermesi daha sağlıklı gibi çünkü bazı plugin'ler örneğin dosya silme izlene ihtiyaç duyup da Ondan sonra çalışacak plug-inin sileceği şey editleyeceği klasöre erişim olmayacak ya aslında buradaki yapışından başlıyor Cloud senkronizasyon sistemi yapacağız diyelim ki bir plug-in değişiklik yapıyor ve bir plug-in Cloud senkronizasyon yapıyor bu sırada ne olacak abi plug-in değiştirdikçe girecekler tekrar tekrar senkronizasyon. Bunu önlemek için abi bir plugin dosya düzenleme, bir plugin ise işte dosya okuma kgoldisiyim vereceğim. Hayır. Ama daha mantıklı, daha pluginlerin kendi deklar ettiği bir şekilde orkestrasyon ve dependans yapmak gerekiyor diye düşündüm. Pluginlerin mümkün olduğunca özgürlük tanımak istedim. Onların Pluginden ziyade onlara kendi kararlarını kendi verebilen güvenilir. Ama orkestrasyonu birbirlerini bilerekten çalıştıran yapılar yapmak istedim. Yanlış bir karar olabilir. Ama şu anda yani hard koduk bir şekilde bu dosya dosya okuyorsa o zaman bu dosya şunu yapamaz. Bundan sonra zorunda gibisinden kararlar verdirmeye k Bence bu Provide Declared yani plugin declared sistem daha sistemin stabilitesini d de sistemin potansiyelini arttırıyor diye düşünüyorum yani ne tip bir gerçek örnek veremediğim için saçmaladığını bilirsin ki haksız da olmayabilirsin Çünkü çok akıllıca konuştuğunu bende düşünmüyorum şu anda ama burada değinmek istediğim bir nokta olduğuna eminim beynimde şu anda sana söyleyemediğim bir örnek var bu örnek provides ile capabilities farkını aslında ortaya çıkartıyor yani capability ile bir şeyi yapabilmek ile bir şey yapmak arasındaki net farkı ortaya koyuyor provides ya abi mesela bilmiyorum en büyük aslında bu provaysın oluşturduğu en büyük problem şey çözdüğü en büyük problem file sistemi ile alakalıydı dosya sisteminde birisi yazarken birisinin güncellemesi dönümlerinden bulmak için plug-in declared bir sistem yapmak istedim bu yanlış bir karar mı bunun önüne nasıl geçiyor diğer büyük projeler bence geçemiyorlar açıkçası böyle bir özgürlüğü başka hiçbir projenin tanıdığını düşünmüyorum sen umarım benim aklımdaki anlatmak istediğim örneği anlamışsın da tam ben aktaramadım sana ama her neyse araştırmanı analizleri çok derin yap bana Hızlıca bakıp gelme. Bana gerçekten de net cevaplar, kaynaklı, kaliteli cevaplar ver. Harbiden istediğim şeyi ver bana.

  Read 1 file

● 2 human-research agents finished
Kestra deep comparison · 0 tool uses
⎿  Done
Plugin systems comparison · 0 tool uses
⎿  Done

● claude-code-guide(Claude plugin analysis) Sonnet 4.6
Initializing…
Error: Cannot create agent worktree: not in a git repository and no WorktreeCreate hooks are configured. Configure WorktreeCreate/WorktreeRemove hooks in settings.json to use worktree isolation with other VCS systems.

  Ran 3 shell commands

Abi şimdi anladım: sen “Archiverr plugin sistemi güzel, bunu her projeye takılabilir generic middleware yapayım mı?” sorusunu soruyorsun ama aynı anda fark etmişsin ki:

▎ Archiverr’daki değer sadece “plugin loader” değil; domain’e göre daraltılmış run modeli + stage modeli + requires/provides + safety disiplini + plugin-agnostic core birleşimi.

Bu aydınlanman doğru. Hatta bence kritik mimari karar burada.

Net kararım

Archiverr plugin sistemini direkt generic middleware olarak çıkarmaya çalışma.

Ama:

Archiverr’dan bir “orchestration kernel/spec” çıkarılabilir.

Yani şu iki şeyi ayır:

Yanlış hedef:
  "Archiverr plugin sistemi her projeye aynen takılsın."

Doğru hedef:
  "Archiverr'daki kazanılmış orkestrasyon prensipleri,
   proje başına domain-specific runtime recipe ile yeniden kullanılabilsin."

Başka deyişle:

Archiverr Plugin Runtime ≠ generic middleware

Archiverr Plugin Runtime =
  generic sayılabilecek küçük çekirdek
  + medya metadata domain'ine özel execution recipe

Bu ayrımı yapmazsan ya Archiverr’ın stabilitesini bozarsın ya da çıkaracağın generic sistem işe yaramaz kadar soyut olur.

---
1. Kestra tam olarak ne?

Kestra bir “projene import edip plugin runtime olarak kullanacağın library” değil. Kestra şudur:

Standalone workflow orchestration platform
  - server
  - repository
  - queue
  - internal storage
  - workers
  - UI
  - YAML flows
  - task/trigger/condition plugin ecosystem

Kestra’da plugin şu anlama geliyor:

Plugin = task / trigger / condition / integration capability
Workflow = bu pluginleri hangi sırada, hangi koşulla çalıştıracağını belirleyen YAML

Kestra docs’taki ayrım önemli:

▎ Workflow orchestration logic’i tanımlar. Plugin execution capability sağlar.

Yani Kestra’da plugin kendi başına “beni requires/provides ile diğer pluginlere göre koştur” demiyor. Çoğu zaman flow bunu belirliyor.

Archiverr’da ise plugin manifest’i şunu söylüyor:

stage: data
run_mode: per_job
requires:
  - plugin.renamer.parsed:success
provides:
  - http.request
  - state.update

Yani Archiverr’da plugin sadece capability değil, aynı zamanda domain execution contract bildiriyor.

Bu önemli fark.

---
2. Kestra’yı Archiverr’a takabilir miyiz?

Teknik olarak evet, pratik olarak hayır / tavsiye etmem.

Kestra’yı Archiverr’a takarsan şunu yapmış olursun:

Archiverr Python domain runtime
  ↓
Kestra server / flow / task / worker dünyası
  ↓
tekrar Python metadata plugin logic

Bu sana şunları getirir:

- UI
- retry
- scheduling
- logs
- worker model
- YAML workflow
- plugin ecosystem
- durable execution

Ama şunları kaybettirir:

- Archiverr’ın küçük/stabil runtime’ı
- Python içi hızlı state erişimi
- domain-specific stage netliği
- plugin-agnostic core testlerinin sadeliği
- “medya metadata pipeline” mental modelinin basitliği
- requires/provides’in domain’e oturan yapısı

Kestra kullanmak şuna benzer:

▎ Bir arşiv düzenleme motoruna Kubernetes klasmanı workflow engine bağlamak.

Güçlü ama ağır.

Archiverr için Kestra’yı entegre etme. Ondan fikir çal.

---
3. Kestra’dan ne çalmalıyız?

Keep/copy — Plugin authoring kalitesi

Kestra’nın güçlü tarafı plugin runtime’dan çok plugin ecosystem productization.

Onlarda var:

- plugin template
- developer guide
- task property schema
- generated docs
- output schema
- retry/failure policy
- plugin publish/build standardı
- compatibility version
- property grouping:
  - main
  - connection
  - source
  - processing
  - execution
  - destination
  - reliability
  - advanced

Archiverr’da en ham kalan taraf bu.

Archiverr’a direkt eklenebilir:

api_version: archiverr.plugin/v1

config_schema:
  api_key:
    type: string
    required: true
    secret: true
    group: connection

  language:
    type: string
    default: tr-TR
    group: main

reliability:
  timeout_seconds: 60
  retries: 2

Ama dikkat: hemen full Kestra clone yapma.

İlk kopyalanacak şey:

plugin template
plugin validate command
plugin docs generation
api_version / min_core_version
timeout / retry

---
Keep/copy — Large output handling

Kestra küçük output’u inline, büyük output’u internal storage URI olarak döndürme modeline sahip.

Archiverr’da plugin result şu an:

PluginResult(data=dict)

Bu küçük metadata için iyi. Ama posterler, raw API dumps, subtitles, NFO, images, huge search results büyürse kötüleşir.

Archiverr’a şu fikir eklenebilir:

{
  "data": {
    "movie": {...},
    "raw_uri": "archiverr://artifacts/run123/tmdb/raw.json"
  }
}

Yani:

small data -> PluginResult.data
large artifact -> artifact store URI

Bu Kestra’dan alınabilecek çok iyi fikir.

---
Keep/copy — Task/plugin docs from schema

Archiverr plugin manifest’lerinden otomatik docs üretmek çok değerli olur:

archiverr plugin docs
archiverr plugin inspect tmdb
archiverr plugin validate tmdb

Bu sistemin “zeki ama kapalı” halini “kullanılabilir SDK” haline getirir.

---
4. Kestra’dan ne almamalıyız?

Remove — Generic workflow engine olma

Archiverr’ın gücü şu:

per_run input
PARSE
DATA
OUTPUT

Bu daraltma stabilite sağlıyor.

Kestra gibi sonsuz DAG, arbitrary branches, subflows, schedules, workers, distributed queue eklersen Archiverr’ın ruhunu bozarsın.

Senin söylediğin “potansiyel vs stabilite savaşı” burada çok doğru.

Kestra potansiyele abanıyor. Archiverr ise:

domain-specific potential
+ hard stability rails

Bu daha kıymetli.

Remove — Kestra’yı embedded dependency yapma

Kestra Java platform. Archiverr Python project. Archiverr’a Kestra koymak:

- operational complexity
- deployment complexity
- plugin authoring friction
- domain state impedance mismatch

getirir.

Archiverr için kötü trade.

---
5. Claude Code plugin sistemi Archiverr’dan üstün mü?

Kısa cevap:

Farklı sınıf.

Claude Code plugin sistemi daha çok şuna benziyor:

Plugin package manager + component loader

Bileşenler:

- slash commands
- skills
- agents
- MCP servers
- hooks
- settings
- output styles
- marketplace/install/update
- plugin manifest
- dependency/caching/blocklist gibi packaging işleri

Ama Claude Code plugin sistemi Archiverr’daki anlamda bir runtime workflow orchestrator değil.

Claude Code plugin’i şunu yapar:

Bu komutu/skill'i/agent'i/tool'u Claude ortamına ekle.

Archiverr plugin’i şunu yapar:

Bu medya pipeline'ında şu stage'de,
şu dependency sağlanınca,
şu job üzerinde,
şu side-effect/provide contract ile çalış.

Bu yüzden:

Claude Code > packaging / installation / component ecosystem
Archiverr > domain runtime ordering / execution semantics

Claude Code’dan alınacak şeyler:

- plugin manifest standardı
- plugin lock file
- marketplace fikri
- plugin enable/disable
- dependency/version resolution
- plugin validation
- installed plugin state
- docs/metadata

Claude Code’dan alınmayacak şey:

- Archiverr execution modelini onun component modeline çevirmek

Çünkü Claude plugin sistemi “workflow dependency planner” değil.

---
6. HashiCorp go-plugin / DotNetCorePlugins / PF4J ne öğretiyor?

Bunların ana dersi:

▎ Plugin sadece extension point değildir; plugin boundary meselesidir.

Archiverr şu an:

importlib.import_module(...)
plugin.execute(...)

Yani trusted in-process plugin.

Bu basit, hızlı, doğru. Ama boundary yok:

- crash isolation yok
- dependency isolation yok
- timeout enforce yok
- memory isolation yok
- malicious plugin engeli yok
- capability enforcement yok

HashiCorp go-plugin:

host process ↔ RPC/gRPC ↔ plugin subprocess

DotNetCorePlugins/PF4J:

assembly/classloader isolation
load/start/stop lifecycle
version/dependency boundary

Archiverr’a direkt bunları almak şu an fazla. Ama ileride “third-party plugin marketplace” olacaksa kaçınılmaz.

Şimdiki karar:

Internal/trusted plugins: in-process kalsın.
Untrusted/external plugins: ileride subprocess runner.

Yani iki seviye:

runtime:
  isolation: in_process   # default
  # future:
  # isolation: subprocess

Şimdi subprocess yapma. Ama manifest’e api_version koy ki ileride kırmadan büyü.

---
7. Provides vs capabilities meselesi

Sen burada doğru bir noktayı yakalamışsın.

Capability = yapabilir

Örnek:

capabilities:
  - fs.write
  - http.request

Bu “plugin’in izin istediği şey”.

Provides / effects = yapacağını beyan eder

Örnek:

provides:
  - state.update
  - fs.write:/media/movies

Bu “bu plugin çalışırsa sistemde ne üretir / hangi side effect olabilir”.

Bunlar aynı şey değil.

Senin verdiğin cloud sync örneği çok iyi:

Plugin A: dosya değiştiriyor
Plugin B: cloud sync yapıyor

Eğer B, A ile aynı anda çalışırsa:

- yarım dosya sync olabilir
- tekrar tekrar sync tetiklenebilir
- stale snapshot oluşabilir

Burada mesele sadece “B fs.read yapabilir mi?” değil. Mesele:

A hangi path üzerinde write effect üretiyor?
B hangi path’i read/sync snapshot olarak tüketiyor?

Bu capability değil, effect/dependency orchestration.

O yüzden provides fikrini kaldırma.

Ama adını/semantics’i netleştir.

Bence en doğru ayrım:

capabilities:
  - fs.write
  - http.request

effects:
  - fs.write:/media/movies
  - state.update:metadata

requires:
  - plugin.renamer.parsed:success
  - effect.fs.write:/media/movies:done

Ama şu an provides kelimesini kullanıyorsun. Kötü değil. Sadece docs’ta şunu söyle:

▎ Provides is not permission. Provides is declared output/effect for orchestration.

Yani:

capability = may do
provide/effect = will produce / may mutate
requires = must observe before running

Bu ayrım çok değerli.

---
8. Diğer büyük projeler bu problemi nasıl çözüyor?

Çoğu çözmüyor; başka seviyede çözüyor.

Argo Workflows

Argo’da synchronization var:

- mutex
- semaphore
- database-backed lock
- queue
- priority

Bu “aynı resource’a aynı anda çalışma” problemini çözer.

Ama Argo genelde şunu der:

synchronization:
  mutex:
    name: media-folder

Yani lock’u workflow author koyar. Plugin kendi “ben şu path’i değiştireceğim” manifestiyle orchestration’a etki etmez.

Prefect

Lock manager / transaction lock var. Ama yine plugin-declared side effect graph değil.

Kestra

Task dependencies flow tarafından belirlenir. Resource conflict için worker groups, retries, flow design, concurrency ayarları var. Ama senin dediğin gibi “plugin kendi declared effect’leriyle ordering oluştursun” modeli Kestra’nın ana modeli değil.

Archiverr’ın farkı

Archiverr’da plugin şunu manifestte bildiriyor:

provides:
  - fs.write:/target

Bu potansiyel olarak çok güçlü. Çünkü workflow author’ın her şeyi bilmesi gerekmez; plugin kendi orchestration metadata’sını taşır.

Bu doğru fikir.

Ama şu an eksik taraf:

▎ Bu provides/effects deklarasyonu enforcement veya lock scheduling’e tam dönüşmemiş.

Yani fikir iyi, implementation ham.

---
9. Archiverr’daki provides yanlış mı?

Hayır.

Ama şu an üç farklı şeyi karıştırma riski var:

1. capability / permission
2. produced data / dependency signal
3. side effect / resource mutation

Bunları ayırırsan sistem çok daha net olur.

Şu an:

provides:
  - http.request
  - state.update
  - fs.write:/path

Bunların hepsi aynı listede. Bu pratik ama semantik olarak bulanık.

Benim önerim:

Şimdilik bozma

Mevcut sistemi kırma.

Ama docs ve validator içinde internal classification yap:

provide kind:
  - capability_signal: http.request
  - data_signal: metadata.movie
  - resource_effect: fs.write:/path

Yani manifest aynı kalabilir:

provides:
  - http.request
  - state.update
  - fs.write:/media

Ama runtime bunları sınıflandırır.

İleride istersen v2 manifest:

capabilities:
  - http.request

outputs:
  - metadata.movie

effects:
  - fs.write:/media

Ama bugün migration yapma. Önce kavramları netleştir.

---
10. Archiverr plugin sistemini ayrı middleware yapmalı mıyız?

Cevap: Şu an hayır.

Çünkü Archiverr’daki en değerli şeyler domain-specific:

per_run / per_job
PARSE / DATA / OUTPUT
JobState
media metadata flow
dry_run/no_delete
plugin result shape
filesystem safety

Bunları generic yapmaya çalışırsan ya:

A) hepsini soyutlayıp sistemi anlamsızlaştırırsın

ya da:

B) her projeye Archiverr'ın medya kokusunu taşırsın

İkisi de kötü.

Ama ileride evet, küçük bir kernel çıkarılabilir

Bu kernel şunları içerebilir:

Manifest model
Requirement matcher
Trigger rules
Topological grouping
Event bus interface
Provides/effects registry
Plugin services protocol
Execution planner
Validation toolkit

Ama şunları içermemeli:

PARSE/DATA/OUTPUT
per_job media state
JobState
Archiverr config merge detayları
media plugin names
scanner/renamer/tmdb assumptions

Yani:

archiverr-runtime-kernel
  generic primitives

archiverr-media-runtime
  media-specific recipe

Ama bunu şimdi paketleme. Önce Archiverr içinde sınırları temizle.

---
11. Averager / AI orchestration projesine Archiverr modeli taşınır mı?

Evet, ama aynen değil.

Averager’da senin problem domain’in farklı:

Archiverr:

file/media jobs
deterministic pipeline
per_run input -> per_job stages

Averager:

agent/event/research/finding/evidence graph
long-running orchestration
event-driven agents
epistemic state
tools
possibly self-improving workflows

Burada Archiverr’ın 3-stage modeli yetmez. Ama Archiverr’dan şu prensipleri taşı:

1. Core plugin/agent isimlerini bilmez.
2. Agent manifest kendi contract’ını bildirir.
3. Requires/provides/effects ile order ve readiness belirlenir.
4. Core sadece state primitives ve safety rails sağlar.
5. Domain’in hard rails’i korunur.

Averager’da muhtemel manifest:

name: scope-reviewer
kind: agent
api_version: averager.agent/v1

triggers:
  - event: research.completed

requires:
  - artifact.research.brief:exists

provides:
  - finding.candidate
  - evidence.linked

capabilities:
  - llm.call
  - web.search
  - db.read

effects:
  - db.write:findings

Burada provides daha çok epistemik çıktı, effects mutation.

---
12. Epistemic zincir core’da mı plugin/agent mı olmalı?

Bu senin 18.md’deki en önemli soru.

Şunlar:

- evidence ekleme
- finding ekleme
- meaning oluşturma
- meaning compress
- voting
- review
- recommendation

Plugin mi core mu?

Net cevabım

Veri modeli ve invariant’lar core’da kalmalı.

Epistemik işlemler agent/plugin olabilir.

Yani:

Core:
  - Evidence table
  - Finding table
  - Claim/Meaning table
  - provenance model
  - append-only history
  - validation rules
  - permission/safety rules
  - transaction boundaries
  - canonical APIs/tools

Agents/plugins:
  - evidence extraction
  - finding proposal
  - meaning synthesis
  - critique/review
  - voting strategy
  - compression strategy
  - ranking/scoring

Bu modülerlik ve stabilite savaşını çözen ayrım.

Neden?

Eğer evidence/finding tablolarını plugin yaparsan sistem kendi epistemik zeminini kaybeder. Plugin bozulursa gerçeklik modeli bozulur.

Ama evidence çıkarma stratejisini plugin yaparsan potansiyel artar.

Doğru model:

Core owns truth ledger.
Plugins propose entries.
Core validates/commits.

Bu çok önemli.

---
13. Tasker örneği burada ne öğretiyor?

Archiverr’da Tasker’ı plugin yapmak mantıklıydı çünkü Tasker:

domain-specific output behavior
template-driven action executor

Core invariant değildi.

Ama Averager’da evidence ledger core invariant’tır.

Yani şu ayrım:

Tasker = behavior plugin olabilir
Evidence DB = substrate/core olmalı
Evidence extraction = plugin olabilir
Evidence commit API = core olmalı

Bu ayrımı kaçırırsan sistem kendi kendini bozabilen bir şeye dönüşür.

---
14. “Her şey plugin olsun” nerede yanlış?

Her şey plugin olursa potansiyel artar gibi görünür ama aslında sistemin sabit noktası kalmaz.

Bir orchestration sisteminde core’un görevi az ama sert olmalı:

Core:
  - identity
  - state model
  - event log
  - artifact store
  - transaction/safety
  - scheduler
  - permission/capability checks
  - invariant validation

Bunlar plugin olmamalı.

Plugin’ler:

- strategy
- interpretation
- integration
- transformation
- external side effects
- agent behavior

olmalı.

Bu senin “stabilite + potansiyel” dengenin cevabı.

---
15. Archiverr’a şimdi ne katmalıyız?

1. Manifest versioning

api_version: archiverr.plugin/v1
min_core_version: "0.3.0"

Keep. Düşük maliyet, yüksek gelecek değeri.

---
2. Plugin validation CLI

archiverr plugin validate tmdb
archiverr plugin inspect tmdb

Kontrol:

- manifest valid
- class exists
- run_mode/stage uyumlu
- execute signature doğru
- requires syntax doğru
- unknown plugin refs
- provides/effects format doğru
- config_schema doğru

Keep. En değerli iyileştirme bu.

---
3. Provides semantiğini netleştir

Bugün migration yapmadan docs/validator ekle:

provides = declared outputs/effects, not permission
capabilities = permission/may-do, future

İç sınıflandırma:

http.request       -> capability-like signal
state.update       -> state effect
fs.write:/path     -> resource effect
metadata.movie     -> data output

Keep.

---
4. Lock planner

Şu an fs_lock ve lockable provides var ama gerçek scheduling’e daha çok bağlanmalı.

Basit hedef:

Aynı path üzerinde conflicting fs.write/fs.move/fs.delete sağlayan pluginler
aynı parallel group'ta çalışmasın.

Yani resolver sadece dependency değil, conflict de çözsün:

Dependency edges + resource conflict edges = execution groups

Bu Archiverr’ın en domain-specific ama güçlü gelişimi olur.

Keep. Bu Kestra’dan daha Archiverr’a yakışan fikir.

---
5. Retry/timeout

Manifest’e basit reliability ekle:

reliability:
  timeout_seconds: 60
  retries: 2

Ama hemen distributed durable workflow yapma.

Simplify. Basit timeout/retry yeter.

---
6. Artifact store

Büyük plugin output’ları için:

PluginResult.data küçük kalsın.
Büyük şey artifact URI olsun.

Keep.

---
16. Archiverr’a ne katmamalıyız?

1. Kestra entegrasyonu

Remove. Ağır ve domain dışı.

2. Marketplace

Şu an erken.

Önce:

- docs
- template
- validate
- api_version

sonra marketplace.

3. Container/subprocess isolation

Şu an erken. Ama design’da kapıyı kapatma.

4. Generic “universal plugin middleware”

Şu an yapma. Önce iki proje içinde aynı prensipleri ayrı recipe olarak uygula. Üçüncü projede tekrar aynı çekirdeği yazma ihtiyacı doğarsa extraction zamanı gelir.

Bu “three strikes rule” burada geçerli:

1. Archiverr: media recipe
2. Averager: agent/epistemic recipe
3. Üçüncü proje: tekrar aynı kernel ihtiyacı

O zaman extraction.

---
17. Archiverr vs Kestra: senin görüşün doğru mu?

Sen diyorsun ki:

▎ Kestra potansiyele abanmış; biz stabilite + potansiyel dengesindeyiz.

Bence bu doğru ama şöyle düzeltmek lazım:

Kestra da stabiliteye önem veriyor, hatta enterprise workflow için çok stabil tasarlanmış. Ama stabiliteyi şu yolla sağlıyor:

platform-level stability
repository/queue/workers/versioned plugins/YAML flows

Archiverr ise stabiliteyi şu yolla sağlıyor:

domain-level constraints
3 stages
plugin-agnostic core
dry-run/no-delete
manifest contract
limited execution model

Bu ikisi farklı stabilite türü.

Kestra’nın stabilitesi büyük platform stabilitesi.
Archiverr’ın stabilitesi domain invariant stabilitesi.

Archiverr için doğru olan ikincisi.

---
18. En net mimari karar

Şunu yaz bir yere:

Archiverr plugin runtime generic workflow engine olmayacak.

Archiverr, medya metadata domain'i için daraltılmış,
manifest-driven, effect-aware plugin orchestration runtime olacak.

Genericleşecek şey implementation değil; prensipler olacak:
- manifest contract
- requires/provides/effects
- trigger rules
- deterministic grouping
- side-effect conflict planning
- plugin-agnostic core
- validation-first SDK

---
19. Kısa plan

Phase 1 — Archiverr plugin sistemi sertleştir

1. api_version ekle.
2. archiverr plugin validate ekle.
3. requires/provides static validator yaz.
4. provides dokümanında permission değil declared effect olduğunu açıkla.
5. Plugin author guide + template oluştur.

Phase 2 — Effect-aware scheduler

1. provides değerlerini sınıflandır:
  - data output
  - capability signal
  - resource effect
2. fs.write/fs.move/fs.delete conflict planner ekle.
3. Aynı path conflict’i olan pluginleri parallel group’tan ayır.
4. fs_lock ile provides fs.* ilişkisini netleştir.

Phase 3 — Reliability

1. timeout
2. retry
3. failure policy
4. artifact store URI
5. plugin execution history daha net recovery model

Phase 4 — Averager’a prensipleri taşı

Archiverr kodunu direkt kopyalama. Şu modeli kur:

Core ledger:
  evidence/finding/meaning/event/artifact DB

Agent/plugin runtime:
  manifest-driven agents
  requires/provides/effects
  event triggers
  tools exposed by core

Epistemic DB core’da. Epistemic stratejiler agent/plugin.

Phase 5 — ancak sonra kernel düşün

Archiverr + Averager’da aynı kod tekrar ederse:

orchestration-kernel
  requirement matcher
  trigger evaluator
  manifest validator
  execution planner
  event interface

çıkarılır.

---
Son hüküm

Abi senin sezgin doğru: Archiverr’daki sistemin değeri “her projeye takılabilir plugin middleware” olmasında değil. Değeri:

▎ Domain’e özel stabil rails içinde, pluginlere yüksek potansiyel tanıyan orkestrasyon modeli.

Kestra’yı gördün diye “bizimki küçük kalmış” deme. Kestra başka sınıf. Archiverr’ın kazanımı Kestra olmak değil; Kestra gibi sistemlerden SDK, validation, docs, retry, artifact, plugin template fikirlerini alıp, kendi domain-specific stabilitesini korumak.

Provides fikrini de atma. Sadece adını ve semantiğini netleştir:

capability = yapabilir
provide/effect = yapacağını/üreteceğini beyan eder
requires = çalışmak için gözlemek zorunda olduğu şey

Bu ayrım gerçekten güçlü. Özellikle filesystem/cloud sync/side-effect ordering gibi yerlerde klasik workflow engine’lerin çoğundan daha domain-aware bir model kurmanı sağlar.
Interrupted · What should Claude do instead?

❯ şuana kadar anladığın hali ile bizim projenin felsefesini kurallarını öne çıkan yanlarını eksikliklerini diğer projelerden farklarını başka yapay zekaların okuyacağını bilerek bizim projeyi en net başka ai lere tanıtma ve her türlü kararı verirken bizim prjenina maıcnı yapısınıı yazım flsefesini çalışma prensiplerini vs bilemelerini sağlatacak AGENT.md dosyasını oluştursana direkt kök dizininde

  Listed 1 directory

● Write(AGENT.md)
Wrote 377 lines to AGENT.md
 AGENT.md — Archiverr Project Philosophy and Decision Guide

his file is for AI agents and humans working on Archiverr. Read it before making architecture decision

# What Archiverr Is

rchiverr is a plugin-driven media archive orchestration system.

etadata playground for media archives: movies, shows, anime, subtitles, file organization, provider me
adata, output generation, and future integrations.
… +395 lines

AGENT.md kök dizinde oluşturuldu:

/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/AGENT.md

İçine projenin felsefesini, mimari karar kurallarını, Archiverr’ın diğer sistemlerden farkını, güçlü/zayıf yanlarını, requires/provides ayrımını, Kestra/Temporal/Claude Code gibi sistemlerden ne alınması/ne alınmaması gerektiğini ve “core mu plugin mi?” karar kuralını yazdım.
