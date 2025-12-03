# FINAL CHANGELOG v2

## TERMINOLOJI

match -> job
execution -> run
MatchState -> JobState
ExecutionState -> RunState
execution_id -> run_id
not_supported -> skipped
requires_prefix -> default_alias

## STAGE SISTEMI

6 stage -> 4 stage
input/extract/metadata/modify/finalize/output -> input/parse/data/output
ingest reddedildi
enrich reddedildi
modify kaldirildi
finalize kaldirildi

## INPUT OUTPUT YAPISI

input.path -> input.value
output.paths -> output.values
input.data eklendi
output.data eklendi
size_bytes input.data icinde
virtual data destegi input.value ile

## GLOBAL STATE YAPISI

run: jobs ici bos (referans job id ile)
job: plugins ici bos (referans plugin id ile)
plugins: ayri global state
memory management sadece plugins icin

## PROVIDES SISTEMI

kategori bazli -> teknik etki bazli
metadata._ kaldirildi
notification._ kaldirildi
data.\* kaldirildi
http.response kaldirildi

fs.copy eklendi
fs.hardlink eklendi
fs.symlink eklendi
fs.mkdir eklendi
fs.chmod eklendi
process.spawn eklendi
process.exec eklendi
input.value eklendi
input.data eklendi
output.values eklendi
output.data eklendi

state.updated -> state.update
job.created -> job.create

## LOCKABLE PROVIDES

fs.write
fs.delete
fs.move
fs.hardlink
fs.symlink

## NON-LOCKABLE PROVIDES

fs.read
fs.copy
fs.mkdir
fs.chmod
http.request
job.create
state.update
process.spawn
process.exec
input.value
input.data

## PROVIDES LOCK

path-based lock eklendi
syntax: fs.write:/path
config._ degiskeni gecerli
job._ degiskeni gecersiz
run.\* degiskeni gecersiz

## REQUIRES SISTEMI

implicit parsing -> explicit prefix
after kaldirildi
depends*on kaldirildi
waits_for kaldirildi
triggers_on kaldirildi
prefix zorunlu: provides.* job.\_ events.\*

## TRIGGER RULES

all_success default
one_success eklendi
all_done eklendi
all_fail eklendi
none_fail eklendi
always kaldirildi (all_done ile ayni)

## CONFIG SISTEMI

plugins wrapper kaldirildi
FlexGet style eklendi
enabled key varsa true
tvdb: false disabled
aliases top-level eklendi

## INCLUDE SISTEMI

!include_list KALDIRILDI
!include_merge KALDIRILDI
sadece !include ./path kullanilir
dizin verilirse tum yml dosyalari yuklenir
tekil dosya verilirse o dosya yuklenir

## MANIFEST SISTEMI

category -> stage
depends_on kaldirildi
expects -> requires
provides eklendi
trigger_rule eklendi
reactive eklendi
config_schema eklendi

## CONFIG MANIFEST ILISKISI

manifest uste import
config alta kalir
config kazanir
immutable: name version stage class_name entry_point
mutable: requires provides trigger_rule reactive config_schema
list merge = replace

## CONFLICT DETECTION

startup detection eklendi
ayni path ayni stage = error
parent-child overlap = warning
generic provides = info
force bypass eklendi

## VALIDATION KATMANLARI

startup: config syntax schema conflict dynamic-var
pre-execution: requires plugin-init
runtime kaldirildi (run asla durmasin)

## PLUGIN SERVICES

get_debugger kaldirildi
services.state eklendi
services.events eklendi
services.logger eklendi
services.config eklendi
tek interface

## STATE STRUCTURE

plugins nested by stage -> flat
plugins job icinden cikarildi
plugins ayri collection
stage bilgisi manifest te
template erisimi kolaylasti
job.plugins.tmdb.movie (lazy load)

## JOB IDENTIFICATION

index: single run scope
job*id: global unique
format: job*{run*id}*{index}

## MONGODB

executions -> runs
matches -> jobs
plugin_results -> plugins
plugins ayri collection (memory icin)
nested structure eklendi

## EXECUTION MODE

per_job: her job icin (method: execute)
per_run: tum run icin (method: execute_run)
input stage default per_run
diger stage ler default per_job

## ERROR HANDLING

plugin fail = job devam
stage fail = diger stage devam
run fail = sadece kritik hata
run asla durmasin felsefesi

## MEMORY MANAGEMENT

sadece plugins icin
job ve run kuculdu
hot cold tiering
max_plugins_mb (max_state_mb degil)
flush_threshold
eviction_policy
lazy_cache_size
phase 2 ye birakildi

## DEFAULT ALIAS SISTEMI

sistem: run job jobs plugins config options provides events
short alias kaldirildi
user alias: config.aliases
inline alias: jinja2 set
priority: inline > user > system

## PHASE KURALLARI

input: job olustur input.value + input.data doldur
parse: analiz dosya kaydetme
data: analiz cache kaydedebilir ana dosya kaydetme
output: cikti olustur output.values + output.data doldur

## JOB LOCK

gereksiz
namespace izolasyonu yeterli
requires ile siralama
cross-namespace yazim anti-pattern

## TASKER CONDITION

condition key kaldirildi
jinja2 if/endif kullanilacak
{% if p.movie %}...{% endif %}

## EVENTS

run: started completed failed
job: created started completed failed
stage: started completed failed
plugin: started completed failed
file: created deleted moved copied

## WEB UI KATEGORILERI

INPUT = input + parse
OUTPUT = data + output
